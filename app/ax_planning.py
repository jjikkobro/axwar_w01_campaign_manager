"""Grounded pre-submission decision support. Predictions are assumptions, never approvals."""
import copy,math
from datetime import date,timedelta
from app.domain import day,number
from app.demand import evidence,reference,quantile,signature
from app.formulas import run
from app.portfolio import simulate,context_basis,cash_context
from app.finance import cash_bundle,routing,MIN_CASH,next_business

MODEL='W01-AX-PREPLAN-3'
def optional(v,label):
 n=None if v in [None,''] else number(v,label)
 if n is not None and n>10**12:raise ValueError(label+' 입력 범위를 초과했습니다.')
 return n
def preview(raw,data,config,cid=None):
 if not isinstance(raw,dict):raise ValueError('사전검토 입력을 확인하세요.')
 from app.formulas import context
 data=context(data,config)
 estimate_only=raw.get('mode')=='estimate_only'
 finance_pending=[];scm_pending=[]
 asof=raw.get('as_of');start=raw.get('start');end=raw.get('end')
 if not day(asof)<=day(start)<=day(end) or (day(end)-day(asof)).days>180:raise ValueError('기준일·캠페인 기간(최대 180일)을 먼저 입력하세요.')
 requested=raw.get('items')
 if not isinstance(requested,list) or not 1<=len(requested)<=14:raise ValueError('제품을 1~14개 선택하세요.')
 ids=[r.get('sku_id') for r in requested if isinstance(r,dict)]
 if len(ids)!=len(requested) or any(not isinstance(x,str) for x in ids) or len(set(ids))!=len(ids) or not set(ids)<={s['sku_id'] for s in data['sku']['rows']}:raise ValueError('SKU 선택을 확인하세요.')
 budget=optional(raw.get('budget'),'캠페인 요청액');settle=None if estimate_only else raw.get('settlement_date') or None
 if settle:day(settle)
 total=optional(raw.get('group_total'),'소속 기안 총액') or budget
 inputs={'as_of':asof,'start':start,'end':end,'budget':budget,'settlement_date':settle,'group_total':total,'items':[]}
 if estimate_only:inputs['mode']='estimate_only'
 from app.marketing_cost import estimate as estimate_marketing
 marketing_cost=estimate_marketing(raw.get('marketing_cost_inputs'),data,asof,start,end)
 if marketing_cost['enabled']:inputs['marketing_cost_inputs']=marketing_cost['inputs']
 p={'as_of':asof,'start':start,'end':end,'scope_skus':ids,'items':[]};b={'_case_id':cid,'as_of':asof,'marketing':p};rows=[];issues=[]
 for r in requested:
  sid=r['sku_id'];ev=evidence(sid,data,asof);sku=next(s for s in data['sku']['rows'] if s['sku_id']==sid);inv=next(s for s in data['inventory']['rows'] if s['sku_id']==sid)
  if day(inv['snapshot_date'])>=day(asof):raise ValueError('재고 스냅샷 이후 기준일을 사용하세요.')
  forecast=math.ceil(max(0,quantile([o['increment'] for o in ev['observations']],.5))) if ev['observation_count']>=4 else None
  mode=r.get('demand_mode','unset');demand=optional(r.get('demand'),'주간 추가 수요')
  if mode not in ['forecast','manual','unset']:raise ValueError('수요 입력 방식을 확인하세요.')
  if mode=='forecast':demand=forecast
  if mode=='unset':demand=forecast;issues.append(sid+' 수요 가정 채택 필요')
  if demand is None:issues.append(sid+' 수요 근거 부족 · 직접 입력 필요')
  if ev['observation_count']<4:issues.append(sid+' 비교 관측 4건 미만')
  if not ev['recent_weeks'] or len(ev['recent_weeks'])<4 or (day(asof)-day(ev['recent_weeks'][-1]['week'])-timedelta(days=7)).days>14:issues.append(sid+' 최근 완료 판매 자료 부족/오래됨')
  if demand is not None and ev['range_low'] is not None and not ev['range_low']<=demand<=ev['range_high']:issues.append(sid+' 과거 증분 범위 밖 · 담당자 검토 필요')
  weekly=run(data,'weekly_average',sales_total=sum(x['sold_qty'] for x in ev['recent_weeks']),weeks_count=len(ev['recent_weeks'])) if ev['recent_weeks'] else None
  p['items'].append({'sku_id':sid,'demand':demand or 0,'unit':'EA/주','start':start,'end':end,'total_quantity':(demand or 0)*((day(end)-day(start)).days+1)/7,'basis':'기안 사전검토','overlap':'기존 판매 제외한 순증'})
  normalized={'sku_id':sid,'demand_mode':mode,'demand':demand,'qty_mode':r.get('qty_mode','unset'),'qty':optional(r.get('qty'),'발주 수량'),'price_mode':r.get('price_mode','unset'),'unit_price':optional(r.get('unit_price'),'단가'),'payment_date':None if estimate_only else r.get('payment_date') or None}
  if normalized['qty_mode'] not in ['forecast','manual','unset'] or normalized['price_mode'] not in ['forecast','manual','unset']:raise ValueError('발주 입력 방식을 확인하세요.')
  if normalized['payment_date']:day(normalized['payment_date'])
  inputs['items'].append(normalized)
  # Read only observations completed before the review date; no future sales.
  histories={(x['week'],x['sku_id']):x for x in reference()['sales']};histories.update({(x['week'],x['sku_id']):x for x in data['sales']['rows']})
  hist=sorted([x for x in histories.values() if x['sku_id']==sid and day(x['week'])+timedelta(days=7)<=day(asof)],key=lambda x:x['week'])
  predictions=[]
  for k in range(max(4,len(hist)-8),len(hist)):
   past=hist[k-4:k];pred=run(data,'weekly_average',sales_total=sum(int(x['sold_qty']) for x in past),weeks_count=4);predictions.append((pred,int(hist[k]['sold_qty'])))
  denom=sum(a for _,a in predictions);wape=sum(abs(f-a) for f,a in predictions)/denom if denom else None
  rows.append({'sku_id':sid,'name':sku['sku_name'],'forecast_weekly_extra':forecast,'chosen_weekly_extra':demand,'baseline_weekly':weekly,'reference_range':[ev['range_low'],ev['range_high']],'observations':ev['observation_count'],'confidence':'보통' if ev['observation_count']>=8 else '낮음','history':{'from':hist[0]['week'] if hist else None,'to':hist[-1]['week'] if hist else None,'completed_weeks':len(hist)},'backtest':{'weeks':len(predictions),'baseline_wape':wape,'note':'최근 8개 완료 주의 직전 4주 평균 기초 판매 검산. 캠페인 증분 예측 정확도 또는 성공 확률 아님.'},'evidence':ev,'inventory':int(inv['on_hand_qty']),'moq':int(sku['moq']),'lead_time_weeks':int(sku['lead_time_weeks'])})
 # Shared ledger counts confirmed supplies and other approved campaign promises once.
 ledger=simulate(data,b,end=end,sku_ids=ids)
 from app.replenishment import plan as replenishment_plan
 regular=replenishment_plan(b,data)
 regular_by={r['sku_id']:r for r in regular['items']}
 from app.planning import snapshot
 planning=snapshot(data,b,ledger,regular);planning_by={r['sku_id']:r for r in planning['items']}
 for row,r in zip(rows,inputs['items']):
  sid=row['sku_id'];sim=next(i for i in ledger['items'] if i['sku_id']==sid);sku=next(s for s in data['sku']['rows'] if s['sku_id']==sid)
  minimum=sim['campaign_min'] if row['chosen_weekly_extra'] is not None else None;target=run(data,'safety_target',weekly=row['baseline_weekly'] or 0,safety_weeks=int(sku['safety_stock_weeks_min']))
  normal=regular_by[sid];shared=planning_by[sid];use_regular=shared['use_regular']
  proposed=shared['recommended_qty']
  qty=r['qty'] if r['qty_mode']=='manual' else proposed
  if qty and qty<row['moq']:raise ValueError(sid+' 발주량이 원본 MOQ 미만입니다.')
  po=sorted([o for o in data['purchase']['rows'] if o['sku_id']==sid and o.get('order_date','')<=asof and int(o['order_qty'])>0],key=lambda o:o.get('order_date',''))
  historical_price=math.ceil(int(po[-1]['amount_krw'])/int(po[-1]['order_qty'])) if po else None
  price=r['unit_price'] if r['price_mode']=='manual' else historical_price
  amount=run(data,'purchase_amount',qty=qty,unit_price=price) if qty is not None and price is not None else None
  arrival=shared['earliest_arrival_assumption'];pay=r['payment_date']
  if qty:
   if r['qty_mode']=='unset':issues.append(sid+' 발주 수량 채택 필요')
   if r['price_mode']=='unset':issues.append(sid+' 과거 단가 가정 확인 필요')
   if price in [None,0]:issues.append(sid+' 발주 단가 확인 필요')
   if not pay:(finance_pending if estimate_only else issues).append(sid+(' 계획 지급일 재무 확인 필요' if estimate_only else ' 발주 지급일 확인 필요'))
   if pay and not '2026-07-01'<=pay<='2026-09-28':issues.append(sid+' 지급일이 현금 재전망 범위 밖')
   if amount is not None and amount!=qty*price:issues.append(sid+' 예상 금액이 수량×단가와 다름 · 재무 확인 필요')
  projected=[d['campaign_closing']+(qty or 0 if d['date']>=arrival else 0) for d in normal['days'] if start<=d['date']<=end] if use_regular else [d['closing']+(qty or 0 if d['date']>=arrival else 0) for d in sim['days'] if start<=d['date']<=end]
  if min(projected)<0:issues.append(sid+' 리드타임 반영 후에도 캠페인 공급 부족')
  if sim['campaign_min'] is not None and sim['campaign_min']<0:
   if use_regular:scm_pending.append(sid+' 정기 보충·미확인 입고 가정은 실제 공급이 아닙니다. SCM 상세 검토 필요')
   else:issues.append(sid+' 현재 확정 공급만으로 부족 · 공급자 확인 필요')
  if any((r.get('reservation') or {}).get('status')=='legacy_pending' for r in data.get('portfolio',{}).get('rows',[]) if r['case_id'] in sim['other_case_ids']):issues.append(sid+' 기존 승인 수요 약속 복원 확인 필요')
  if not sim['data_complete']:issues.append(sid+' 재고 기준일·판매 자료 확인 필요')
  row.update(regular_replenishment=normal if use_regular else None,regular_condition_required=use_regular,recommended_qty=proposed,chosen_qty=qty,unit_price_estimate=historical_price,chosen_unit_price=price,estimated_cost=amount,earliest_arrival_assumption=arrival,payment_date=pay,campaign_min_before=minimum,campaign_min_after_assumption=min(projected) if minimum is not None else None,safety_target=target,other_case_ids=sim['other_case_ids'],price_source=po[-1]['po_id'] if po else None,price_note='과거 발주 단가 참고 · 신규 공급 견적 아님',provenance='계산 결과 / 참가자 가정')
 # Inspect hypothetical cash impact without adding sample marketing budgets.
 bundle=cash_bundle(data,config);results={}
 for sid,s in bundle['scenarios'].items():
  out=0;days=[]
  for d in s['calendar']:
   out+=sum(r['estimated_cost'] or 0 for r in rows if r['chosen_qty'] and r['payment_date'] and (next_business(day(r['payment_date'])).isoformat() if config.get('weekend_shift') else r['payment_date'])==d['date'])
   if d['business_day']:days.append({'date':d['date'],'closing':d['closing']-out})
  results[sid]={'minimum':min(d['closing'] for d in days),'breach_dates':[d['date'] for d in days if d['closing']<MIN_CASH]}
 selected=[bundle['selected']] if bundle['confirmed'] else list(results);breach=set(d for k in selected for d in results[k]['breach_dates']);routes=[]
 for r in rows:
  if not r['chosen_qty']:continue
  fake={'approval_type':'재고발주','financial_assessment':{'change':'추가발주','amount':r['estimated_cost'],'payment_date':r['payment_date']}}
  route=routing(fake,bundle);effective=next_business(day(r['payment_date'])).isoformat() if r['payment_date'] and config.get('weekend_shift') else r['payment_date']
  if effective in breach:route.update(authority='CEO/이사회')
  routes.append({'sku_id':r['sku_id'],'authority':route['authority'],'blocked':route['blocked']})
 if budget is None:issues.append('캠페인 요청액 확인 필요')
 if budget is None or settle is None:(finance_pending if estimate_only else issues).append('캠페인 계획 정산일 재무 확인 필요')
 else:
  fake={'approval_type':'캠페인집행','proposal_total':total,'financial_assessment':{'change':'신규 계약','amount':budget,'payment_date':settle}}
  route=routing(fake,bundle);effective=next_business(day(settle)).isoformat() if config.get('weekend_shift') else settle
  if not route['blocked']:route.update(authority='CEO/이사회' if effective in breach else route.get('normal',route['authority']))
  routes.append({'sku_id':None,'authority':route['authority'],'blocked':route['blocked']})
 if not bundle['confirmed']:(finance_pending if estimate_only else issues).append('공식 재무 시나리오 확인 필요')
 if bundle['validation_errors']:issues+=bundle['validation_errors']
 if ledger['supply']['conflicts']:issues.append('동일 발주 공급 회신 불일치')
 if any(r['blocked'] for r in routes):(finance_pending if estimate_only else issues).append('결재선 판정에 필요한 정보 재무 확인')
 cash_complete=all(r['chosen_qty'] is not None and (not r['chosen_qty'] or (r['estimated_cost'] is not None and r['payment_date'] and '2026-07-01'<=r['payment_date']<='2026-09-28')) for r in rows)
 from app.planning_schedule import terms,calculate as schedule_calculate
 if not estimate_only and raw.get('schedule_terms') is not None:inputs['schedule_terms']=terms(raw['schedule_terms'])
 schedule=schedule_calculate(inputs,rows,inputs.get('schedule_terms'),data=data)
 schedule['marketing_budget']=marketing_cost.get('adopted_budget')
 schedule['adopted_total_requirement']=run(data,'campaign_total_requirement',marketing_budget=marketing_cost['adopted_budget'],procurement_budget=schedule['procurement_budget']) if marketing_cost.get('adopted_budget') is not None and schedule['procurement_budget'] is not None else None
 schedule['predicted_total_requirement']=run(data,'campaign_total_requirement',marketing_budget=marketing_cost['recommended_budget'],procurement_budget=schedule['procurement_budget']) if marketing_cost['recommended_budget'] is not None and schedule['procurement_budget'] is not None else None
 schedule['campaign_total_requirement']=run(data,'campaign_total_requirement',marketing_budget=budget,procurement_budget=schedule['procurement_budget']) if budget is not None and schedule['procurement_budget'] is not None else None
 source_versions={k:v.get('version') for k,v in data.items() if k!='portfolio'}
 key=signature({'model':MODEL,'history_sources':reference()['sources'],'marketing_sources':marketing_cost.get('sources',[]),'inputs':inputs,'datasets':source_versions,'config':config,'supply':context_basis(b,data),'cash':cash_context(b,data)})
 return {'marketing_cost':marketing_cost,'planning':planning,'calculation_context':__import__('app.formulas',fromlist=['revision']).revision(data,config),'replenishment':regular,'model':MODEL,'basis':key,'schedule':schedule,'inputs':inputs,'items':rows,'issues':sorted(set(issues)),'finance_pending':sorted(set(finance_pending)),'scm_pending':sorted(set(scm_pending)),'scm_review_eligible':not issues and not scm_pending,'estimate_ready':not issues,'simple_review_eligible':not issues and not finance_pending and not scm_pending,'routes':routes,'cash':{'threshold':MIN_CASH,'baseline_minimum':min(bundle['scenarios'][k]['cash_min'] for k in selected),'complete':cash_complete,'minimum_after':min(results[k]['minimum'] for k in selected) if cash_complete else None,'scenarios':results,'confirmed':bundle['confirmed'],'scenario':bundle['selected'] if bundle['confirmed'] else '네 시나리오 합집합'},'source_versions':source_versions,'provenance':'예측·추천은 참가자 가정 / 검산은 계산 결과','method':'추가 수요는 동일 제품라인 완료 주 증분 P50. 장기 캠페인은 정기 보충(리드타임+1주 후 안전재고 도달 시 발주 검토)과 캠페인 추가분을 분리. 단기는 현재 확인 공급 기준 부족을 계산. MOQ 최소량 적용. 정기 보충·기존 PO 예상 입고는 가정이며 실제 공급·현금에 합산하지 않음.','limitations':['주간 판매는 약 18개월이며 30개월을 가장하지 않음. 자금일보의 30개월과 구분.','관측 증분은 인과 효과·보장 수요·확률이 아님. 자동 승인·발주·자금 조달 없음.',('실제 입고·지급 일정은 승인 후 SCM 발주·공급처 회신을 조회.' if estimate_only else '입고일은 원본 리드타임 가정이며 실제 공급 회신 아님. 지급일은 직접 확인해야 함.'),'마케팅 표본 예산은 전사 현금에 합산하지 않음. 새 발주 비용만 가상 대조.']}

