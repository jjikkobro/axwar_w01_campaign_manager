"""Read-only replenishment drafts. Never creates POs, confirmed stock or cash entries."""
import math
from datetime import date,timedelta
from app.portfolio import simulate,supplies,digest,records
from app.formulas import run
from app.planning import lead_days,lead_date

POLICY={'id':'SCM-REPLENISH-2','source':'Business_Process_Map.md §2.2; calculation_definitions.md §1.3; m_sku_ms',
 'provenance':'참가자 가정 / 계산 결과','review_interval_days':7,
 'assumptions':['7일마다 보충 검토 · 원본에 주기 명시 없음',
 '최근 완료 4주 평균 판매 유지 · 일별 균등 배분',
 '리드타임+1주 후 예상 재고가 최소 안전재고 이하이면 이번 주 발주안 생성 · 사용자 지정 가정. 리드타임+최대 안전재고까지 보충, MOQ 최소량 적용',
 '기존 미확인 발주는 발주일+리드타임을 예상 입고일로만 사용. 실제 판매가능일 미확인',
 '공급능력·견적·지급일 미확인. 승인·확정 입고·현금 전망에 자동 합산하지 않음']}

def plan(case,data):
 p=case['marketing'];raw=simulate(data,case,end=p['end']);start=date.fromisoformat(p['as_of']);end=date.fromisoformat(p['end']);result=[]
 confirmed=supplies(data,case)['confirmed'];confirmed_ids={r['po_id'] for r in confirmed}
 for base in raw['items']:
  sid=base['sku_id'];sku=next(s for s in data['sku']['rows'] if s['sku_id']==sid)
  weekly=base['weekly_average'];lead=int(sku['lead_time_weeks']);minw=int(sku['safety_stock_weeks_min']);maxw=int(sku['safety_stock_weeks_max']);moq=int(sku['moq'])
  orders=[];pipeline=[];unplaced=[]
  # One dated PO pipeline; never add the aggregate in_transit quantity again.
  for po in data['purchase']['rows']:
   if po['sku_id']!=sid or po['po_id'] in confirmed_ids:continue
   replies=[r['receipts'][po['po_id']] for r in records(data,case) if po['po_id'] in r['receipts'] and r['receipts'][po['po_id']].get('po_fingerprint')==digest(po)]
   latest=max(replies,key=lambda r:r.get('at',''),default={})
   if latest.get('status')=='불가':continue
   arrival=date.fromisoformat(lead_date(data,po['order_date'],po.get('lead_time_weeks') or lead))
   if arrival<start:unplaced.append(po['po_id']);continue
   pipeline.append({'id':po['po_id'],'date':arrival.isoformat(),'qty':float(po['order_qty']),'kind':'기존 발주 예상 입고 · 미확인','source':'sc_purchase_orders_ms','provenance':'참가자 가정'})
  pending=list(pipeline);daily=[];stock=base['days'][0]['opening'] if base['days'] else 0
  bydate={d['date']:d for d in base['days']}
  for offset in range((end-start).days+1):
   current=start+timedelta(days=offset);ds=current.isoformat();row=bydate.get(ds)
   if not row:break
   stock+=row['inflow']+sum(o['qty'] for o in pending if o['date']==ds)
   if offset%7==0 and weekly>0 and base['data_complete']:
    until=(current+timedelta(days=lead_days(data,lead)+maxw*7)).isoformat()
    outstanding=sum(o['qty'] for o in pending if ds<o['date'])
    incoming=sum(d['inflow'] for d in base['days'] if ds<d['date']<=until)
    other=sum(d['other_campaign'] for d in base['days'] if ds<=d['date']<until)
    position=stock+outstanding+incoming
    next_week=(current+timedelta(days=lead_days(data,lead)+7)).isoformat()
    other_next=sum(d['other_campaign'] for d in base['days'] if ds<=d['date']<next_week)
    trigger=run(data,'replenishment_trigger',weekly=weekly,lead_weeks=lead_days(data,lead)/7,review_weeks=1,safety_weeks=minw)+other_next
    check_position=stock+sum(o['qty'] for o in pending if ds<o['date']<=next_week)+sum(d['inflow'] for d in base['days'] if ds<d['date']<=next_week)
    target=run(data,'replenishment_target',weekly=weekly,lead_weeks=lead_days(data,lead)/7,safety_weeks=maxw)+other
    gap=run(data,'procurement_gap',target=target,on_hand=stock,in_transit=outstanding+incoming)
    if check_position<=trigger and gap>0:
     qty=math.ceil(run(data,'procurement_moq',gap=math.ceil(round(gap,8)),moq=moq));arrival=lead_date(data,ds,lead)
     o={'id':'DRAFT-'+sid+'-'+ds,'order_date':ds,'date':arrival,'qty':qty,'lead_plus_week_stock':round(check_position-run(data,'baseline_daily',weekly=weekly)*(lead_days(data,lead)+7)-other_next,4),'trigger_checkpoint':next_week,'safety_qty':run(data,'safety_target',weekly=weekly,safety_weeks=minw),'kind':'정기 보충 계산안','provenance':'참가자 가정 / 계산 결과'}
     orders.append(o);pending.append(o)
   stock-=row['base']+row['other_campaign']
   daily.append({'date':ds,'baseline_closing':round(stock,4),'campaign_closing':round(stock-sum(d['campaign'] for d in base['days'] if d['date']<=ds),4)})
  campaign=[d for d in daily if p['start']<=d['date']<=p['end']];target=run(data,'safety_target',weekly=weekly,safety_weeks=minw)
  minimum=min((d['campaign_closing'] for d in campaign),default=None)
  baseline_min=min((d['baseline_closing'] for d in campaign),default=None)
  gap=math.ceil(round(run(data,'ax_replenishment_gap',safety_target=min(target,baseline_min),minimum_projected=minimum),8)) if minimum is not None else None
  extra=math.ceil(run(data,'procurement_moq',gap=gap,moq=moq)) if gap else gap
  arrival=lead_date(data,p['as_of'],lead)
  after=min((d['campaign_closing']+(extra or 0 if d['date']>=arrival else 0) for d in campaign),default=None)
  required=next((d['date'] for d in daily if d['campaign_closing']<target and d['date']>=p['start']),p['start'])
  latest=lead_date(data,required,lead,-1)
  past=[o for o in data['purchase']['rows'] if o['sku_id']==sid and o['order_date']<=p['as_of'] and float(o['order_qty'])>0]
  po=max(past,key=lambda o:o['order_date'],default=None);price=math.ceil(float(po['amount_krw'])/float(po['order_qty'])) if po else None
  regular_qty=sum(o['qty'] for o in orders if o['date']<=p['end'])
  result.append({'sku_id':sid,'name':sku['sku_name'],'data_complete':base['data_complete'] and not base['unknown_demand'],'baseline_weekly':weekly,'lead_time_weeks':lead,'effective_lead_days':lead_days(data,lead),'safety_min_weeks':minw,'safety_max_weeks':maxw,'safety_qty':target,'regular_orders':orders,'pipeline_assumptions':pipeline,'undated_overdue_pos':unplaced,'regular_qty':regular_qty,'regular_cost':run(data,'purchase_amount',qty=regular_qty,unit_price=price) if price is not None else None,'incremental_qty':extra,'incremental_cost':run(data,'purchase_amount',qty=extra,unit_price=price) if extra is not None and price is not None else None,'reference_unit_price':price,'price_source':po['po_id'] if po else None,'baseline_min':baseline_min,'campaign_min_with_regular':minimum,'campaign_min_with_extra':after,'earliest_arrival_assumption':arrival,'latest_order_date':latest,'feasible':after is not None and after>=-0.000001 and base['data_complete'] and not base['unknown_demand'],'pre_campaign_gap':next((d['date'] for d in daily if d['date']<p['start'] and d['baseline_closing']<0),None),'days':daily})
 return {'policy':POLICY,'items':result,'feasible':bool(result) and all(i['feasible'] for i in result) and not raw['supply']['conflicts'],'provenance':'참가자 가정 / 계산 결과','note':'정기 보충을 실행한다는 조건의 계획. 실제 재고·승인·발주·현금과 분리.','basis':digest({'policy':POLICY,'plan':p,'sources':{k:v for k,v in data.items() if k in ['sku','sales','inventory','purchase','formula_settings','portfolio']}})}
