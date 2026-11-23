"""Verify screen 1 against an isolated local DB/server only; creates demonstration cases."""
import base64,json,os,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse

BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8083')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost'] or urlparse(BASE).scheme!='http':raise SystemExit('Local isolated test server only')

def call(path,body=None,expected=200):
 req=Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 try:
  with urlopen(req,timeout=30) as r:status=r.status;data=json.load(r)
 except HTTPError as e:status=e.code;data=json.load(e)
 assert status==expected,(path,status,data)
 return data

def main():
 from tests.test_marketing import MarketingTests
 fixture=MarketingTests();fixture.setUp();plan=fixture.plan
 initial=call('/api/state');payload={'role':'마케팅','operation':'save','submission_key':str(uuid.uuid4()),'plan':plan}
 created=call('/api/marketing',payload);cid=created['id']
 assert call('/api/marketing',payload)['id']==cid
 detail=call('/api/cases/'+cid)
 assert detail['case']['marketing_stage']=='작성 중'
 assert not any(t['case_id']==cid for t in detail['tasks'])
 assert len(detail['calculation']['items'])==2
 doc=b'actual evidence stored in PostgreSQL'
 call('/api/documents',{'role':'마케팅','id':cid,'version':detail['case']['version'],'name':'marketing-evidence.txt','provenance':'모의 회신','content':base64.b64encode(doc).decode()})
 detail=call('/api/cases/'+cid);did=detail['documents'][0]['id']
 assert urlopen(BASE+'/api/documents/'+did).read()==doc
 call('/api/marketing',{'role':'마케팅','operation':'submit','id':cid,'version':detail['case']['version'],'plan':plan})
 detail=call('/api/cases/'+cid)
 assert detail['case']['marketing_stage']=='SCM 검토 요청'
 assert any(t['case_id']==cid and t['role']=='SCM' and t['status']=='대기' for t in detail['tasks'])
 assert any(t['case_id']==cid and t['role']=='마케팅' for t in detail['tasks'])
 v=detail['case']['version']
 call('/api/action',{'role':'승인권자','id':cid,'version':v,'action':'approve','scope':'SCM 전결','note':'bypass attempt'},400)
 call('/api/assessment',{'role':'재무','id':cid,'version':v,'assessment':{}},400)
 call('/api/marketing',{'role':'마케팅','operation':'save','id':cid,'version':1,'plan':plan},409)
 call('/api/draft',{'role':'마케팅','id':cid,'version':v})
 detail=call('/api/cases/'+cid)
 assert detail['case']['marketing_stage']=='SCM 검토 요청'
 assert detail['case']['approval'] is None
 assert detail['case']['draft']['packet']['project_policy']['id']=='W01-HUMAN-LED-1'
 plan['budget']=900
 call('/api/marketing',{'role':'마케팅','operation':'submit','id':cid,'version':detail['case']['version'],'plan':plan})
 final=call('/api/cases/'+cid)
 assert final['case']['marketing']['reference']['plan']['requested_budget_krw']=='18962703'
 assert final['case']['marketing']['budget']==900
 assert len(final['documents'])==1
 # Existing single-SKU endpoint remains compatible.
 legacy={'title':'single SKU compatibility','sku_id':'SKU-1001','as_of':'2026-07-01','start':'2026-07-13','end':'2026-07-19','quantity':1000,'evidence':'모의 호환 검증','demand_status':'가정'}
 lid=call('/api/cases',{'role':'SCM','case':legacy})['id']
 assert call('/api/cases/'+lid)['calculation']['weekly']==8320.75
 state=call('/api/state');events=[e for e in state['events'] if e['case_id']==cid]
 assert any(e['event']=='마케팅 계획 SCM 검토 요청' and e['detail'].get('before') for e in events)
 assert state['finance']['scenarios']==initial['finance']['scenarios']
 result={'screen':'① 마케팅','source':'격리 로컬 PostgreSQL 실제 실행 · 외부 업무는 모의','checks':{'draft_save_and_reload':True,'duplicate_create_replayed':True,'two_skus_and_periods':True,'file_stored_and_downloaded':True,'scm_handoff_after_human_submission':True,'unknown_performance_task':True,'approval_and_assessment_bypass_blocked':True,'stale_version_conflict':True,'draft_has_policy_and_sources_without_approval':True,'original_and_changed_budget_separate':True,'legacy_case_compatible':True,'budget_not_added_to_cash':True},'case':final['case'],'calculation':{'items':[{'sku':i['sku']['sku_id'],'weekly':i['weekly'],'demand':i['demand'],'weeks':i['weeks']} for i in final['calculation']['items']]},'tasks':[t for t in final['tasks'] if t['case_id']==cid],'events':events}
 target=Path('docs/verification/screen-reviews/01-marketing-results.json');target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print('Screen 1 PostgreSQL checks passed:',len(result['checks']))

if __name__=='__main__':main()