def attach(case,raw,data,config,cid):
 """Recompute from authoritative data, and verify adopted values match the plan."""
 result=preview(raw,data,config,cid);p=case['marketing'];i=result['inputs']
 if (p.get('submission_mode')=='estimate_only')!=(i.get('mode')=='estimate_only'):raise ValueError('신청 유형과 예상안이 다릅니다.')
 if (p['as_of'],p['start'],p['end'],p['budget'],p['settlement_date'])!=(i['as_of'],i['start'],i['end'],i['budget'],i['settlement_date']):raise ValueError('사전검토와 기안의 기간·금액·정산일이 다릅니다. 다시 계산하세요.')
 if (p.get('group_total') or p['budget'])!=i['group_total']:raise ValueError('소속 기안 총액이 사전검토와 다릅니다.')
 mc=i.get('marketing_cost_inputs')
 if mc and mc.get('budget_mode')=='items' and (result['marketing_cost'].get('adopted_budget') is None or result['marketing_cost']['adopted_budget']!=p['budget']):raise ValueError('마케팅 비용 항목의 합계와 집행 예산이 다릅니다. 항목을 확인하고 다시 계산하세요.')
 if mc and (set(mc['media'])!=set(p.get('media',[])) or mc.get('product_line')!=p.get('target') or mc.get('country')!=p.get('country') or (mc.get('platform') or '')!=(p.get('sns_channel') or '') or (mc.get('sns_format') or '')!=(p.get('sns_format') or '') or (mc.get('influencer_id') or '')!=(p.get('influencer_id') or '')):raise ValueError('마케팅 비용의 매체·제품라인·국가가 기안과 다릅니다. 다시 계산하세요.')
 if set(p['scope_skus'])!={r['sku_id'] for r in i['items']} or len(p['items'])!=len(i['items']):raise ValueError('사전검토의 SKU·수요를 기안에 반영하세요.')
 for x in p['items']:
  chosen=next(r for r in result['items'] if r['sku_id']==x['sku_id'])
  if chosen['chosen_weekly_extra'] is None or abs(x['total_quantity']*7/((day(x['end'])-day(x['start'])).days+1)-chosen['chosen_weekly_extra'])>.000001:raise ValueError('사전검토와 기안의 추가 수요가 다릅니다. 다시 계산하세요.')
 st=i.get('schedule_terms') or {}
 if st.get('settlement_mode')=='derived' and p['settlement_date']!=result['schedule']['suggested_settlement']:raise ValueError('정산일 산정 조건과 기안 날짜가 다릅니다.')
 if st.get('deadline_mode')=='derived' and (not result['schedule']['deadline_applicable'] or p['contract_deadline']!=result['schedule']['suggested_deadline']):raise ValueError('기안 확정 권고일을 다시 검토하세요.')
 result['plan_signature']=signature(p);result['status']='사전검토 초안 · 부서 미확인'
 return result

