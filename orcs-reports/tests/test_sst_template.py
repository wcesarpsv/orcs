from unittest.mock import Mock,patch
from app import app

UID='00000000-0000-4000-8000-000000000001'

def test_sst_template_account_workflow(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL','https://example.invalid')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','test-public-key')
    c=app.test_client();url='/api/report-template/SST%20Install'
    assert c.put(url,json={'template':'custom'}).status_code==401
    headers={'Authorization':'Bearer test-only-token'}
    with patch('requests.get') as get,patch('requests.post') as post,patch('requests.delete') as delete:
        get.side_effect=[Mock(ok=True,json=lambda:{'id':UID}),Mock(ok=True,json=lambda:[{'template_text':'My SST template'}])]
        assert c.get(url,headers=headers).json['template']=='My SST template'
        assert get.call_args.kwargs['params']['report_type']=='eq.SST Install'
        get.side_effect=None;get.return_value=Mock(ok=True,json=lambda:{'id':UID})
        post.return_value=Mock(ok=True)
        response=c.put(url,headers=headers,json={'template':'My SST template','user_id':'forged'})
        assert response.status_code==200
        assert post.call_args.kwargs['json']=={'user_id':UID,'report_type':'SST Install','template_text':'My SST template'}
        assert c.put(url,headers=headers,json={'template':''}).status_code==400
        delete.return_value=Mock(ok=True)
        assert c.delete(url,headers=headers).status_code==200
        assert delete.call_args.kwargs['params']=={'user_id':'eq.'+UID,'report_type':'eq.SST Install'}
        get.return_value=Mock(ok=False)
        assert c.put(url,headers=headers,json={'template':'My SST template'}).status_code==401


def test_sst_screen_order():
    s=app.test_client().get('/').data.decode()
    assert s.index('id="sst-install-fields"')<s.index('id="additional-report-photos"')<s.index('id="service-work"')<s.index('id="sst-install-report-template"')
    section=s.split('id="sst-install-report-template"',1)[1].split('</section>',1)[0]
    for id in ['sst-install-template','save-sst-install-template','restore-sst-install-template','sst-install-template-status']:
        assert 'id="'+id+'"' in section
    photos=s.split('id="sst-install-fields"',1)[1].split('</section>',1)[0]
    assert '<textarea' not in photos
