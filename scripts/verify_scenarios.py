"""Run only against a local test server; persist verifiable scenario evidence."""
import json,os
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8080')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost']:raise SystemExit('Only a local test server is allowed')
events={};report={'base':BASE,'provenance':'모의 회신 / 계산 결과','scenarios':[]}

def call(path,body=None,expected=200):
 req=Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 try:
  with urlopen(req,timeout=30) as response:status=response.status;data=json.load(response)
 except HTTPError as e:status=e.code;data=json.load(e)
 if status!=expected:raise AssertionError((path,status,data))
 return data
def state():
 s=call('/api/state')
 events.update({e['seq']:e for e in s['events']})
 return s
def confirm(sid):
 s=state();call('/api/finance',{'role':'재무','version':s['finance_version'],'operation':'confirm','selected':sid,'weekend_shift':False,'review_date':'2026-07-01','next_review_date':'2026-07-08','decision_maker':'재무 시연 담당자','reason':'검증 시나리오 확정','evidence':'원본 AR·AP·발주 스케줄 + 모의 회신'})
 state()
def get(cid):return call('/api/cases/'+cid)
def create(title,payment_date,deadline='2026-07-03'):
 case={'title':title,'sku_id':'SKU-1001','as_of':'2026-07-01','start':'2026-07-20','end':'2026-07-26','quantity':1000,'demand_status':'가정','evidence':'시연 가정. 실제 수요확약 아님.','approval_type':'재고발주','requested_amount':1000000,'requested_payment_date':payment_date,'contract_deadline':deadline}
 cid=call('/api/cases',{'role':'마케팅','case':case})['id'];state();return cid,case
def action(cid,a,role='SCM',expected=200,**kwargs):
 c=get(cid)['case'];r=call('/api/action',{'role':role,'id':cid,'version':c['version'],'action':a,**kwargs},expected);state();return r
def assess(cid,payment):
 c=get(cid)['case']
 call('/api/assessment',{'role':'재무','id':cid,'version':c['version'],'assessment':{'payment_date':payment,'amount':1000000,'change':'추가발주','decision_maker':'재무 시연 담당자','reason':'원본 발주와 별도인 증가 유출분 확인','evidence':'가상 신규 발주 지급 협의 회신','opinion':'기존 현금 하회 위험과 증가 유출분 검토','alternatives':'지급일 분할 협의 또는 발주 감량. 확정 전 자동 집행 금지'}});state()
def prepare(cid,payment):
 action(cid,'request',note='마케팅·SCM·재무 협조 요청')
 action(cid,'reply','마케팅',reply={'result':'확인','message':'추가 1000개는 참가자 가정, 일정 조정 가능'})
 action(cid,'reply',reply={'result':'확인','message':'모의 공급 확인. 실제 공급 확약 아님.','po_id':'SPO-0001','qty':24000,'available_date':'2026-07-15','confirmed':True})
 assess(cid,payment)
def finish(cid,scope):
 action(cid,'submit',note='부서 근거·재무 의견 첨부 상신')
 action(cid,'approve','승인권자',scope=scope,note='모의 사람 승인. 공급·현금 제약 검토. 실제 집행 아님.')
 action(cid,'order',note='승인된 범위 모의 발주 전달')
 action(cid,'reply',reply={'result':'확인','message':'발주 전달 후 모의 공급자 회신','po_id':'SPO-0001','qty':24000,'available_date':'2026-07-15','confirmed':True})
 action(cid,'complete',note='일정표·회신 기록 완료. 실제 입고·판매 완료 아님.')
def capture(name,inputs,cids,observations):
 state();report['scenarios'].append({'name':name,'input':inputs,'observations':observations,'cases':[{'id':cid,'workflow_status':get(cid)['case']['status'],'routing':get(cid)['calculation']['routing'],'tasks':get(cid)['tasks']} for cid in cids],'history':[e for _,e in sorted(events.items()) if e['case_id'] in cids]})

