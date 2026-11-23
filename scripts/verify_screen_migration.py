"""Local-only transactional tests for the migrated role workflows."""
import json,os,uuid,urllib.request,urllib.error
from urllib.parse import urlparse
from pathlib import Path
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8087')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost','::1']:raise SystemExit('Local isolated DB only')
def call(path,body=None,expected=200):
 req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:status=r.status;d=json.load(r)
 except urllib.error.HTTPError as e:status=e.code;d=json.load(e)
 assert status==expected,(path,status,d,expected)
 return d

def get(cid):return call('/api/cases/'+cid)
def command(cid,operation,role='SCM',expected=200,**kw):
 return call('/api/execution',{'id':cid,'version':get(cid)['case']['version'],'role':role,'operation':operation,'mutation_id':str(uuid.uuid4()),'decision_maker':role+' 검증 담당','reason':'역할 흐름 검증','evidence':'격리 DB 모의 회신',**kw},expected)
def create(name,podate='2026-09-21'):
 p={'title':name,'campaign_name':name,'author':'기안자','department':'마케팅','position':'매니저','purpose':'현업 흐름 검증','country':'국내','target':'기초','media':['퍼포먼스'],'sns_channel':'YouTube','sns_format':'숏츠','sales_channel':'자사몰','as_of':'2026-07-01','written_date':'2026-07-01','start':'2026-07-13','end':'2026-07-19','budget':5000000,'expected_gmv':None,'settlement_date':'2026-09-21','contract_deadline':'2026-07-10','performance_status':'미확인','performance_unknown_reason':'모의 신규 캠페인으로 실적 없음','items':[{'sku_id':'SKU-2002','demand':100,'unit':'EA/기간','start':'2026-07-13','end':'2026-07-19','basis':'모의 증가 수요','confidence':'낮음','overlap':'기존 판매 제외한 순증'}]}
 cid=call('/api/marketing',{'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':p})['id']
 r={'decision_maker':'SCM 검증','reason':'캠페인 공급과 재고 보충 분리 검토','evidence':'현재고·판매·MOQ 원본 대조','direction':'추가 발주 필요','alternatives':'캠페인 조정 가능','requests':[],'items':[{'sku_id':'SKU-2002','supply_result':'가능','procurement':'신규 발주 검토','target_qty':40000,'target_basis':'후속 기간 보충 가정','requested_qty':16000,'requested_unit_price':12600,'planned_order_date':'2026-07-01','requested_payment_date':podate,'proposed_available_date':'2026-07-14','note':'희망 입고일은 모의 단축 협의 가정'}]}
 call('/api/scm',{'role':'SCM','id':cid,'version':get(cid)['case']['version'],'operation':'handoff','mutation_id':str(uuid.uuid4()),'review':r})
 f={k:'모의 검토 근거' for k in ['decision_maker','reason','evidence','opinion','alternatives','performance_basis']};f.update(requests=[],targets=[{'id':'campaign','kind':'캠페인집행','change':'신규 계약','cash_scope':'표본·현금 합산 제외','proposal_total':5000000,'basis':'단독 기안·표본','payments':[{'date':'2026-09-21','amount':5000000}]},{'id':'po-SKU-2002','sku_id':'SKU-2002','kind':'재고발주','change':'추가발주','cash_scope':'전사 현금 반영 확인','basis':'모의 수량·단가·지급일 확인','payments':[{'date':podate,'amount':201600000}]}])
 submit(cid,f);return cid,p,f

def submit(cid,f):return call('/api/finance-review',{'role':'재무','id':cid,'version':get(cid)['case']['version'],'finance_version':call('/api/state')['finance_version'],'operation':'submit','review':f})
def approve(cid):
 for t in get(cid)['execution']['targets']:
  command(cid,'decide','승인권자',authority=t['authority'],decisions=[{'id':t['id'],'decision':'승인','condition':''}])
def order(cid,date='2026-09-21',expected=200):return command(cid,'order',expected=expected,lines=[{'target_id':'po-SKU-2002','qty':16000,'order_date':'2026-07-01','payment_date':date,'wanted_date':'2026-07-14','reply_deadline':'2026-07-06','channel':'이메일 모의'}])
def receipt(cid,date='2026-09-21'):
 o=get(cid)['execution']['orders'][0]
 return command(cid,'receipt',lines=[{'po_id':o['po_id'],'payment_date':date,'shipments':[{'available_date':'2026-07-14','qty':8000},{'available_date':'2026-07-16','qty':8000}]}],message='분할 회신 확인 · 기간 공급 가능',judgment='캠페인 유지 제안')
