"""SCM review and human handoff. Procurement proposals never become approved orders."""
import copy,hashlib,json
from pathlib import Path
from datetime import timedelta
from decimal import Decimal,ROUND_HALF_UP
from app.domain import calculate,day,number
from app.marketing import text
from app.formulas import run,token,context

KINDS=['기존 발주 확인','기존 발주 변경','신규 발주 검토','추가 조달 없음','판단 대기']
DIRECTIONS=['재고로 가능','정기 보충 확인 필요','추가 발주 필요','공급 불가','추가 확인 대기']
RESULTS=['가능','조정 필요','불가','미확인']
DATA_KINDS=['sku','inventory','sales','purchase']
SOURCE_ORDERS={p['po_id']:p for p in json.loads((Path(__file__).resolve().parent.parent/'data/seed.json').read_text())['purchase']['rows']}

def fingerprint(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def selected(case):return {i['sku_id'] for i in case['marketing']['items']}
def orders(case,data):return [p for p in data['purchase']['rows'] if p['sku_id'] in selected(case)]
def optional_number(v,label):return None if v in ('',None) else number(v,label)
def optional_date(v):
 if v in ('',None):return None
 day(v);return v

def receipt_replies(case,data):
 result=[];po={p['po_id']:p for p in orders(case,data)}
 for key,r in case.get('scm',{}).get('receipts',{}).items():
  if r['status']=='확인' and r.get('qty') is not None and r.get('available_date') and key in po and r.get('po_fingerprint')==fingerprint(po[key]):
   result.append({'role':'SCM','po_id':key,'result':'확인','confirmed':True,'qty':r['qty'],'available_date':r['available_date'],'message':r['evidence'],'provenance':r['provenance']})
 return result

def validate_receipt(raw,case,data):
 if not isinstance(raw,dict):raise ValueError('공급 회신 형식을 확인하세요.')
 po=next((p for p in orders(case,data) if p['po_id']==raw.get('po_id')),None)
 if not po:raise ValueError('현재 기안 SKU의 기존 발주를 연결하세요.')
 r={k:text(raw.get(k,''),label,True) for k,label in [('decision_maker','기록자'),('reason','기록 사유'),('evidence','회신 근거')]}
 r.update(po_id=po['po_id'],status=raw.get('status'),qty=optional_number(raw.get('qty'),'확인된 잔여 입고량'),receipt_date=optional_date(raw.get('receipt_date')),available_date=optional_date(raw.get('available_date')),provenance=raw.get('provenance','모의 회신'),po_fingerprint=fingerprint(po))
 if r['status'] not in ['확인','미확인','불가']:raise ValueError('회신은 확인·미확인·불가 중 선택하세요.')
 if r['provenance'] not in ['모의 회신','부서 주장']:raise ValueError('입력 회신은 모의 회신 또는 부서 주장으로 구분하세요.')
 if r['qty'] is not None and r['qty']>number(po['order_qty']):raise ValueError('확인 수량이 원본 발주 수량을 초과합니다.')
 if r['status']=='확인' and (r['qty'] is None or not r['available_date']):raise ValueError('확인 회신은 잔여 수량과 판매가능일이 필요합니다.')
 if r['available_date'] and day(r['available_date'])<day(case['as_of']):raise ValueError('기준일 이전 물량은 현재고에서 확인하세요.')
 if r['receipt_date'] and r['available_date'] and r['receipt_date']>r['available_date']:raise ValueError('판매가능일은 입고일보다 빠를 수 없습니다.')
 return r

def validate_review(raw,case,data,preview=False):
 if not isinstance(raw,dict):raise ValueError('SCM 검토 형식을 확인하세요.')
 r={k:text(raw.get(k,''),label,not preview and k!='reason') for k,label in [('decision_maker','SCM 담당자'),('reason','검토 사유'),('evidence','검토 근거')]}
 r['alternatives']=text(raw.get('alternatives',''),'조정 대안')
 r['direction']=raw.get('direction','추가 확인 대기')
 if r['direction'] not in DIRECTIONS:raise ValueError('SCM 처리 방향을 선택하세요.')
 items=raw.get('items',[])
 if not isinstance(items,list) or len(items)!=len(selected(case)):raise ValueError('기안의 모든 SKU를 제품별로 검토하세요.')
 seen=set();r['items']=[]
 for x in items:
  if not isinstance(x,dict) or x.get('sku_id') not in selected(case) or x['sku_id'] in seen:raise ValueError('중복 또는 기안에 없는 SKU입니다.')
  sid=x['sku_id'];seen.add(sid)
  item={'sku_id':sid,'supply_result':x.get('supply_result','미확인'),'procurement':x.get('procurement','판단 대기'),'target_qty':optional_number(x.get('target_qty'),'목표 수량'),'target_basis':text(x.get('target_basis',''),'목표 기준'),'requested_qty':optional_number(x.get('requested_qty'),'조달 요청 수량'),'requested_unit_price':optional_number(x.get('requested_unit_price'),'요청 단가'),'requested_payment_date':optional_date(x.get('requested_payment_date')),'planned_order_date':optional_date(x.get('planned_order_date')),'proposed_available_date':optional_date(x.get('proposed_available_date')),'note':text(x.get('note',''),'제품별 의견'),'reference_po':x.get('reference_po') or None}
  if item['supply_result'] not in RESULTS or item['procurement'] not in KINDS:raise ValueError('제품별 공급 판단·조달 유형을 선택하세요.')
  if item['target_qty'] is not None and not item['target_basis']:raise ValueError('목표 수량의 기간·산정 근거를 기록하세요.')
  if item['reference_po'] and not any(p['po_id']==item['reference_po'] and p['sku_id']==sid for p in orders(case,data)):raise ValueError('같은 SKU의 기존 발주를 연결하세요.')
  if item['procurement'] in ['기존 발주 확인','기존 발주 변경'] and not item['reference_po']:raise ValueError('기존 발주 확인·변경은 원본 PO가 필요합니다.')
  if item['planned_order_date'] and item['planned_order_date']<case['as_of']:raise ValueError('새 발주 가정일은 기준일 이후여야 합니다.')
  if item['proposed_available_date'] and item['proposed_available_date']<case['as_of']:raise ValueError('새 조달안의 판매가능일은 기준일 이후입니다.')
  if item['planned_order_date'] and item['proposed_available_date'] and item['proposed_available_date']<item['planned_order_date']:raise ValueError('새 조달안의 판매가능일은 발주 가정일보다 빠를 수 없습니다.')
  if item['procurement']=='신규 발주 검토' and item['requested_qty'] is not None:
   sku=next(p for p in data['sku']['rows'] if p['sku_id']==sid)
   if item['requested_qty'] and item['requested_qty']<number(sku['moq']):raise ValueError('신규 요청 수량은 원본 MOQ 이상이어야 합니다. 배수 규칙은 적용하지 않습니다.')
  r['items'].append(item)
 requests=raw.get('requests',[])
 if not isinstance(requests,list) or len(requests)>40:raise ValueError('확인 요청은 최대 40건입니다.')
 r['requests']=[];seen=set()
 for x in requests:
  if not isinstance(x,dict):raise ValueError('확인 요청 형식을 확인하세요.')
  key=text(x.get('id',''),'요청 식별자',True,100)
  if key in seen:raise ValueError('확인 요청 식별자가 중복되었습니다.')
  seen.add(key)
  q={'id':key,'role':x.get('role','SCM'),'question':text(x.get('question',''),'확인할 내용',True),'blocking':x.get('blocking',True),'status':x.get('status','대기'),'answer':text(x.get('answer',''),'확인 회신'),'evidence':text(x.get('evidence',''),'회신 근거'),'po_id':x.get('po_id') or None}
  if q['role'] not in ['마케팅','SCM'] or not isinstance(q['blocking'],bool) or q['status'] not in ['대기','완료']:raise ValueError('요청 담당자·차단 여부·상태를 확인하세요.')
  if q['po_id'] and not any(p['po_id']==q['po_id'] for p in orders(case,data)):raise ValueError('확인 요청의 PO가 현재 기안에 없습니다.')
  if q['status']=='완료':
   if not q['answer'] or not q['evidence']:raise ValueError('확인 요청 완료에는 회신 내용과 근거가 필요합니다.')
   if q['po_id']:
    receipt=case.get('scm',{}).get('receipts',{}).get(q['po_id'],{})
    if receipt.get('status') not in ['확인','불가'] or receipt.get('po_fingerprint')!=fingerprint(next(p for p in orders(case,data) if p['po_id']==q['po_id'])):raise ValueError('PO 확인 요청은 확인·불가 회신을 먼저 기록하세요. 미확인 회신으로 닫지 않습니다.')
  r['requests'].append(q)
 old=case.get('scm',{}).get('review',{})
 if old.get('basis',{}).get('plan')==fingerprint(case['marketing']):
  if any(q['status']=='대기' and q['id'] not in seen for q in old.get('requests',[])):raise ValueError('미응답 확인 요청을 삭제해 종료할 수 없습니다. 회신을 기록하세요.')
 return r

def analysis(case,data,finance=None,review=None,calculation=None):
 if not case.get('marketing'):return None
 data=context(data,finance or {})
 r=review if review is not None else case.get('scm',{}).get('review',{})
 calc=calculation or calculate(case,data,finance)
 plans={p['sku_id']:p for p in r.get('items',[])}
 # Carry the adopted marketing estimate rather than regenerate a different SCM order.
 from app.ax_planning import adopted
 adopted_plan=adopted(case,data,finance or {})
 if adopted_plan:
  if review is None and r.get('basis',{}).get('plan')!=fingerprint(case['marketing']):plans={}
  for x in adopted_plan['items']:
   if x['sku_id'] not in plans:plans[x['sku_id']]={'procurement':'신규 발주 검토' if x['chosen_qty'] else '추가 조달 없음','target_qty':None,'target_basis':'마케팅에서 채택한 예상 발주안','requested_qty':x['chosen_qty'],'requested_unit_price':x['chosen_unit_price'],'requested_payment_date':None,'planned_order_date':case['as_of'],'proposed_available_date':x['earliest_arrival_assumption'],'note':'마케팅 신청 예상안 · 미승인/입고 미확인'}
 result=[]
 for x in calc['items']:
  sid=x['sku']['sku_id'];p=plans.get(sid,{})
  stock=x['stock'];campaign=[d for d in stock if case['start']<=d['date']<=case['end']]
  before_end=[d for d in stock if d['date']<=case['end']]
  first=next((d['date'] for d in before_end if d['closing']<0),None)
  campaign_first=next((d['date'] for d in campaign if d['closing']<0),None);before_first=next((d['date'] for d in stock if d['date']<case['start'] and d['closing']<0),None)
  applicable=[o for o in orders(case,data) if o['sku_id']==sid]
  target=p.get('target_qty');transit=number(x['inventory']['in_transit_qty']);oh=number(x['inventory']['on_hand_qty']);moq=number(x['sku']['moq'])
  suggested=run(data,'procurement_gap',target=target,on_hand=oh,in_transit=transit) if target is not None else None
  final=run(data,'procurement_moq',gap=suggested,moq=moq) if suggested else suggested
  ref=next((o for o in applicable if o['po_id']==p.get('reference_po')),None)
  historical=Decimal(ref['amount_krw'])/Decimal(ref['order_qty']) if ref and number(ref['order_qty']) else None
  qty=p.get('requested_qty') if p.get('requested_qty') is not None else final
  price=Decimal(p['requested_unit_price']) if p.get('requested_unit_price') is not None else historical
  amount=run(data,'purchase_amount',qty=qty,unit_price=float(price)) if price is not None and qty is not None else None
  existing=[]
  for po in applicable:
   receipt=case.get('scm',{}).get('receipts',{}).get(po['po_id']);valid=bool(receipt and receipt.get('po_fingerprint')==fingerprint(po))
   existing.append({'source_record':SOURCE_ORDERS.get(po['po_id']),'original':po,'receipt':receipt,'receipt_current':valid,'applied':valid and receipt.get('status')=='확인','original_provenance':data['purchase'].get('provenance','원본 사실')})
  complete=len(x['weeks'])==4 and x['weekly']>0 and day(x['inventory']['snapshot_date'])+timedelta(days=1)==day(case['as_of'])
  result.append({'sku_id':sid,'sku':x['sku'],'inventory':x['inventory'],'weeks':x['weeks'],'weekly':x['weekly'],'cover':x['cover'],'simple_cover':x['simple_cover'],'demand':x['demand'],'stock':stock,'campaign_min':min(d['closing'] for d in campaign),'campaign_end_stock':campaign[-1]['closing'],'first_short_through_campaign':first,'first_short_in_campaign':campaign_first,'first_short_before_campaign':before_first,'first_short_horizon':x['first_short'],'model_status':'기간 내 음수 재고 없음 · 가정 기준' if complete and not campaign_first else '기간 내 공급 부족' if complete else '자료 확인 필요','data_complete':complete,'existing_orders':existing,'procurement':{'kind':p.get('procurement','판단 대기'),'target_qty':target,'target_basis':p.get('target_basis',''),'raw_suggested_qty':suggested,'moq_qty':final,'requested_qty':p.get('requested_qty'),'effective_proposal_qty':qty,'requested_unit_price':float(price) if price is not None else None,'historical_unit_price':float(historical) if historical is not None else None,'estimated_amount':amount,'requested_payment_date':p.get('requested_payment_date'),'planned_order_date':p.get('planned_order_date'),'lead_time_arrival_assumption':__import__('app.planning',fromlist=['lead_date']).lead_date(data,p['planned_order_date'],x['sku']['lead_time_weeks']) if p.get('planned_order_date') else None,'proposed_available_date':p.get('proposed_available_date'),'provenance':'참가자 가정 + 계산 결과','approved':False},'warnings':x['warnings'],'sources':x['evidence_sources']})
 from app.scm_advice import recommend
 from app.replenishment import plan as replenishment_plan
 replenishment=replenishment_plan(case,data)
 advice=recommend(case,data,result,replenishment)
 from app.planning import snapshot
 shared=snapshot(data,case,regular=replenishment)
 return {'planning':shared,'replenishment':replenishment,'adopted_estimate_revalidated':bool(adopted_plan),'recommendation':advice,'items':result,'scope':'현재고·확인 공급·다른 승인 캠페인 수요를 합산한 기간 검산','valid':bool(r.get('valid')),'direction':r.get('direction','추가 확인 대기'),'assumptions':['통합 원장의 확인 공급·다른 승인 캠페인 수요를 반영하며 미래 예상안은 별도 조건부로 검산.','기존 판매·추가 수요를 일별 균등 배분. 라이브 피크 보장 아님.','원본 커버에는 운송 중 미합산; 원본 발주량에서는 운송 중 차감.','판매가능일이 확인된 기존 PO 회신만 날짜별 반영. 운송 중을 별도로 더하지 않음.','미승인 신규 조달안·그 입고 가정은 현재 공급량에 합산하지 않음.','MOQ는 최소량이며 배수 주문을 강제하지 않음.','적정 목표 수량·기간은 담당자 가정이며 자동 확정하지 않음.']}

def can_handoff(review,calc):
 if not calc['items']:raise ValueError('기안의 SKU·수요 가정이 없습니다. 마케팅에 보완 요청하고 확인한 뒤 인계하세요.')
 if review['direction']=='추가 확인 대기':raise ValueError('추가 확인 대기는 ②에 남습니다. 검토 결과를 정한 뒤 인계하세요.')
 regular_possible=calc.get('recommendation',{}).get('kind')=='procurement' and not calc['recommendation'].get('campaign_extra_required') and calc.get('replenishment',{}).get('feasible') and not any(i['procurement'] in ['신규 발주 검토','기존 발주 변경'] for i in review['items'])
 if review['direction']=='재고로 가능' and regular_possible and not review.get('reason','').strip():raise ValueError('정기 보충을 반영한 공급 판단의 사유를 기록하세요.')
 if any(q['status']=='대기' and q['blocking'] for q in review['requests']):raise ValueError('중요 확인 요청의 회신을 먼저 확보하세요.')
 for line in review['items']:
  x=next(x for x in calc['items'] if x['sku_id']==line['sku_id'])
  if line['procurement']=='신규 발주 검토' and (not line.get('requested_qty') or not line.get('requested_unit_price')):raise ValueError('신규 발주 요청의 제품별 수량과 예상 단가를 입력하세요.')
  if line['supply_result']=='미확인':raise ValueError('모든 SKU의 공급 검토 의견을 기록하세요.')
  if not x['data_complete']:raise ValueError('완료된 4주 수요 자료를 확인하세요.')
  if line['supply_result']=='가능' and x['first_short_in_campaign'] and not regular_possible:raise ValueError('기간 내 공급 부족이 있습니다. 확인 입고를 기록하거나 조정 필요·불가로 구분하세요.')
 if review['direction']=='재고로 가능' and any(x['supply_result']!='가능' for x in review['items']):raise ValueError('재고로 가능 방향은 모든 SKU의 가능 판단이 필요합니다.')
 if review['direction']=='정기 보충 확인 필요':
  if calc.get('recommendation',{}).get('kind')!='procurement' or calc['recommendation'].get('campaign_extra_required') or not calc.get('replenishment',{}).get('feasible'):raise ValueError('캠페인 추가 발주 없이 정기 보충 가정으로 공급 가능한지 먼저 확인하세요.')
  if any(x['procurement'] in ['신규 발주 검토','기존 발주 변경'] for x in review['items']):raise ValueError('캠페인 추가 발주안은 정기 보충과 구분하여 선택하세요.')
 if review['direction']=='공급 불가' and not review['alternatives']:raise ValueError('공급 불가 의견에는 마케팅 보완 후보·대안을 기록하세요.')
 if review['direction']=='추가 발주 필요' and not any(x['procurement'] in ['신규 발주 검토','기존 발주 변경'] for x in review['items']):
  raise ValueError('캠페인 추가 발주·기존 발주 변경 검토안을 함께 기록하세요. 정기 보충만 필요하면 재고로 가능을 선택하고 보충 근거를 기록하세요.')

def basis(case,data):
 from app.portfolio import context_basis
 return {'plan':fingerprint(case['marketing']),'datasets':{k:data[k].get('version') for k in DATA_KINDS},**({'portfolio':context_basis(case,data)} if 'portfolio' in data else {}),**({'formulas':token(data)} if token(data) else {})}
def invalidate(case,reason):
 if not case.get('scm'):return False
 review=case['scm'].get('review')
 if not review:return False
 was=bool(review.get('valid'));review['valid']=False;review['invalidation_reason']=reason
 case['scm'].pop('finance_packet',None)
 if case.get('marketing_stage')!='작성 중':case['marketing_stage']='SCM 재검토 필요'
 return was

def stale(case,data):
 r=case.get('scm',{}).get('review',{})
 return bool(r.get('valid') and r.get('basis')!=basis(case,data))

def task_specs(case):
 scm=case.get('scm',{});r=scm.get('review',{});out=[]
 if case.get('marketing_stage')=='작성 중':return out
 for q in r.get('requests',[]):
  if q['status']=='대기':out.append({'key':'scm:request:'+q['id'],'title':q['question'],'role':q['role'],'blocking':q['blocking'],'provenance':'내부 통제'})
 if case.get('marketing_stage')=='재무 검토 요청' and r.get('valid'):
  out.append({'key':'scm:finance','title':'SCM 검토 결과·조달안의 금액·신규 여부·권한 확인','role':'재무','provenance':'내부 통제'})
  for p in r['items']:
   if p['procurement']=='신규 발주 검토' and p.get('requested_qty') is None and p.get('target_qty') is None:out.append({'key':'scm:quantity:'+p['sku_id'],'title':p['sku_id']+' 조달 목표·수량 확인 · 미확정 초안','role':'SCM','provenance':'내부 통제'})
   if p['procurement'] in ['신규 발주 검토','기존 발주 변경'] and not p['requested_payment_date']:out.append({'key':'scm:payment:'+p['sku_id'],'title':p['sku_id']+' 조달안 유출일 확인 · 승인 판정 전 필수','role':'재무','provenance':'내부 통제'})
 elif r:
  for p in r.get('items',[]):
   if p['supply_result']=='미확인':out.append({'key':'scm:supply:'+p['sku_id'],'title':p['sku_id']+' 수요·공급 조건 확인','role':'SCM','provenance':'내부 통제'})
 return out

def packet(case,review,calc):
 return {'type':'SCM 검토 결과 인계 · 미승인','plan_reference':case['marketing'].get('reference_plan_id'),'plan':copy.deepcopy(case['marketing']),'scm_decision':copy.deepcopy(review),'supply_and_procurement':copy.deepcopy(calc),'approval':None,'note':'재무가 실제 유출일·금액·신규 여부·현금 구간을 확인할 자료. 발주·캠페인 집행 승인이 아님.','provenance':'부서 주장 / 참가자 가정 / 계산 결과 / 모의 회신을 항목별 구분'}

def handoff_demand(case,data,config,review,confirmation):
 """Human confirmation is atomic with handoff; never repairs missing demand as zero."""
 from app.demand import assess,require_ready
 a=assess(case,data)
 if a['ready']:return case,None
 if not isinstance(confirmation,dict) or confirmation.get('checked') is not True:raise ValueError('수요 근거 확인을 체크하세요. 수요 누락 여부와 참고 범위를 같은 인계 창에서 확인할 수 있습니다.')
 from app.operations import apply
 from app.execution import metadata
 raw={'operation':'demand_review','basis':confirmation.get('basis'),'override_reason':confirmation.get('override_reason',''),'decision_maker':review['decision_maker'],'reason':review.get('reason') or 'SCM 대조 결과 전달 시 SKU 수요와 과거 참고 범위 확인','evidence':review['evidence']}
 b,event=apply(case,data,config,raw,'SCM',metadata);require_ready(b,data)
 return b,event