# Use a fresh local test DB so original golden inputs are reproducible.
if state()['finance']['config'].get('overrides'):raise SystemExit('Fresh local test DB required: existing finance replies must not be overwritten.')
confirm('exclude_pay')
normal,inputs=create('최종 시연 1 · 하회구간 밖 발주','2026-09-21')
prepare(normal,'2026-09-21');assert get(normal)['calculation']['authority']=='SCM 전결'
finish(normal,'SCM 전결');assert get(normal)['case']['status']=='회신 기록 완료'
capture('정상',inputs,[normal],['하회구간 밖 → SCM 전결 → 사람 승인 → 모의 발주·회신 완료'])

expanded,inputs=create('최종 시연 2 · 더마 신규 발주','2026-07-21')
prepare(expanded,'2026-07-21');assert get(expanded)['calculation']['authority']=='CEO/이사회'
action(expanded,'submit',note='평시 SCM이나 현금 하회구간 신규 약정으로 CEO 상신')
action(expanded,'conditional','승인권자',scope='CEO/이사회',note='모의 조건부 승인: 지급조건 확인 후 재상신')
assert any(t['status']=='대기' and t['key']=='conditions' for t in get(expanded)['tasks'])
action(expanded,'order',expected=400,note='조건 미충족 실행 차단 검증')
action(expanded,'submit',note='조건 이행 근거를 사람이 확인하고 재상신')
action(expanded,'reject','승인권자',note='모의 반려: 추가 지급 협의 필요')
assert get(expanded)['case']['status']=='보완 필요'
assert any(t['key']=='rework' and t['status']=='대기' for t in get(expanded)['tasks'])
finish(expanded,'CEO/이사회')
capture('확장·부서영향',inputs,[expanded],['평시 SCM → CEO 상신','재무 의견 첨부','조건부 승인 → 조건 작업 생성·발주 차단','반려 → 보완 작업 생성','사람 재승인 후 모의 발주·회신 완료'])

changed,inputs=create('최종 시연 3A · 변경되는 결재선','2026-08-25')
retained,_=create('최종 시연 3B · 유지되는 결재선','2026-07-21')
prepare(changed,'2026-08-25');prepare(retained,'2026-07-21')
action(changed,'submit',note='재무 변경 전 CEO 승인 대기')
action(retained,'submit',note='재무 변경 전 CEO 승인 대기')
before={cid:get(cid)['calculation']['routing'] for cid in [changed,retained]}
assert before[changed]['authority']=='CEO/이사회'
assert before[retained]['authority']=='CEO/이사회'
for r in state()['finance']['overdue']:
 if r['kind']=='ar':
  s=state();call('/api/finance',{'role':'재무','version':s['finance_version'],'operation':'overdue_reply','record_id':r['id'],'date':'2026-07-01','provenance':'모의 회신','decision_maker':'재무 시연 담당자','reason':'연체채권 회수 확인 모의 회신','evidence':r['record_id']+' 전액 7/1 회수 가정 확인'});state()
confirm('collect_pay')
assert get(changed)['calculation']['authority']=='SCM 전결'
assert get(retained)['calculation']['authority']=='CEO/이사회'
capture('변경',inputs,[changed,retained],{'before':before,'after':{cid:get(cid)['calculation']['routing'] for cid in [changed,retained]},'note':'6건 회수 확인 → 공식 시나리오 변경 → 8/25 경로 변경, 7/21 경로 유지'})

missing,inputs=create('최종 시연 4 · 지급일 미확인',None)
assert get(missing)['calculation']['routing']['status']=='판정 불가'
assert any(t['key']=='payment' and t['status']=='대기' for t in get(missing)['tasks'])
action(missing,'submit',expected=400,note='지급일 누락 승인 차단')
assess(missing,'2026-07-21')
assert get(missing)['calculation']['authority']=='CEO/이사회'
assert not any(t['key']=='payment' and t['status']=='대기' for t in get(missing)['tasks'])
capture('정보 부족',inputs,[missing],['지급일 없음 → 판정 불가·확인 작업','상신 차단','재무 회신 입력 → CEO 재판정·지급일 작업 완료'])

state();report['finance_history']=[e for _,e in sorted(events.items()) if e['case_id'] is None]
report['result']='4개 시나리오 통과'
Path('docs/verification/system/SCENARIO_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(report['result'])
