"""Single planning calculation shared by marketing, SCM and downstream evidence."""
from datetime import date,timedelta
import math
from app.formulas import run,token

MODEL='W01-SHARED-PLANNING-1'
def lead_days(data,weeks):
 value=run(data,'lead_time_days',lead_weeks=float(weeks))
 if value!=int(value) or not 1<=value<=365:raise ValueError('리드타임 산식은 1~365일의 정수여야 합니다.')
 return int(value)
def lead_date(data,value,weeks,direction=1):
 return (date.fromisoformat(value)+timedelta(days=direction*lead_days(data,weeks))).isoformat()
def snapshot(data,case,ledger=None,regular=None):
 from app.portfolio import simulate
 from app.replenishment import plan
 ledger=ledger or simulate(data,case,end=case['marketing']['end']);regular=regular or plan(case,data)
 p=case['marketing'];items=[]
 for row in regular['items']:
  sid=row['sku_id'];raw=next(r for r in ledger['items'] if r['sku_id']==sid)
  use_regular=(date.fromisoformat(p['start'])-date.fromisoformat(p['as_of'])).days>lead_days(data,row['lead_time_weeks']) and row['feasible']
  minimum=raw['campaign_min'];target=run(data,'safety_target',weekly=row['baseline_weekly'],safety_weeks=row['safety_min_weeks'])
  gap=row['incremental_qty'] if use_regular else math.ceil(run(data,'ax_replenishment_gap',safety_target=target,minimum_projected=minimum)) if minimum is not None and not raw['unknown_demand'] else None
  qty=gap if use_regular else math.ceil(run(data,'procurement_moq',gap=gap,moq=float(next(s['moq'] for s in data['sku']['rows'] if s['sku_id']==sid)))) if gap else gap
  review=next((i for i in case.get('scm',{}).get('review',{}).get('items',[]) if i['sku_id']==sid),{})
  order_date=review.get('planned_order_date') or p['as_of']
  from app.planning_schedule import shift_business
  items.append({'sku_id':sid,'recommended_qty':qty,'safety_target':target,'use_regular':use_regular,'earliest_arrival_assumption':lead_date(data,p['as_of'],row['lead_time_weeks']),'order_by':lead_date(data,p['start'],row['lead_time_weeks'],-1),'order_draft_arrival':lead_date(data,order_date,row['lead_time_weeks']),'planned_order_date':order_date,'reply_deadline_hint':shift_business(order_date,3),'lead_time_days':lead_days(data,row['lead_time_weeks'])})
 return {'model':MODEL,'formula_revision':token(data),'replenishment':regular,'items':items,'provenance':'참가자 가정 / 계산 결과','note':'공통 산식의 현재 계획. 실제 발주·회신·지급 기록은 별도로 보존.'}

def catalog(data,asof='2026-07-01'):
 out=[]
 for sku in data['sku']['rows']:
  rows=sorted([r for r in data['sales']['rows'] if r['sku_id']==sku['sku_id'] and date.fromisoformat(r['week'])+timedelta(days=7)<=date.fromisoformat(asof)],key=lambda r:r['week'])[-4:]
  avg=run(data,'weekly_average',sales_total=sum(float(r['sold_qty']) for r in rows),weeks_count=len(rows)) if rows else None
  out.append({'sku_id':sku['sku_id'],'weekly_average':avg,'lead_time_days':lead_days(data,sku['lead_time_weeks'])})
 return out
