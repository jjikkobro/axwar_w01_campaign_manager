"""Create review cases only on an isolated local test server."""
import json,os
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8086')
if urlparse(BASE).hostname not in ['localhost','127.0.0.1']:raise SystemExit('Local test server required')
def call(path,body=None,expected=200):
 try:
  with urlopen(Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})) as r:code=r.status;data=json.load(r)
 except HTTPError as e:code=e.code;data=json.load(e)
 assert code==expected,(path,code,data)
 return data

def main():
 state=call('/api/state');record=state['finance']['overdue'][0]
 call('/api/finance',{'role':'재무','version':state['finance_version'],'operation':'overdue_reply','record_id':record['id'],'date':None,'provenance':'모의 회신','decision_maker':'검증 담당','reason':'독립 테스트 초기 조건','evidence':'실제 회신 아님'})
 from tests.test_finance import FinanceTests
 from tests.test_finance_review import ReviewTests
 fixture=FinanceTests();fixture.setUp();sample=ReviewTests();sample.setUp()
 cid=call('/api/cases',{'role':'SCM','case':fixture.case})['id'];results=[]
 def payload(op,review=None):
  state=call('/api/state');d=call('/api/cases/'+cid)
  return {'role':'재무','id':cid,'version':d['case']['version'],'finance_version':state['finance_version'],'operation':op,'review':review or sample.raw}
 p=payload('save');call('/api/finance-review',{**p,'role':'마케팅'},400);results.append('non-finance rejected')
 call('/api/finance-review',p);call('/api/finance-review',p,409);results.append('stale version rejected')
 before=call('/api/cases/'+cid)['case']['version'];call('/api/finance-review',payload('preview'));assert call('/api/cases/'+cid)['case']['version']==before;results.append('preview does not save')
 call('/api/finance-review',payload('submit'),400);results.append('unconfirmed cash blocks submit')
 s=call('/api/state');call('/api/finance',{'role':'재무','version':s['finance_version'],'operation':'confirm','selected':'exclude_pay','weekend_shift':False,'review_date':'2026-07-01','next_review_date':'2026-07-08','decision_maker':'재무 시연','reason':'독립 검증','evidence':'원본 CSV'})
 call('/api/finance-review',payload('submit'));d=call('/api/cases/'+cid)
 assert d['case']['finance_review']['operation']=='submit' and d['case']['status']!='승인'
 assert any(t['role']=='승인권자' and t['status']=='대기' for t in d['tasks']);results.append('persistent packet and approval task, no approval/order')
 call('/api/finance-review',payload('submit'),400);results.append('duplicate submit rejected')
 review=json.loads(json.dumps(sample.raw));review['requests']=[{'role':'SCM','question':'지급 증빙 확인','answer':''}]
 call('/api/finance-review',payload('request',review));assert any(t['title']=='지급 증빙 확인' and t['status']=='대기' for t in call('/api/cases/'+cid)['tasks']);results.append('real followup task saved')
 result={'case_id':cid,'base':BASE,'checks':results,'passed':True};Path('docs/verification/screen-reviews/03-finance-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
