"""Planning dates from explicit assumptions, never inferred contract/payment terms."""
from datetime import date,timedelta

def shift_business(value,days):
 d=date.fromisoformat(value);step=1 if days>=0 else -1
 for _ in range(abs(days)):
  d+=timedelta(days=step)
  while d.weekday()>=5:d+=timedelta(days=step)
 return d.isoformat()

def terms(raw):
 if raw is None:return None
 if not isinstance(raw,dict):raise ValueError('일정 산정 조건을 확인하세요.')
 base=raw.get('settlement_base','end')
 if base not in ['start','end']:raise ValueError('정산 기준일을 확인하세요.')
 def integer(key,default,maximum):
  v=raw.get(key,default)
  if v in [None,'']:return None
  if type(v) is bool:raise ValueError('일정 일수는 정수입니다.')
  try:n=int(v)
  except (ValueError,TypeError,OverflowError):raise ValueError('일정 일수는 정수입니다.')
  if str(n)!=str(v) or not 0<=n<=maximum:raise ValueError('일정 일수 범위를 확인하세요.')
  return n
 out={'settlement_base':base,'settlement_offset_days':integer('settlement_offset_days',None,180),'review_business_days':integer('review_business_days',3,30)}
 if out['review_business_days'] is None:raise ValueError('검토 여유일을 입력하세요.')
 for k in ['settlement_mode','deadline_mode']:
  out[k]=raw.get(k,'manual')
  if out[k] not in ['manual','derived']:raise ValueError('일정 채택 방식을 확인하세요.')
 return out

def calculate(inputs,rows,raw=None,data=None):
 from app.planning import lead_date
 data=data or {}
 t=terms(raw) or {'settlement_base':'end','settlement_offset_days':None,'review_business_days':3,'settlement_mode':'manual','deadline_mode':'manual'}
 start=inputs['start'];active=[r for r in rows if r['chosen_qty'] is None or r['chosen_qty']>0]
 plans=[{'sku_id':r['sku_id'],'order_by':lead_date(data,start,r['lead_time_weeks'],-1),'lead_time_weeks':r['lead_time_weeks'],'earliest_arrival':lead_date(data,inputs['as_of'],r['lead_time_weeks']),'quantity_unconfirmed':r['chosen_qty'] is None} for r in active]
 milestone=min([start]+[r['order_by'] for r in plans]);deadline=shift_business(milestone,-t['review_business_days']);offset=t['settlement_offset_days']
 settlement=(date.fromisoformat(inputs[t['settlement_base']])+timedelta(days=offset)).isoformat() if offset is not None else None
 return {'terms':t,'orders':plans,'suggested_deadline':deadline,'deadline_applicable':deadline>=inputs['as_of'],'suggested_settlement':settlement,'procurement_budget':sum(r['estimated_cost'] or 0 for r in rows) if all(r['chosen_qty'] is not None and (r['chosen_qty']==0 or r['estimated_cost'] is not None) for r in rows) else None,'provenance':'참가자 가정 / 계산 결과','basis':'기안 확정 권고일 = min(캠페인 시작일, 추가 발주의 리드타임 역산 발주시한) − 검토 여유 영업일. 월~금, 공휴일 미반영. 실제 계약 확정기한을 입증하지 않음. 정산일은 선택한 캠페인 기준일 + 직접 입력한 유예 달력일이며 발주 지급일과 별도.'}
