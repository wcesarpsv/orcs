from io import BytesIO
import pytest
from PIL import Image
from app import app
from reports import build_report


def photo():
    out=BytesIO();Image.new('RGB',(24,24),'white').save(out,'JPEG');out.seek(0)
    return out,'photo.jpg'

FIELDS=['sst_front_photo','sst_call_clear_photo','sst_id_photo']


def payload():
    return dict(kind='SST Install',place='Test Retailer',rdl='12345',**{name:photo() for name in FIELDS})

@pytest.mark.parametrize('missing',FIELDS)
def test_each_required_photo(missing,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    data=payload();del data[missing]
    r=app.test_client().post('/api/generate',data=data)
    assert r.status_code==400 and 'Required photo missing' in r.json['error']


def test_summary_and_exports(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    c=app.test_client();r=c.post('/api/generate',data=payload())
    assert r.status_code==200
    data=r.json
    assert data['sections'][0]['text']=='SST Install completed - Test Retailer (RDL: 12345) - Summary'
    assert 'The SST installation has been completed successfully at Test Retailer' in data['plain']
    assert 'Upon inspection, no scratches or damage were observed on either the machine or the surrounding floor area.' in data['plain']
    assert 'The SST key was handed over to the retailer' in data['plain']
    assert [s['text'] for s in data['sections'] if s['image']]==['SST front','Call Clear','SST ID']
    pdf=c.post('/api/pdf',json={'sections':data['sections']})
    assert pdf.status_code==200 and pdf.data.startswith(b'%PDF')


def test_editable_template(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    data=payload();data.update(sst_install_template='SST Install completed - [Store Name] (RDL: [RDL]) - Summary\n\nCustom wording.',details='Retailer received the key.')
    r=app.test_client().post('/api/generate',data=data)
    assert r.status_code==200
    assert r.json['sections'][0]['text'].startswith('SST Install completed - Test Retailer (RDL: 12345) - Summary')
    assert 'Custom wording.' in r.json['plain'] and 'Retailer received the key.' in r.json['plain']


def test_bad_photo(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    data=payload();data['sst_id_photo']=(BytesIO(b'not an image'),'bad.jpg')
    r=app.test_client().post('/api/generate',data=data)
    assert r.status_code==400 and 'unreadable' in r.json['error']


def test_location_required(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    data=payload();data['place']=''
    assert app.test_client().post('/api/generate',data=data).status_code==400


def test_additional_photos_and_pdf(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    data=payload();data['additional_photos']=[photo(),photo()]
    c=app.test_client();r=c.post('/api/generate',data=data)
    assert r.status_code==200
    images=[s for s in r.json['sections'] if s['image']]
    assert [s['text'] for s in images]==['SST front','Call Clear','SST ID','Additional Photo 1','Additional Photo 2']
    assert c.post('/api/pdf',json={'sections':r.json['sections']}).status_code==200


def test_unreadable_additional_photo(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    data=payload();data['additional_photos']=[(BytesIO(b'broken'),'bad.jpg')]
    r=app.test_client().post('/api/generate',data=data)
    assert r.status_code==400 and 'additional photo is unreadable' in r.json['error']


def test_additional_photo_for_pm(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    data=dict(kind='PM',place='Test Store',rdl='12345',key_status='Yes',additional_photos=[photo(),photo()])
    r=app.test_client().post('/api/generate',data=data)
    assert r.status_code==200
    assert [s['text'] for s in r.json['sections'] if s['image']]==['Additional Photo 1','Additional Photo 2']
