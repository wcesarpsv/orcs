import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from inventory import identify,prepare_item,register_routes,RULES
from flask import Flask

@pytest.mark.parametrize('name,serial',[
 ('PIN PAD','P1234567'),('PRINTER VKP80III','MEC3013623150848'),
 ('19INCH CARMANAH SIGN','EMONJC123456'),('30INCH CARMANAH SIGN','EMONJC123456'),('30INCH NEW CARMANAH SIGN','EMONJC123456'),
 ('4.5 INCH BETSLIP RDR','8000001234567890'),('BURSTER ASSY','192582123456'),('QUAD BURSTER ASSY','192582123456'),
 ('DS4608 SCANNER -BLACK','24347010559249'),('MAINBOARD ENCLOSURE','0118DC5B1F0000E1')])
def test_catalog(name,serial):
 assert name in identify(serial)['candidates']
 assert prepare_item(dict(product=name,serial=serial))['serial']==serial

def test_ambiguity_and_preservation():
 assert len(identify('EMONJC123456')['candidates'])==3
 assert len(identify('192582123456')['candidates'])==2
 assert identify(" *0118-dc5b 1f0000e1* ")['serial']=='0118DC5B1F0000E1'
 assert identify('P１２３４５６７')['candidates']==[]
 assert identify('not a serial')['candidates']==[]

@pytest.mark.parametrize('data',[
 {'product':'BURSTER ASSY','serial':'P1234567'},
 {'product':'PIN PAD','serial':'P1234567','active_cn':'G123456'},
 {'product':'PIN PAD','serial':1234567},
 {'product':'PIN PAD','serial':'P1234567','condition':'Installed'},
 {'product':'PIN PAD','serial':'P1234567','notes':'a'*2001},
])
def test_invalid(data):
 with pytest.raises(ValueError):prepare_item(data)

def test_routes():
 calls=[]
 def cloud(method,path,payload=None):
  calls.append((method,path,payload))
  if 'members?' in path:return [{'active':True}]
  if path.startswith('rpc/'):return payload['p_data']
  return []
 app=Flask(__name__);register_routes(app,cloud);client=app.test_client()
 assert client.get('/api/inventory/catalog').status_code==200
 assert client.post('/api/inventory/identify',json={'serial':'P1234567'}).json['candidates']==['PIN PAD']
 assert client.post('/api/inventory/identify',json=[]).status_code==400
 body=dict(action='add',request_id='dfc190eb-954f-430c-9c4e-039edb3b6c2b',data=dict(product='PIN PAD',serial='p1234567'))
 assert client.post('/api/inventory/action',json=body).status_code==200
 assert calls[-1][2]['p_data']['serial']=='P1234567'
 assert 'owner_id' not in calls[-1][2]['p_data']
 body['data']['owner_id']='forged'
 assert client.post('/api/inventory/action',json=body).status_code==200
 assert 'owner_id' not in calls[-1][2]['p_data']
 body['action']='install';body['data']={'id':'dfc190eb-954f-430c-9c4e-039edb3b6c2b','revision':1}
 assert client.post('/api/inventory/action',json=body).status_code==400
 assert client.get('/api/inventory/items').status_code==200
 assert client.get('/api/inventory/history/not-uuid').status_code==400
