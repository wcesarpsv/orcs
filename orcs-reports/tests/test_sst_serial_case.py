from io import BytesIO
from zipfile import ZipFile
import pytest
from unittest.mock import patch
from app import app
from sst_pm import prepare
from test_sst_pm import payload


def test_case_only_difference_matches_and_exports_uppercase():
 p=payload();p['components'][0].update(reference='  00ab1cD-ef  ',physical='00AB1CD-EF',reason='',confirmed=False)
 pm=prepare(p)
 assert pm['components'][0]['status']=='OK'
 assert pm['components'][0]['reference']==pm['components'][0]['physical']=='00AB1CD-EF'
 r=app.test_client().post('/api/sst-pm/report',json={**p,'format':'xlsx'})
 assert r.status_code==200
 data=ZipFile(BytesIO(r.data)).read('xl/worksheets/sheet1.xml')
 assert b'00AB1CD-EF' in data and b'00ab1cD-ef' not in data


def test_case_insensitive_duplicate_is_rejected():
 p=payload();p['components'][0].update(reference='00ab1cd',physical='00AB1CD');p['components'][1]['reference']='00AB1CD'
 with pytest.raises(ValueError,match='duplicate reference serial'):prepare(p)


def test_real_difference_still_requires_observation():
 p=payload();p['components'][0].update(reference='00abc1',physical='00ABC2',reason='',confirmed=True)
 with pytest.raises(ValueError,match='serial difference'):prepare(p)


def test_cloud_save_receives_canonical_serials():
 p=payload();p['components'][0].update(reference='00aBc1',physical='00ABC1',reason='')
 with patch('app.sst_cloud_request',return_value={'revision':1}) as cloud:
  r=app.test_client().post('/api/sst-pm/save',json=p)
  assert r.status_code==200
  row=cloud.call_args.args[2]['p_record']['components'][0]
  assert row['reference']==row['physical']=='00ABC1'