def adopted(case,data,config):
 """Recompute an adopted draft, matching business values rather than JSON numeric types.
 Draft reuse never copies approvals. Changed demand/date/budget is rejected.
 """
 saved=case.get('ax_plan')
 if not saved:return None
 p=case['marketing'];raw=saved.get('inputs') or {}
 if not raw:return saved if saved.get('plan_signature')==signature(p) else None
 if any(p.get(k)!=raw.get(k) for k in ['as_of','start','end','budget','settlement_date']):return None
 if (p.get('group_total') or p.get('budget'))!=raw.get('group_total'):return None
 rows=raw.get('items',[])
 if set(p.get('scope_skus') or [])!={r['sku_id'] for r in rows} or len(p['items'])!=len(rows):return None
 for i in p['items']:
  r=next((r for r in rows if r['sku_id']==i['sku_id']),None)
  weekly=float(i['total_quantity'])*7/((day(i['end'])-day(i['start'])).days+1)
  if not r or i['start']!=raw['start'] or i['end']!=raw['end'] or r.get('demand') is None or abs(weekly-float(r['demand']))>.000001:return None
 try:
  live=preview(raw,data,config,case.get('_case_id') or case.get('id'))
  for i in p['items']:
   item=next(x for x in live['items'] if x['sku_id']==i['sku_id'])
   weekly=float(i['total_quantity'])*7/((day(i['end'])-day(i['start'])).days+1)
   if item['chosen_weekly_extra'] is None or abs(weekly-item['chosen_weekly_extra'])>.000001:return None
   old=next((x for x in saved.get('items',[]) if x['sku_id']==i['sku_id']),None)
   if old and any(old.get(k)!=item.get(k) for k in ['chosen_qty','chosen_unit_price']):return None
  return live
 except ValueError:return None

