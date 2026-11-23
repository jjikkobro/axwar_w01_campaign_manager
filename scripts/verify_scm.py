"""Run SCM scenarios only on a dedicated local test DB/server; creates mock records."""
import copy,json,os,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8085')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost'] or urlparse(BASE).scheme!='http':raise SystemExit('Local test server only')

def call(path,body=None,status=200):
 req=Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 try:
  with urlopen(req,timeout=30) as r:code=r.status;data=json.load(r)
 except HTTPError as e:code=e.code;data=json.load(e)
 assert code==status,(path,code,data)
 return data

def get(cid):return call('/api/cases/'+cid)
def create(qty=1000):
 p={'title':'② SCM 통합검증 '+str(uuid.uuid4())[:8],'author':'마케팅 시연','department':'마케팅','purpose':'원본·시안 대조 시연','as_of':'2026-07-01','written_date':'2026-07-01','start':'2026-07-13','end':'2026-07-19','performance_unknown_reason':'성과 비용 범위 별도 확인','items':[{'sku_id':'SKU-2002','demand':qty,'unit':'EA/기간','start':'2026-07-13','end':'2026-07-19','basis':'검증용 가상 수요','confidence':'미확인','overlap':'기존 판매 제외한 순증'}]}
 cid=call('/api/marketing',{'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':p})['id'];return cid,p

def review(procurement='추가 조달 없음'):
 return {'decision_maker':'SCM 시연 담당','reason':'기간별 공급·보충 분리 검토','evidence':'원본 자료와 모의 회신','alternatives':'일정·수량 조정 협의','direction':'재고로 가능','items':[{'sku_id':'SKU-2002','supply_result':'가능','procurement':procurement,'target_qty':None,'target_basis':'','requested_qty':None,'reference_po':'SPO-0006'}],'requests':[]}

def post(cid,op,**payload):
 return {'role':'SCM','id':cid,'version':get(cid)['case']['version'],'operation':op,'mutation_id':str(uuid.uuid4()),**payload}

def upload_purchase(data,label):
 current=call('/api/state')['datasets']['purchase'];cols=list(data['rows'][0]);csv='|'.join(cols)+'\n'+'\n'.join('|'.join(str(r[k]) for k in cols) for r in data['rows'])
 call('/api/datasets',{'role':'SCM','kind':'purchase','version':current['version'],'csv':csv,'source':label,'provenance':data.get('provenance','원본 사실'),'reason':'SCM 격리 테스트의 자체 변경 복원'})

