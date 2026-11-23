"""Disposable PostgreSQL integration evidence for W01/A01 upgrade."""
import copy,json,os,urllib.request,urllib.error,uuid
from pathlib import Path
from urllib.parse import urlparse
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8088')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost','::1']:raise SystemExit('Local only')
def call(path,body=None,status=200):
 req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=45) as r:code=r.status;d=json.load(r)
 except urllib.error.HTTPError as e:code=e.code;d=json.load(e)
 assert code==status,(path,code,d,status)
 return d

def get(cid):return call('/api/cases/'+cid)
def meta(role='SCM'):return {'decision_maker':role+' 확장 검증','reason':'원본 수요·공유 재고·약정 조건 검토','evidence':'격리 DB 모의 회신 · 출처는 각 계산 패킷'}
def ops(cid,operation,role='SCM',status=200,**payload):return call('/api/operations',{'id':cid,'version':get(cid)['case']['version'],'role':role,'mutation_id':str(uuid.uuid4()),'operation':operation,**meta(role),**payload},status)
def action(cid,operation,role='승인권자',status=200,**payload):return call('/api/execution',{'id':cid,'version':get(cid)['case']['version'],'role':role,'mutation_id':str(uuid.uuid4()),'operation':operation,**meta(role),**payload},status)
def create(name,qty=5000,sid='SKU-2002',budget=5000000,settle='2026-09-21',missing=False,inf=''):
 line=next(s['sku_name'].split()[0] for s in call('/api/state')['datasets']['sku']['rows'] if s['sku_id']==sid)
 p={'title':name,'author':'마케팅 확장 검증','department':'마케팅','campaign_name':name,'purpose':'현업 목표·제약을 통합한 운영 검증','target':line,'country':'국내','sales_channel':'자사몰','sns_channel':'YouTube','sns_format':'숏츠','influencer_id':inf,'media':['인플루언서'] if inf else ['퍼포먼스'],'as_of':'2026-07-01','written_date':'2026-07-01','start':'2026-07-13','end':'2026-07-19','budget':budget,'settlement_date':settle,'contract_deadline':'2026-07-10','performance_status':'미확인','performance_unknown_reason':'신규 시연 건 · 과거 성과 귀속 미확인','scope_skus':[sid],'scope_basis':'해당 SKU만 캠페인 대상으로 명시','items':[] if missing else [{'sku_id':sid,'demand':qty,'unit':'EA/기간','start':'2026-07-13','end':'2026-07-19','basis':'회사 규모 미래 순증 수량의 모의 부서 회신','confidence':'낮음','overlap':'기존 판매 제외한 순증'}]}
 cid=call('/api/marketing',{'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':p})['id'];return cid,p

def review(cid):
 d=get(cid);return ops(cid,'demand_review',basis=d['demand_validation']['basis'],override_reason='겹친 캠페인·참고 범위를 확인했고 별도 미래 물량 근거를 모의 회신으로 제시. 실제 개선 성과를 주장하지 않음.')
def handoff(cid,procure=False,pay='2026-08-21',adjust=False):
 d=get(cid);p=d['case']['marketing'];sku=p['items'][0]['sku_id'];m=next(s for s in call('/api/state')['datasets']['sku']['rows'] if s['sku_id']==sku);po=next(p for p in call('/api/state')['datasets']['purchase']['rows'] if p['sku_id']==sku);qty=int(m['moq']);unit=int(po['amount_krw'])/int(po['order_qty'])
 r={**meta(),'direction':'추가 발주 필요' if procure else '공급 불가' if adjust else '재고로 가능','alternatives':'기간·판매량·입고 일정 재검토' if adjust else '추가 대안 없음 · 조건 유지 검토','requests':[],'items':[{'sku_id':sku,'supply_result':'조정 필요' if adjust else '가능','procurement':'신규 발주 검토' if procure else '추가 조달 없음','target_qty':qty*2 if procure else None,'target_basis':'보충 목표 가정' if procure else '', 'requested_qty':qty if procure else None,'requested_unit_price':int(unit) if procure else None,'requested_payment_date':pay if procure else None,'planned_order_date':'2026-07-01' if procure else None,'proposed_available_date':'2026-07-14' if procure else None,'reference_po':po['po_id'],'note':'모의 발주 견적/지급일 확인' if procure else '추가 발주 없음'}]}
 call('/api/scm',{'role':'SCM','id':cid,'version':d['case']['version'],'operation':'handoff','mutation_id':str(uuid.uuid4()),'review':r});return r