def current(case,data,config):
 saved=case.get('ax_plan')
 if not saved:raise ValueError('기안의 사전검토 자료가 없습니다. 기존 검토 절차를 사용하세요.')
 if saved.get('plan_signature')!=signature(case['marketing']):raise ValueError('기안이 변경되었습니다. 마케팅에서 사전검토를 갱신하세요.')
 live=preview(saved['inputs'],data,config,case.get('_case_id'))
 if live['basis']!=saved['basis']:raise ValueError('자료·현금 기준·다른 캠페인 약속이 변경되었습니다. 사전검토를 갱신하세요.')
 return live

def confirm(case,data,config,raw,role):
 from app.execution import metadata,projection
 from app import scm,finance_review
 from app.demand import assess
 b=copy.deepcopy(case);m=metadata(raw)
 if b.get('execution',{}).get('orders') or b.get('execution',{}).get('closed'):raise ValueError('발주 전달·종료 후 간편 확인할 수 없습니다.')
 live=current(b,data,config)
 eligible=live.get('scm_review_eligible') if role=='SCM' and live['inputs'].get('mode')=='estimate_only' else live['simple_review_eligible']
 if not eligible:raise ValueError('상세 검토 필요: '+' / '.join(live['issues']+live.get('scm_pending',[])+live.get('finance_pending',[])))
 stage=projection(b,data,config)['stage']
 if role=='SCM':
  if stage!=2:raise ValueError('SCM 검토 단계에서만 확인할 수 있습니다.')
  a=assess(b,data)
  if any(i['missing'] or i['outside_range'] or i['insufficient_evidence'] for i in a['items']):raise ValueError('수요 근거를 상세 검토하세요.')
  b['demand_review']={**m,'role':role,'basis':a['basis'],'override_reason':'','note':'SCM이 사전검토 수요 근거와 공급을 함께 확인'}
  items=[{'sku_id':r['sku_id'],'supply_result':'가능','procurement':'신규 발주 검토' if r['chosen_qty'] else '추가 조달 없음','target_qty':math.ceil(r['safety_target']),'target_basis':live['method'],'requested_qty':r['chosen_qty'],'requested_unit_price':r['chosen_unit_price'],'requested_payment_date':r['payment_date'],'planned_order_date':b['as_of'] if r['chosen_qty'] else None,'proposed_available_date':r['earliest_arrival_assumption'] if r['chosen_qty'] else None,'note':'기안 사전검토 확인 · '+m['evidence']} for r in live['items']]
  review=scm.validate_review({**m,'direction':'추가 발주 필요' if any(r['chosen_qty'] for r in live['items']) else '재고로 가능','items':items,'requests':[],'alternatives':'변경·긴급 이슈 발생 시 기존 상세 검토로 전환'},b,data)
  calc=scm.analysis(b,data,config,review=review);scm.can_handoff(review,calc)
  review.update(valid=True,basis=scm.basis(b,data),at=m['at'],provenance='부서 주장')
  b.setdefault('scm',{})['review']=review;b['marketing_stage']='재무 검토 요청';b['scm']['finance_packet']=scm.packet(b,review,calc)
 elif role=='재무':
  if stage!=3:raise ValueError('SCM 확인을 마친 재무 검토 단계에서만 진행하세요.')
  if not config.get('confirmed'):raise ValueError('공식 재무 시나리오를 먼저 확정하세요.')
  r=finance_review.initial_review(b)
  r.update(**{k:m[k] for k in ['decision_maker','reason','evidence']},opinion='기안의 유출일·현금 영향·계산된 결재선을 확인하여 승인 요청',alternatives='조건·자료 변경 시 재무 재판정',performance_basis=b['marketing'].get('performance_evidence') or b['marketing'].get('performance_unknown_reason') or '성과는 미확인 · 공급/현금 사전검토와 구분')
  for t in r['targets']:t['cash_scope']='전사 현금 반영 확인' if t['kind']=='재고발주' else '표본·현금 합산 제외'
  r=finance_review.validate(r,b,data);r.update(operation='submit',basis=finance_review.basis(b,data,config),at=m['at'],provenance='부서 주장')
  test=finance_review.view(b,data,config,r)
  if test['errors']:raise ValueError('상세 재무 검토 필요: '+' / '.join(test['errors']))
  b['finance_review']=r
 else:raise ValueError('SCM·재무 담당자가 각 부서의 확인을 기록합니다.')
 b.setdefault('operations',{}).setdefault('ax_confirmations',{})[role]=m
 return b,{'operation':'ax_confirm','model':MODEL,'basis':live['basis'],'role':role,**m,'note':'사전검토를 부서 담당자가 확인. 최종 승인·발주·지급 아님.'}