def main():
 s=call('/api/state');call('/api/finance',{'role':'재무','version':s['finance_version'],'operation':'confirm','selected':'exclude_pay','weekend_shift':False,'review_date':'2026-07-01','next_review_date':'2026-07-06','decision_maker':'재무 검증','reason':'격리 검증 기준','evidence':'원본 재전망 회귀값'})
 results=[]
 cid,p,f=create('마이그레이션 정상 흐름')
 order(cid,expected=400)
 approve(cid);order(cid)
 command(cid,'order',expected=400,lines=[])
 receipt(cid)
 command(cid,'close','마케팅',start=p['start'],end=p['end'],budget=p['budget'],sku_ids=['SKU-2002'],notified=True)
 assert get(cid)['execution']['closed'];results.append({'name':'정상·평시·분할 회신·회차 종료','case_id':cid})
 cid2,_,_=create('마이그레이션 CEO·조건부','2026-08-21')
 t=next(t for t in get(cid2)['execution']['targets'] if t['kind']=='재고발주');assert t['authority']=='CEO/이사회'
 command(cid2,'decide','마케팅',expected=400,authority='CEO/이사회',decisions=[{'id':t['id'],'decision':'승인'}])
 command(cid2,'decide','승인권자',expected=400,authority='SCM 전결',decisions=[{'id':t['id'],'decision':'승인'}])
 command(cid2,'decide','승인권자',authority='CEO/이사회',decisions=[{'id':t['id'],'decision':'조건부 승인','condition':'지급 협의 근거 보완'}])
 order(cid2,'2026-08-21',400)
 results.append({'name':'CEO 경로·조건부 발주 차단','case_id':cid2})
 cid3,p3,_=create('마이그레이션 반려·보류')
 t=get(cid3)['execution']['targets'][0]
 command(cid3,'decide','승인권자',authority=t['authority'],decisions=[{'id':t['id'],'decision':'반려'}])
 command(cid3,'rework','마케팅',expected=400,notified=False)
 command(cid3,'rework','마케팅',notified=True)
 assert get(cid3)['execution']['rework']
 command(cid3,'note','SCM',to_role='재무')
 p3['title']='반려 후 보완 기안'
 call('/api/marketing',{'role':'마케팅','operation':'submit','id':cid3,'version':get(cid3)['case']['version'],'plan':p3})
 revised=get(cid3);assert len(revised['execution']['notes'])==1;assert not revised['case']['scm']['review']['valid'];assert not revised['execution']['rework']
 results.append({'name':'반려·통보·재작성','case_id':cid3})
 cid4,_,f4=create('마이그레이션 회신 지급일 변경')
 approve(cid4);order(cid4);receipt(cid4,'2026-08-21')
 assert not get(cid4)['execution']['finance_valid'];assert not get(cid4)['execution']['receipt']['clear']
 command(cid4,'clear_receipt','재무',expected=400)
 f4['targets'][1]['payments'][0]['date']='2026-08-21';submit(cid4,f4);approve(cid4)
 command(cid4,'clear_receipt','재무')
 assert get(cid4)['execution']['receipt']['clear'];results.append({'name':'지급일 변경·재무 재판정·CEO 재승인','case_id':cid4})
 # Replaying a successful command cannot duplicate a task/event or mutate twice.
 version=get(cid4)['case']['version'];key=str(uuid.uuid4())
 note={'id':cid4,'version':version,'role':'SCM','operation':'note','mutation_id':key,'decision_maker':'SCM 검증','reason':'재무 확인 요청','evidence':'모의 문의 기록','to_role':'재무'}
 call('/api/execution',note);after=get(cid4)['case']['version']
 assert call('/api/execution',note)['replayed'];assert get(cid4)['case']['version']==after
 call('/api/execution',{**note,'reason':'키 재사용 내용 변경'},400)
 call('/api/execution',{**note,'mutation_id':str(uuid.uuid4())},409)
 command(cid4,'answer','재무',index=0)
 # Read-only page/API visits must not create a mutation.
 d=get(cid4);version=d['case']['version'];get(cid4);assert get(cid4)['case']['version']==version
 for r in results:
  d=get(r['case_id']);r['projection']=d['execution'];r['history']=[{'role':e['role'],'event':e['event'],'at':e['at']} for e in d['history']]
 out={'base_url':BASE,'passed':True,'scope':'별도 로컬 PostgreSQL · 모든 전달/회신/승인은 모의','scenarios':results}
 Path('docs/verification/screen-reviews/13-screen-scenarios.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'passed':True,'cases':[r['case_id'] for r in results]},ensure_ascii=False))
if __name__=='__main__':main()
