import base64
import io
import unittest
from PIL import Image
from app import app

class ReportsTest(unittest.TestCase):
    def setUp(self):
        self.client=app.test_client()
        self.base={'kind':'PM','place':'Test Store','rdl':'12345','key_status':'Yes'}
    def test_key_statuses(self):
        for status,dest,reason,expected in [('Yes','','','successfully collected'),('No','','Retailer needs access','returned to the retailer'),('Return SST Key','Warehouse','','previous visit')]:
            r=self.client.post('/api/generate',data={**self.base,'key_status':status,'key_destination':dest,'key_reason':reason})
            self.assertEqual(r.status_code,200)
            self.assertIn(expected,r.json['sections'][-1]['text'])
        for fields in [{'key_status':''},{'key_status':'No'},{'key_status':'Return SST Key'}]:
            self.assertEqual(self.client.post('/api/generate',data={**self.base,**fields}).status_code,400)
    def test_breakfix_serial_validation_and_photo_pdf(self):
        data={'kind':'BREAKFIX WJS','place':'Test & <Store>','rdl':'RDL: 12345','old_sn':'OLD1'}
        self.assertEqual(self.client.post('/api/generate',data=data).status_code,400)
        image=io.BytesIO();Image.new('RGB',(400,200),'red').save(image,'PNG');image.seek(0)
        r=self.client.post('/api/generate',data={**data,'new_sn':'NEW2','new_photo':(image,'label.png')})
        self.assertEqual(r.status_code,200)
        self.assertIn('OLD1',r.json['plain']);self.assertIn('NEW2',r.json['plain'])
        self.assertIn('&lt;Store&gt;',r.json['html'])
        self.assertIn('data:image/jpeg;base64,',r.json['html'])
        pdf=self.client.post('/api/pdf',json={'sections':r.json['sections']})
        self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.data.startswith(b'%PDF'))
    def test_types_and_validation(self):
        for kind in ['INSTALLATION','DEINSTALLATION']:
            r=self.client.post('/api/generate',data={**self.base,'kind':kind})
            self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.post('/api/generate',data={**self.base,'rdl':'123abc'}).status_code,400)
        self.assertEqual(self.client.post('/api/pdf',json={'sections':[]}).status_code,400)
        self.assertEqual(self.client.post('/api/generate',data={**self.base,'call_photo':(io.BytesIO(b'bad'),'bad.png')}).status_code,400)
    def test_page(self):
        r=self.client.get('/');self.assertEqual(r.status_code,200);self.assertIn(b'ORCS Reports',r.data)
        self.assertEqual(self.client.get('/api/health').status_code,200)

if __name__=='__main__':unittest.main()
