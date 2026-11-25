from io import BytesIO
from unittest.mock import patch
import zipfile
from PIL import Image
from app import app
from test_sst_pm import payload


def photo():
 out=BytesIO();Image.new('RGB',(20,20),'white').save(out,'JPEG');out.seek(0);return out,'call.jpg'


def test_call_photo_extracts_location_without_report(monkeypatch):
 monkeypatch.setenv('OPENAI_API_KEY','test-key')
 with patch('app.OpenAI'),patch('app.extract',return_value={'place_name':'Test Store','rdl':'00123'}) as read:
  r=app.test_client().post('/api/sst-pm/extract',data={'mode':'place','photo':photo()})
  assert r.status_code==200 and r.json=={'place_name':'Test Store','rdl':'00123'}
  assert read.call_args.args[2]=='place'


def test_unreadable_rdl_not_invented(monkeypatch):
 monkeypatch.setenv('OPENAI_API_KEY','test-key')
 with patch('app.OpenAI'),patch('app.extract',return_value={'place_name':'Test Store','rdl':'RDL: unclear'}):
  r=app.test_client().post('/api/sst-pm/extract',data={'mode':'place','photo':photo()})
  assert r.status_code==200 and r.json['rdl']==''


def test_call_photo_errors(monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 assert app.test_client().post('/api/sst-pm/extract',data={'mode':'place','photo':photo()}).status_code==503
 monkeypatch.setenv('OPENAI_API_KEY','test-key')
 with patch('app.OpenAI'),patch('app.extract',side_effect=ValueError):
  assert app.test_client().post('/api/sst-pm/extract',data={'mode':'place','photo':photo()}).status_code==502
 assert app.test_client().post('/api/sst-pm/extract',data={'mode':'place','photo':(BytesIO(b'broken'),'call.jpg')}).status_code==400


def test_direct_excel_before_key_and_summary():
 p=payload();p.update(format='xlsx',key_status='',notes='')
 r=app.test_client().post('/api/sst-pm/report',json=p)
 assert r.status_code==200 and r.data.startswith(b'PK')
 assert 'DC_SST_Components_RDL_44483.xlsx' in r.headers['Content-Disposition']
 z=zipfile.ZipFile(BytesIO(r.data))
 assert b'SERIAL001' in z.read('xl/worksheets/sheet1.xml')
 assert b'Not recorded' in z.read('xl/worksheets/sheet3.xml')
 assert b'PM summary not finalized' in z.read('xl/worksheets/sheet3.xml')
 p['format']='preview'
 assert app.test_client().post('/api/sst-pm/report',json=p).status_code==400


def test_excel_keeps_double_check_validation():
 p=payload();p.update(format='xlsx',key_status='')
 p['components'][1]['physical']=''
 r=app.test_client().post('/api/sst-pm/report',json=p)
 assert r.status_code==400 and 'physical serial is required' in r.json['error']


def test_start_and_direct_export_buttons():
 html=app.test_client().get('/').data.decode()
 assert html.index('id="sst-call-photo"')<html.index('id="sst-visit-details"')
 assert 'id="sst-read-call"' in html and 'id="sst-excel-direct"' in html
