import unittest,io,zipfile,base64,xml.etree.ElementTree as ET
from unittest.mock import patch
from PIL import Image
from app import app
from sst_pm import COMPONENTS,NO_TEST,prepare,sections,excel,labels

def payload():
 return dict(sst_id='100164',sst_serial='4966100164',place='Test Store',rdl='44483',technician='Test Technician',date='2026-11-14',key_status='Yes',components=[dict(name=n,reference='' if n=='Key' else f'SERIAL{i:03}',physical='' if n=='Key' else f'SERIAL{i:03}',test='' if n in NO_TEST else 'Passed',reason='',confirmed=False,absent=False) for i,n in enumerate(COMPONENTS)],photos=[])
class SstPmTests(unittest.TestCase):
 def setUp(self):self.client=app.test_client()
 def test_key_is_optional_through_exports(self):
  p=payload();pm=prepare(p);self.assertTrue(pm['completed']);self.assertEqual(pm['components'][-1]['status'],'Optional — not provided');self.assertEqual(pm['components'][-1]['test'],'Not applicable')
  for format,magic in [('xlsx',b'PK'),('labels',b'%PDF'),('pdf',b'%PDF')]:
   r=self.client.post('/api/sst-pm/report',json={**p,'format':format});self.assertEqual(r.status_code,200);self.assertTrue(r.data.startswith(magic))
  with open('/workspace/scratch/35f2fe03da48/sst_pm_test.xlsx','wb') as f:f.write(excel(pm))
  with open('/workspace/scratch/35f2fe03da48/sst_pm_labels.pdf','wb') as f:f.write(labels(pm))
 def test_required_serial_and_test(self):
  p=payload();p['components'][1]['physical']='';self.assertRaises(ValueError,prepare,p)
  p=payload();p['components'][1]['test']='';self.assertRaises(ValueError,prepare,p)
 def test_mismatch_requires_reason_and_confirmation(self):
  p=payload();r=p['components'][1];r['physical']='REPLACED1';self.assertRaises(ValueError,prepare,p);r['confirmed']=True;self.assertRaises(ValueError,prepare,p);r['reason']='Found undocumented replacement';self.assertEqual(prepare(p)['components'][1]['status'],'Previously Swapped / Not Documented')
 def test_failed_pm_does_not_claim_completion_or_save(self):
  p=payload();p['components'][1]['test']='Failed';p['components'][1]['reason']='Jam during test';pm=prepare(p);self.assertFalse(pm['completed']);self.assertIn('NOT COMPLETED',sections(pm)[0]['text'])
  with patch('app.sst_cloud_request') as cloud:
   r=self.client.post('/api/sst-pm/save',json=p);self.assertEqual(r.status_code,400);cloud.assert_not_called()
 def test_router_not_installed(self):
  p=payload();p['components'][-2].update(reference='',physical='',absent=True,test='');self.assertEqual(prepare(p)['components'][-2]['status'],'Not installed')
 def test_duplicate_serial_and_sst_identity(self):
  p=payload();p['components'][1]['physical']=p['components'][0]['physical'];self.assertRaises(ValueError,prepare,p)
  p=payload();p['sst_serial']='4966999999';self.assertRaises(ValueError,prepare,p)
 def test_photo_summary(self):
  p=payload();buf=io.BytesIO();Image.new('RGB',(30,30),'white').save(buf,'JPEG');p['photos']=[dict(caption='Cleaned rollers',image=base64.b64encode(buf.getvalue()).decode())]
  r=self.client.post('/api/sst-pm/report',json=p);self.assertEqual(r.status_code,200);self.assertIn('Cleaned rollers',r.json['plain']);self.assertIn('data:image/jpeg',r.json['html'])
 def test_cloud_config_never_claims_saved_when_unconfigured(self):
  with patch.dict('os.environ',{'SUPABASE_URL':'','SUPABASE_PUBLISHABLE_KEY':''}):
   self.assertFalse(self.client.get('/api/sst-pm/config').json['cloud_ready']);self.assertEqual(self.client.post('/api/sst-pm/save',json=payload()).status_code,400)
 def test_cloud_save_strips_photos_and_preserves_revision(self):
  p=payload();p.update(expected_revision=2,request_id='37ec0da3-6ec8-4fb5-99fc-b6a2049276fe')
  with patch('app.sst_cloud_request',return_value={'revision':3}) as call:
   r=self.client.post('/api/sst-pm/save',json=p);self.assertEqual(r.status_code,200);body=call.call_args.args[2];self.assertNotIn('photos',body['p_record']);self.assertEqual(body['p_expected_revision'],2)
 def test_template_values_and_no_key_label(self):
  p=payload();p['components'][-1].update(reference='KEY123',physical='KEY123');pm=prepare(p);z=zipfile.ZipFile(io.BytesIO(excel(pm)));ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};data=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
  self.assertEqual(data.find('.//x:c[@r="G19"]/x:is/x:t',ns).text,'KEY123');self.assertNotIn(b'KEY123',z.read('xl/worksheets/sheet2.xml'));self.assertNotIn(b'192582150539',z.read('xl/sharedStrings.xml'))
 def test_existing_reports_and_key_not_required_html(self):
  page=self.client.get('/').data;self.assertIn(b'<option>SST PM</option>',page);self.assertIn(b'Key serials are optional',page);self.assertIn(b'<option>PM</option>',page)
if __name__=='__main__':unittest.main()