def main():
 current=call('/api/state')['datasets']['purchase']
 if current['source']=='격리 검증용 발주 변경':upload_purchase(json.loads(Path('data/seed.json').read_text())['purchase'],'SCM 검증 복원 원본 스냅샷')
 results=[];cid,p=create();r=review()
 before=get(cid);v=before['case']['version'];preview=call('/api/scm/preview',{'role':'SCM','id':cid,'version':v,'review':r})
 assert get(cid)['case']['version']==v
 assert preview['calculation']['items'][0]['campaign_end_stock']==6659
 command=post(cid,'save',review=r);call('/api/scm',command);s=get(cid)
 assert s['case']['marketing_stage']=='SCM 검토 요청'
 assert call('/api/scm',command)['replayed'];assert get(cid)['case']['version']==s['case']['version']
 call('/api/scm',{**command,'mutation_id':str(uuid.uuid4())},409)
 bad=copy.deepcopy(command);bad['review']['reason']='내용 다름';call('/api/scm',bad,400)
 call('/api/scm',{**post(cid,'save',review=r),'role':'마케팅'},400)
 call('/api/scm',post(cid,'handoff',review=r));normal=get(cid)
 assert normal['case']['marketing_stage']=='재무 검토 요청';assert normal['case']['approval'] is None
 assert normal['case']['scm']['finance_packet']['approval'] is None
 assert any(t['role']=='재무' and t['status']=='대기' for t in normal['tasks'] if t['case_id']==cid)
 results.append({'name':'정상','case_id':cid,'input':r,'after':normal['case']['marketing_stage'],'approval':None})
 # Draft procurement is separate from actual cash and supply.
 cid2,_=create();r2=review('신규 발주 검토');r2['direction']='추가 발주 필요';r2['items'][0].update(target_qty=22000,target_basis='모의 목표 재고',planned_order_date='2026-07-01')
 call('/api/scm',post(cid2,'handoff',review=r2));new=get(cid2);x=new['scm_calculation']['items'][0]
 assert x['procurement']['raw_suggested_qty']==1529 and x['procurement']['moq_qty']==16000
 assert x['procurement']['estimated_amount']==201600000
 assert x['procurement']['requested_payment_date'] is None
 assert sum(d['inflow'] for d in x['stock'])==0
 assert any('유출일' in t['title'] and t['status']=='대기' for t in new['tasks'] if t['case_id']==cid2)
 assert new['calculation']['cash_min']==normal['calculation']['cash_min']
 results.append({'name':'추가 조달·정보 부족','case_id':cid2,'input':r2,'proposal':x['procurement'],'after':new['case']['marketing_stage'],'cash_unchanged':True})
 # Critical supplier confirmation: unknown must neither close the request nor add supply.
 cid3,p3=create(20000);r3=review();r3['direction']='추가 확인 대기';r3['items'][0]['supply_result']='미확인';r3['requests']=[{'id':'supplier-check','po_id':'SPO-0006','role':'SCM','question':'잔여량·판매가능일 확인','blocking':True,'status':'대기','answer':'','evidence':''}]
 call('/api/scm',post(cid3,'save',review=r3))
 rec={'po_id':'SPO-0006','status':'미확인','qty':16000,'available_date':'2026-07-13','decision_maker':'SCM 시연','reason':'아직 확인되지 않음','evidence':'모의 미확인 회신','provenance':'모의 회신'}
 call('/api/scm',post(cid3,'receipt',receipt=rec));unknown=get(cid3)
 assert unknown['case']['scm']['review']['requests'][0]['status']=='대기'
 assert sum(d['inflow'] for d in unknown['scm_calculation']['items'][0]['stock'])==0
 attempt=copy.deepcopy(r3);attempt['direction']='재고로 가능';attempt['items'][0]['supply_result']='가능';call('/api/scm',post(cid3,'handoff',review=attempt),400)
 rec.update(status='확인',reason='잔여 16000EA 판매가능일 모의 확인');call('/api/scm',post(cid3,'receipt',receipt=rec))
 confirmed=get(cid3)
 rec.update(status='미확인',reason='확인 일정 재검토 중');call('/api/scm',post(cid3,'receipt',receipt=rec))
 assert get(cid3)['case']['scm']['review']['requests'][0]['status']=='대기'
 rec.update(status='확인',reason='잔여 수량·판매가능일 재확인');call('/api/scm',post(cid3,'receipt',receipt=rec))
 confirmed=get(cid3);r3=confirmed['case']['scm']['review'];r3['direction']='재고로 가능';r3['items'][0]['supply_result']='가능'
 assert r3['requests'][0]['status']=='완료'
 assert sum(d['inflow'] for d in confirmed['scm_calculation']['items'][0]['stock'])==16000
 call('/api/scm',post(cid3,'handoff',review=r3));assert get(cid3)['case']['marketing_stage']=='재무 검토 요청'
 rec.update(status='불가',reason='공급자 일정 철회 모의 회신');call('/api/scm',post(cid3,'receipt',receipt=rec));changed=get(cid3)
 assert changed['case']['marketing_stage']=='SCM 재검토 필요'
 assert not changed['case']['scm']['review']['valid'];assert 'finance_packet' not in changed['case']['scm']
 assert any(t['status']=='종료(재검토)' for t in changed['tasks'] if t['case_id']==cid3 and t['role']=='재무')
 r3=changed['case']['scm']['review'];r3['direction']='공급 불가';r3['items'][0]['supply_result']='불가';r3['alternatives']='마케팅 수량·일정 보완 요청'
 call('/api/scm',post(cid3,'handoff',review=r3));negative=get(cid3)
 assert negative['case']['marketing_stage']=='재무 검토 요청' and negative['case']['approval'] is None
 results.append({'name':'미확인→확인→불가 회신·변경','case_id':cid3,'after_unknown':unknown['case']['marketing_stage'],'after_changed':changed['case']['marketing_stage'],'after_negative_opinion':negative['case']['marketing_stage'],'approval':None})
 # Plan revision preserves prior review and response but invalidates handoff.
 p3['items'][0]['demand']=21000
 call('/api/marketing',{'role':'마케팅','operation':'submit','id':cid3,'version':negative['case']['version'],'plan':p3})
 revised=get(cid3);assert not revised['case']['scm']['review']['valid'];assert revised['case']['scm']['receipts']['SPO-0006']['status']=='불가'
 results.append({'name':'기안 변경','case_id':cid3,'stage':revised['case']['marketing_stage'],'previous_review_preserved':True,'receipt_preserved':True})
 # Dataset updates invalidate SCM basis.
 s=call('/api/state');purchase=s['datasets']['purchase'];columns=list(purchase['rows'][0]);rows=copy.deepcopy(purchase['rows']);next(x for x in rows if x['po_id']=='SPO-0006')['amount_krw']='201600001'
 csv='|'.join(columns)+'\n'+'\n'.join('|'.join(str(row[k]) for k in columns) for row in rows)
 call('/api/datasets',{'role':'SCM','kind':'purchase','version':purchase['version'],'csv':csv,'source':'격리 검증용 발주 변경','provenance':'모의 회신','reason':'원본 파일은 보존한 DB 시나리오 변경'})
 revised2=get(cid2);assert revised2['case']['marketing_stage']=='SCM 재검토 필요';assert not revised2['case']['scm']['review']['valid']
 upload_purchase(purchase,'SCM 검증 복원 원본 스냅샷')
 events=call('/api/state')['events']
 assert any(e['event']=='SCM 검토 완료 · 재무 인계' for e in events)
 report={'base':BASE,'scope':'격리 로컬 PostgreSQL · 입력은 모의 시나리오','scenarios':results,'guards':['명시적 인계 전 단계 유지','중복 요청 재전송·다른 내용 재사용 차단','버전 충돌','타 부서 SCM 수정 차단','미확인 회신 공급 미반영·요청 미종료','확인 입고 단일 가산','미승인 신규 조달·예산 현금 미합산','유출일 미확인 재무 작업','공급 불가와 승인 반려 구분','회신·계획·발주 데이터 변경 시 인계 무효화'],'events':[e for e in events if e['case_id'] in [cid,cid2,cid3]]}
 Path('docs/verification/screen-reviews/02-scm-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('SCM PostgreSQL scenarios passed:',len(results))
if __name__=='__main__':main()