def finance(cid,procure=False,pay='2026-08-21',opinion='승인'):
 d=get(cid);p=d['case']['marketing'];targets=[{'id':'campaign','kind':'캠페인집행','change':'신규 계약','cash_scope':'표본·현금 합산 제외','basis':'단독 기안 · 표본 요청액','proposal_total':p['budget'],'payments':[{'date':p['settlement_date'],'amount':p['budget']}]}]
 if procure:
  i=d['case']['scm']['review']['items'][0];targets.append({'id':'po-'+i['sku_id'],'sku_id':i['sku_id'],'kind':'재고발주','change':'추가발주','cash_scope':'전사 현금 반영 확인','basis':'모의 수량·단가·유출일 확인','payments':[{'date':pay,'amount':i['requested_qty']*i['requested_unit_price']}]})
 r={**meta('재무'),'opinion':opinion,'alternatives':'기간·수량·지급일 분할은 원 담당자 재검토','performance_basis':'원본 표본과 미래 실제 규모 가정을 구분','targets':targets,'requests':[]}
 call('/api/finance-review',{'role':'재무','id':cid,'version':d['case']['version'],'finance_version':call('/api/state')['finance_version'],'operation':'submit','review':r});return r

def approve(cid,status=200):
 for t in get(cid)['execution']['targets']:action(cid,'decide',status=status,authority=t['authority'],decisions=[{'id':t['id'],'decision':'승인'}])
def supply(cid,date):
 d=get(cid);rec={'po_id':'SPO-0006','status':'확인','qty':16000,'available_date':date,**meta(),'provenance':'모의 회신'}
 call('/api/scm',{'role':'SCM','id':cid,'version':d['case']['version'],'operation':'receipt','mutation_id':str(uuid.uuid4()),'receipt':rec})
def agree(cid):
 alts=[{'title':'검토안의 수량·기간·확인 입고 조건으로 진행','marketing_effect':'공유 재고에 맞춰 순증 판매량 조정','scm_effect':'기존 약속 유지·품절 방지','finance_effect':'현금 제약과 실제 승인권한 유지'}]
 ops(cid,'consult_open',subject='수요 감량과 공급·현금 조건 협의',alternatives=alts)
 ops(cid,'consult_reply',position='동의',alternative_id='0');ops(cid,'consult_resolve',status=400)
 ops(cid,'consult_reply','재무',position='동의',alternative_id='0');ops(cid,'consult_resolve')
