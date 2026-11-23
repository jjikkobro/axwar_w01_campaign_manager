"""W01 calculations. Dates and units remain explicit; missing supply is never inferred."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import csv
import io
from app.finance import cash_bundle, routing
from app.formulas import run,context

ROLES = ['마케팅', 'SCM', '재무', '승인권자']
SCHEMAS = {
 'sku': ('SKU 마스터', 'SCM', ['sku_id','sku_name','product_id','safety_stock_weeks_min','safety_stock_weeks_max','moq','lead_time_weeks']),
 'inventory': ('재고', 'SCM', ['sku_id','snapshot_date','on_hand_qty','in_transit_qty']),
 'sales': ('주간 판매', '마케팅', ['week','sku_id','sold_qty']),
 'purchase': ('발주', 'SCM', ['po_id','sku_id','order_qty','amount_krw','payment_due_date']),
 'cash': ('현금 실적', '재무', ['date','closing_balance']),
 'ar': ('회수 예정', '재무', ['ar_id','due_date','outstanding_krw']),
 'ap': ('지급 예정', '재무', ['ap_id','po_id','payment_due_date','amount_krw']),
 'forecast': ('공식 전망 · 부서 주장', '재무', ['forecast_date','week','projected_inflow_krw','projected_outflow_krw','projected_closing_krw']),
}
NUMERIC = {'on_hand_qty','in_transit_qty','sold_qty','order_qty','amount_krw','outstanding_krw','closing_balance','moq','lead_time_weeks','safety_stock_weeks_min','safety_stock_weeks_max','projected_inflow_krw','projected_outflow_krw','projected_closing_krw'}
DATES = {'week','snapshot_date','date','due_date','payment_due_date','forecast_date'}

def number(value, label='수치'):
 try:
  v = Decimal(str(value))
  if not v.is_finite() or v < 0 or v != v.to_integral_value(): raise ValueError()
  return int(v)
 except (InvalidOperation, ValueError, TypeError): raise ValueError(f'{label}: 0 이상의 정수를 입력하세요.')

def day(value):
 try: return date.fromisoformat(str(value))
 except (TypeError, ValueError): raise ValueError('날짜는 YYYY-MM-DD 형식이어야 합니다.')

def parse_dataset(kind, text):
 if kind not in SCHEMAS: raise ValueError('지원하지 않는 데이터입니다.')
 if not isinstance(text, str) or len(text) > 2_000_000: raise ValueError('파일은 2MB 이하이어야 합니다.')
 reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')), delimiter='|')
 required = SCHEMAS[kind][2]
 if not reader.fieldnames or not set(required) <= set(reader.fieldnames): raise ValueError('필수 열: ' + ' | '.join(required))
 rows = list(reader)
 if not rows or len(rows) > 10000: raise ValueError('1~10,000행을 입력하세요.')
 keys = {'sku':['sku_id'],'inventory':['sku_id'],'sales':['sku_id','week'],'purchase':['po_id'],'cash':['date'],'ar':['ar_id'],'ap':['ap_id'],'forecast':['week']}[kind]
 seen=set()
 for i,row in enumerate(rows,2):
  if None in row or any(row.get(k) is None or not row[k].strip() for k in required): raise ValueError(f'{i}행: 빈 필수 값 또는 열 개수 오류입니다.')
  for k,v in row.items():
   if len(v or '') > 1000: raise ValueError(f'{i}행: 값이 너무 깁니다.')
   if k in NUMERIC: number(v,k)
   if k in DATES: day(v)
  key=tuple(row[k] for k in keys)
  if key in seen: raise ValueError(f'{i}행: 식별자가 중복되었습니다.')
  seen.add(key)
 return rows

def validate_case(c):
 # Requesters cannot inject finance decisions, approvals, routing or workflow state.
 allowed={'title','sku_id','start','end','as_of','quantity','evidence','demand_status','approval_type','requested_payment_date','requested_amount','contract_deadline','proposal_id','proposal_total','proposal_basis','annual_amount'}
 c={k:v for k,v in c.items() if k in allowed}
 for k in ['title','sku_id','start','end','as_of','quantity','evidence','demand_status']:
  if k not in c: raise ValueError(f'{k} 값이 필요합니다.')
 if not str(c['title']).strip() or len(c['title'])>120: raise ValueError('제목은 1~120자입니다.')
 c['quantity']=number(c['quantity'],'캠페인 수량')
 if not c['quantity']: raise ValueError('캠페인 수량은 1 이상이어야 합니다.')
 if not day(c['as_of']) <= day(c['start']) <= day(c['end']): raise ValueError('기준일 ≤ 시작일 ≤ 종료일이어야 합니다.')
 if (day(c['end'])-day(c['as_of'])).days > 180: raise ValueError('최대 180일까지만 검토합니다.')
 if c['demand_status'] not in ['가정','확인됨','미확인']: raise ValueError('수요 근거 구분을 확인하세요.')
 if len(str(c['evidence']))>4000: raise ValueError('근거는 4,000자 이하입니다.')
 c['approval_type']=c.get('approval_type','재고발주')
 if c['approval_type'] not in ['재고발주','캠페인집행','연간전속계약']:raise ValueError('승인 유형을 선택하세요.')
 for key in ['requested_amount','proposal_total','annual_amount']:
  if c.get(key) not in (None,''):c[key]=number(c[key],key)
  else:c[key]=None
 for key in ['requested_payment_date','contract_deadline']:
  if c.get(key):day(c[key])
  else:c[key]=None
 if c['approval_type']=='캠페인집행' and (not c.get('proposal_id') or not c.get('proposal_basis') or c.get('proposal_total') is None):raise ValueError('캠페인집행은 소속 기안 ID·총액·묶음 근거가 필요합니다.')
 c['value_provenance']={'request':'참가자 가정','approval_rules':'내부 통제','demand_evidence':c['evidence']}
 return c

def validate_reply(r,case,datasets):
 if r.get('role') not in ROLES: raise ValueError('담당 역할을 확인하세요.')
 if not isinstance(r.get('message'),str) or not 1<=len(r['message'].strip())<=4000: raise ValueError('회신 내용은 1~4,000자입니다.')
 if r.get('result') not in ['확인','보완 필요','거절']: raise ValueError('회신 상태를 확인하세요.')
 if r.get('po_id'):
  po=next((x for x in datasets['purchase']['rows'] if x['po_id']==r['po_id'] and x['sku_id'] in {i['sku_id'] for i in case.get('marketing',{}).get('items',[{'sku_id':case['sku_id']}])}),None)
  if not po: raise ValueError('선택 SKU의 기존 발주를 선택하세요.')
  if number(r.get('qty'), '공급 수량') > number(po['order_qty']): raise ValueError('회신 수량이 기존 발주량을 초과합니다.')
  day(r.get('available_date'))
  if day(r['available_date'])<day(case['as_of']): raise ValueError('기준일 이전 공급은 현재고에서 확인하세요.')
 if r['role']=='재무' and r['result']=='확인':
  number(r.get('new_payment',0),'신규 지급액')
  if number(r.get('new_payment',0)): day(r.get('payment_date'))
 return r

def calculate(case,datasets,finance_config=None):
 datasets=context(datasets,finance_config or {})
 if not case.get('marketing'):return _calculate_single(case,datasets,finance_config)
 from app.marketing import route
 from app.scm import receipt_replies
 case={**case,'replies':case.get('replies',[])+receipt_replies(case,datasets)}
 items=[]
 for item in case['marketing']['items']:
  single={**case,'sku_id':item['sku_id'],'quantity':item['total_quantity'],'demand_start':item['start'],'demand_end':item['end']}
  calc=_calculate_single(single,datasets,finance_config)
  weekly_extra=run(datasets,'campaign_daily',total_quantity=item['total_quantity'],duration_days=(day(item['end'])-day(item['start'])).days+1)*7
  calc['simple_cover']=round(run(datasets,'campaign_cover',on_hand=number(calc['inventory']['on_hand_qty']),weekly=calc['weekly'],weekly_extra=weekly_extra),2) if calc['weekly']+weekly_extra else None
  if 'portfolio' in datasets:
   from app.portfolio import simulate
   plan=simulate(datasets,case,end=calc['stock'][-1]['date'],sku_ids=[item['sku_id']]);combined=plan['items'][0]
   calc['stock']=combined['days'];calc['first_short']=combined['first_short'];calc['portfolio']=plan
   calc['warnings']+=plan['warnings']+(['승인된 다른 캠페인의 수요 약속 포함: '+', '.join(combined['other_case_ids'])] if combined['other_case_ids'] else [])
  calc['demand']=item;items.append(calc)
 if not items:
  bundle=cash_bundle(datasets,finance_config);active=bundle['scenarios'][bundle['selected']]
  return {'items':[],'routing':route(),'authority':route()['authority'],'finance':bundle,'cash':active['daily'],'cash_min':active['cash_min'],'warnings':['SKU 수요 가정 미입력. 공급 가능을 확정하지 않으며 SCM에서 SKU·수요 확인이 필요합니다.'],'missing':['SKU·수요 확인'],'stock':[],'primary_sku_only':False}
 result={**items[0],'items':items,'primary_sku_only':True,'routing':route(),'authority':route()['authority']}
 result['warnings']+=['제품별 결과를 별도로 확인하세요. 대표 SKU 수치는 합산 결과가 아닙니다.']
 return result

def _calculate_single(case,datasets,finance_config=None):
 rows=lambda k:datasets[k]['rows']
 sku=next((r for r in rows('sku') if r['sku_id']==case['sku_id']),None)
 inv=next((r for r in rows('inventory') if r['sku_id']==case['sku_id']),None)
 if not sku or not inv: raise ValueError('SKU 또는 재고 자료가 없습니다.')
 asof=day(case['as_of']); end=day(case['end']); start=day(case['start'])
 if day(inv['snapshot_date'])>=asof: raise ValueError('재고 스냅샷 이후 날짜를 기준일로 설정하세요.')
 sales=sorted([r for r in rows('sales') if r['sku_id']==case['sku_id'] and day(r['week'])+timedelta(days=7)<=asof],key=lambda x:x['week'])[-4:]
 warnings=[]
 from app.formulas import entries
 if entries(datasets):warnings.append('사용자 산식 적용 · 참가자 가정: '+', '.join(entries(datasets))+' · 계산식 설정에서 식·근거 확인')
 if len(sales)<4: warnings.append('완료된 4주 판매 데이터가 부족합니다.')
 weekly=run(datasets,'weekly_average',sales_total=sum(number(r['sold_qty']) for r in sales),weeks_count=len(sales)) if sales else 0
 if not weekly: warnings.append('수요 계산을 위한 판매량이 없습니다.')
 if day(inv['snapshot_date'])!=asof-timedelta(days=1): warnings.append('재고 기준일과 검토 기준일 사이의 수불 확인이 필요합니다.')
 if case['demand_status']!='확인됨': warnings.append('추가 수요는 확정 관측값이 아닙니다. 근거와 가정을 검토하세요.')
 replies=case.get('replies',[])
 latest={r['role']:r for r in replies}
 missing=[r for r in ['마케팅','SCM','재무'] if latest.get(r,{}).get('result')!='확인']
 supplies={}
 for r in replies:
  if r.get('role')=='SCM' and r.get('po_id'):
   supplies[r['po_id']]=r
 inflows={}
 for r in supplies.values():
  if r['result']=='확인' and r.get('confirmed') is True and any(p['po_id']==r['po_id'] and p['sku_id']==case['sku_id'] for p in rows('purchase')):
   inflows[r['available_date']]=inflows.get(r['available_date'],0)+number(r['qty'])
 if number(inv['in_transit_qty']): warnings.append('운송 중 수량은 발주 회신으로 확인된 판매 가능일에만 반영합니다. 별도로 더하지 않습니다.')
 horizon=min(asof+timedelta(days=180),max(end+timedelta(days=14),asof+timedelta(days=34)))
 stock=float(number(inv['on_hand_qty'])); chart=[]; first_short=None
 demand_start=day(case.get('demand_start',case['start']));demand_end=day(case.get('demand_end',case['end']))
 campaign_days=(demand_end-demand_start).days+1
 for i in range((horizon-asof).days+1):
  d=asof+timedelta(days=i); added=inflows.get(d.isoformat(),0)
  before=stock+added
  extra=run(datasets,'campaign_daily',total_quantity=case['quantity'],duration_days=campaign_days) if demand_start<=d<=demand_end else 0
  base=run(datasets,'baseline_daily',weekly=weekly)
  stock=before-base-extra
  if stock<0 and not first_short:first_short=d.isoformat()
  chart.append({'date':d.isoformat(),'inflow':added,'base':round(base,2),'campaign':round(extra,2),'closing':round(stock,2)})
 bundle=cash_bundle(datasets,finance_config)
 route=routing(case,bundle)
 active=bundle['scenarios'][bundle['selected']]
 return {'evidence_sources':{k:{'source':v.get('source','미확인'),'version':v.get('version'),'provenance':v.get('provenance','미확인')} for k,v in datasets.items()},'sku':sku,'inventory':inv,'weekly':round(weekly,2),'weeks':[r['week'] for r in sales],'cover':round(run(datasets,'inventory_cover',on_hand=number(inv['on_hand_qty']),weekly=weekly),2) if weekly else None,'stock':chart,'first_short':first_short,'cash':active['daily'],'first_breach':active['first_breach'],'cash_min':active['cash_min'],'authority':route['authority'],'routing':route,'finance':bundle,'missing':missing,'warnings':warnings+bundle['validation_errors'],'safety_target':run(datasets,'safety_target',weekly=weekly,safety_weeks=number(sku['safety_stock_weeks_min'])),'provenance':{'inventory':datasets['inventory'].get('provenance','원본 사실'),'demand':'참가자 가정','stock':'계산 결과','cash':'계산 결과','routing':'계산 결과','rules':'내부 통제'},'assumptions':['완료된 최근 4주 평균을 일별 균등 수요로 사용','캠페인 수량은 기간에 균등 배분','예약수량은 원본에 없어 별도 차감하지 않음','검토기간 이후의 공급 보장은 하지 않음','현금 4개 시나리오를 분리 계산하며 재무 미확정 시 합집합 하회구간으로 판정']}

def transition(case,action,role,calc):
 if case.get('marketing'):raise ValueError('마케팅 계획 공유는 승인·발주 건이 아닙니다. SCM 검토 후 승인 대상을 구분하세요.')
 status=case['status']
 allowed={'request':('SCM',['접수','검토 중','보완 필요','재검토 필요']),'submit':('SCM',['접수','검토 중','회신 대기','보완 필요','재검토 필요','조건부 승인']),'approve':('승인권자',['승인 대기']),'conditional':('승인권자',['승인 대기']),'reject':('승인권자',['승인 대기']),'order':('SCM',['승인']),'complete':('SCM',['발주 전달'])}
 if action not in allowed or role!=allowed[action][0] or status not in allowed[action][1]:raise ValueError('현재 역할 또는 상태에서 실행할 수 없습니다.')
 if action in ['submit','approve','conditional','order'] and calc.get('routing',{}).get('blocked'):raise ValueError('지급일·신규약정 분류·재무 시나리오 확정 전에는 승인을 진행할 수 없습니다.')
 if action=='submit':
  if calc['missing']:raise ValueError('마케팅·SCM·재무의 확인 회신을 먼저 확보하세요.')
  if calc['weekly']<=0:raise ValueError('판매량을 확인하세요.')
 if action in ['approve','conditional'] and (not case.get('decision_note') or not case.get('approval_scope')):raise ValueError('승인 범위와 위험·미확인 사항에 대한 조건을 작성하세요.')
 if action=='complete' and not any(r.get('role')=='SCM' and r.get('after_order') for r in case.get('replies',[])):raise ValueError('발주 전달 후 공급자 회신을 먼저 기록하세요.')
 return {'request':'회신 대기','submit':'승인 대기','approve':'승인','conditional':'조건부 승인','reject':'보완 필요','order':'발주 전달','complete':'회신 기록 완료'}[action]