def main():
 st=call('/api/state')
 if st['datasets']['portfolio']['rows']:raise SystemExit('이 시연은 비어 있는 별도 PostgreSQL DB가 필요합니다. 기존 검토 건을 삭제하거나 덮어쓰지 않습니다.')
 call('/api/finance',{'role':'재무','operation':'confirm','version':st['finance_version'],'selected':'exclude_pay','weekend_shift':False,'review_date':'2026-07-01','next_review_date':'2026-07-08',**meta('재무')})
 result=[]
 A,pA=create('통합 A · 기존 수요 5000');review(A);handoff(A);finance(A);approve(A);a0=get(A);assert a0['case']['execution']['reservation']['status']=='active'
 B,pB=create('통합 B · 동일 재고 추가 5000');review(B);handoff(B,adjust=True);finance(B,opinion='보류');approve(B,400);b0=get(B);assert b0['portfolio']['items'][0]['campaign_min']<0
 # Grounded proposal creates no approval; human acceptance creates a real consultation.
 before_approval=copy.deepcopy(b0['case'].get('execution',{}).get('decisions'))
 call('/api/assistant',{'role':'SCM','id':B,'version':b0['case']['version'],'operation':'propose',**meta()});b1=get(B);proposal=b1['case']['assistant_proposals'][-1];assert b1['case'].get('execution',{}).get('decisions')==before_approval
 call('/api/assistant',{'role':'SCM','id':B,'version':b1['case']['version'],'operation':'accept','proposal_id':proposal['id'],'action_id':'consult',**meta()});assert get(B)['consultation']['required']
 pB['items'][0]['demand']=2000;ops(B,'update_demand','마케팅',scope_skus=pB['scope_skus'],items=pB['items']);review(B);handoff(B);finance(B);agree(B);approve(B)
 assert get(B)['case']['execution']['reservation']['items'][0]['total_quantity']==2000
 result.append({'case':'정상·다중 기안 충돌·부서 합의','ids':[A,B],'blocked_min':b0['portfolio']['items'][0]['campaign_min'],'after_adjustment':get(B)['portfolio']['items'][0]['campaign_min'],'ai_mode':proposal['mode'],'ai_human_accepted':get(B)['case']['assistant_proposals'][-1]['status']})
 C,pC=create('통합 C · 확인 입고 후 10000');supply(C,'2026-07-13');review(C);handoff(C);finance(C);approve(C);assert get(C)['portfolio']['items'][0]['campaign_min']>0
 supply(C,'2026-07-27');changed={i:get(i) for i in [A,B,C]};assert all(d['portfolio']['items'][0]['campaign_min']<0 for d in changed.values());assert all(d['case']['execution']['reservation']['status']=='active' for d in changed.values())
 pC['items'][0]['demand']=500;ops(C,'update_demand','마케팅',scope_skus=pC['scope_skus'],items=pC['items']);review(C);handoff(C);finance(C);agree(C);approve(C)
 assert get(C)['portfolio']['items'][0]['campaign_min']>0
 result.append({'case':'불리한 공급 지연·전체 재검토·판매량 감량','ids':[A,B,C],'after_delay_min':{i:d['portfolio']['items'][0]['campaign_min'] for i,d in changed.items()},'after_revision_min':get(C)['portfolio']['items'][0]['campaign_min'],'remaining_commitments':sum(r['reservation']['items'][0]['total_quantity'] for r in call('/api/state')['datasets']['portfolio']['rows'] if r.get('reservation') and r['reservation']['status']=='active')})
 # Refreshing unchanged A keeps its promise; closure does not end measurement duty.
 handoff(A);finance(A);approve(A);action(A,'confirm_supply','SCM',mode='stock_only');action(A,'close','마케팅',notified=True,start=pA['start'],end=pA['end'],budget=pA['budget'],sku_ids=['SKU-2002']);assert any(t['status']=='대기' and 'followup:performance' in t['id'] for t in get(A)['tasks'])
 E,pE=create('거절 · 기안 철회와 계약 통보 분리',qty=100,sid='SKU-3002',budget=1000000,inf='INF-001');review(E);handoff(E);finance(E);t=get(E)['execution']['targets'][0];action(E,'decide',authority=t['authority'],decisions=[{'id':t['id'],'decision':'반려'}]);action(E,'withdraw','마케팅',notified=True);assert get(E)['execution']['withdrawn'];assert any('finance:contract:INF-001' in t['id'] and t['status']=='대기' for t in get(E)['tasks'])
 result.append({'case':'승인 거절·통보·철회·별도 의무 유지','ids':[E]})
 F,pF=create('정보 부족 · 수요 미입력',missing=True,sid='SKU-1001');f0=get(F);assert f0['demand_validation']['items'][0]['missing'];ops(F,'demand_review',basis=f0['demand_validation']['basis'],override_reason='미입력을 무시',status=400)
 item={'sku_id':'SKU-1001','demand':0,'unit':'EA/기간','start':pF['start'],'end':pF['end'],'basis':'미입력과 구분한 명시적 순증 없음 모의 회신','confidence':'낮음','overlap':'기존 판매 제외한 순증'};ops(F,'update_demand','마케팅',scope_skus=['SKU-1001'],items=[item]);review(F);assert get(F)['demand_validation']['ready']
 result.append({'case':'정보 부족 → 작업 → 명시적 0 가정 회신','ids':[F],'before_unknown':True,'after_review_ready':True})
 D,pD=create('필수 확장 · 공식/일별 재전망·CEO·발주',qty=1000,sid='SKU-3001',budget=15000000,settle='2026-07-27');review(D);handoff(D,procure=True);finance(D,procure=True);comp=get(D)['forecast_comparison'];assert comp['official_min']==5468884369;assert any(r['changed'] and r['official_counterfactual_authority']=='Masil 대표 승인 + 그룹 보고' and r['reforecast_authority']=='CEO/이사회' for r in comp['rows']);approve(D)
 i=get(D)['case']['scm']['review']['items'][0];action(D,'order','SCM',lines=[{'target_id':'po-SKU-3001','qty':i['requested_qty'],'order_date':'2026-07-01','payment_date':'2026-08-21','wanted_date':'2026-07-14','reply_deadline':'2026-07-06','channel':'이메일 모의'}]);o=get(D)['execution']['orders'][0]
 action(D,'receipt','SCM',lines=[{'po_id':o['po_id'],'payment_date':'2026-08-21','shipments':[{'available_date':'2026-07-14','qty':o['order_qty']}]}],message='분할/기간/지급일 확인 · 모의 회신',judgment='기간 공급 검토')
 assert get(D)['execution']['finance_valid'];action(D,'close','마케팅',notified=True,start=pD['start'],end=pD['end'],budget=pD['budget'],sku_ids=['SKU-3001'])
 ops(D,'followup',kind='physical_receipt',po_id=o['po_id'],received_qty=o['order_qty']//2,actual_date='2026-07-14');assert not get(D)['case']['operations']['followups']['physical_receipt:'+o['po_id']]['complete']
 ops(D,'followup',kind='physical_receipt',po_id=o['po_id'],received_qty=o['order_qty'],actual_date='2026-07-15');ops(D,'followup','마케팅',kind='performance',status=400)
 result.append({'case':'필수 확장 실제 결재 반영·후속 입고 확인','ids':[D],'comparison':comp,'physical_receipt_complete':True,'future_performance_blocked':True})
 # Full history remains available on refresh; exact dwell transitions are persisted.
 dash=call('/api/operations');assert dash['dwell']['completed'];assert any(t['id']=='global:followup:weekly_cash' for t in dash['queue']['tasks'])
 state=call('/api/state');ids=[A,B,C,D,E,F];history={i:get(i)['history'] for i in ids};assert all(history[i] for i in ids)
 data=state['datasets'];assert sum(r['amount'] for r in __import__('app.portfolio',fromlist=['cash_orders']).cash_orders(data))==o['amount_krw']
 for row in result:row['states']={i:{'version':get(i)['case']['version'],'status':get(i)['execution']['status'],'stage':get(i)['execution']['stage']} for i in row['ids']}
 report={'passed':True,'base':BASE,'mode':'격리 PostgreSQL · 실제 DB 처리 / 승인·발주·회신은 모의','scenarios':result,'ids':{'A':A,'B':B,'C':C,'D':D,'E':E,'F':F},'dwell':dash['dwell'],'history':history,'queue':dash['queue']}
 Path('docs/verification/system/UPGRADE_SCENARIOS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':True,'ids':report['ids']},ensure_ascii=False))
if __name__=='__main__':main()
