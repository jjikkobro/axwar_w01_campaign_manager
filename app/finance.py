"""Cash schedules, provenance, and deterministic routing. Never grants approval."""
from datetime import date, timedelta
from collections import defaultdict
from app.policy import PROJECT_POLICY

AS_OF = date(2026, 7, 1)
MIN_CASH = 3_000_000_000
SCENARIOS = {
 'collect_pay': ('7/1 회수 가정', '7/1 지급 가정', True, True),
 'collect_exclude': ('7/1 회수 가정', '지급일 미확인으로 미반영', True, False),
 'exclude_pay': ('회수일 미확인으로 유입 제외', '7/1 지급 가정', False, True),
 'exclude_exclude': ('회수일 미확인으로 유입 제외', '지급일 미확인으로 미반영', False, False),
}
DEFAULT_FINANCE = {'selected':'exclude_pay','confirmed':False,'weekend_shift':False,
 'review_date':'2026-07-01','next_review_date':'2026-07-08','overrides':{}}
PROVENANCE = ['원본 사실','부서 주장','참가자 가정','내부 통제','계산 결과','모의 회신']
RULES = {
 'version':'W01-2026-11-10.1',
 'project_policy':PROJECT_POLICY,
 'source':'00_common/approval_authority_policy.md; 02_masil/financials/covenant_terms_ms.md',
 'cash_formula_source':'00_common/calculation_definitions.md §1.2',
 'interpretation':{'provenance':'내부 통제','basis':'기존 SPO-0001~0014는 원본 확정 발주. 증량·추가발주·지급일 앞당김의 증가/조기 유출분을 신규 약정으로 해석. 감량·연기·취소는 SCM 변경 승인. 기존 채무 자체는 하회 원인으로 관리.'},
 'task_policy':{'provenance':'내부 통제','basis':'다음 주간 재전망보다 결정기한이 빠르면 수시 확정요청. 원본 기한은 변경하지 않음.'},
 'approval_boundary':'결재선 산출은 승인 행위가 아니다. AI·시스템은 자동 승인·자동 지급하지 않는다.'}

def iso(d): return d.isoformat()
def next_business(d):
 while d.weekday()>4: d+=timedelta(days=1)
 return d

def validate_commitment(assessment,original_orders,sku_id):
 change=assessment['change']
 if change in ['추가발주','신규 계약']:return
 po=next((p for p in original_orders if p['po_id']==assessment.get('reference_po') and p['sku_id']==sku_id),None)
 if not po or po['po_id'] not in {f'SPO-{i:04d}' for i in range(1,15)}:raise ValueError('기존·변경 약정은 원본 SPO-0001~0014에 연결해야 합니다.')
 amount=int(assessment['amount']);original_amount=int(po['amount_krw']);d=assessment['payment_date'];original_date=po['payment_due_date']
 if change=='기존 약정' and (amount!=original_amount or d!=original_date):raise ValueError('기존 약정은 원본 지급액·지급일과 일치해야 합니다.')
 if change=='지급일 앞당김' and d>=original_date:raise ValueError('앞당김은 원본 지급일보다 이른 유출일이어야 합니다.')
 if change=='지급일 연기' and (d<=original_date or amount>original_amount):raise ValueError('연기는 원본보다 늦은 지급일이며 금액 증가가 없어야 합니다.')
 if change=='감량' and (amount>=original_amount or d<original_date):raise ValueError('감량은 감소한 잔여 지급액이며 조기 지급을 포함할 수 없습니다.')
 if change=='취소' and amount!=0:raise ValueError('취소의 잔여 지급액은 0원이어야 합니다.')

def cash_bundle(datasets, config=None):
 from app.formulas import run,context
 datasets=context(datasets,config or {})
 config={**DEFAULT_FINANCE,**(config or {})}
 rows=lambda key:datasets[key]['rows']
 opening_rows=[r for r in rows('cash') if r['date']=='2026-06-30']
 if len(opening_rows)!=1: raise ValueError('현금 기초잔액은 2026-06-30 종가 한 건이어야 합니다.')
 opening=int(opening_rows[0]['closing_balance'])
 purchases={r['po_id']:r for r in rows('purchase')}
 linked=[r for r in rows('ap') if r['po_id']!='NONE']
 missing=[r['ap_id'] for r in linked if r['po_id'] not in purchases]
 mismatch=[r['ap_id'] for r in linked if r['po_id'] in purchases and int(r['amount_krw'])!=int(purchases[r['po_id']]['amount_krw'])]
 overdue=[]
 for kind,key,idkey,datekey,amountkey in [('ar','ar','ar_id','due_date','outstanding_krw'),('ap','ap','ap_id','payment_due_date','amount_krw')]:
  for r in rows(key):
   if kind=='ap' and r['po_id']!='NONE': continue
   if date.fromisoformat(r[datekey])<AS_OF:
    override=config['overrides'].get(kind+':'+r[idkey])
    overdue.append({'id':kind+':'+r[idkey],'kind':kind,'record_id':r[idkey],'original_date':r[datekey],'amount':int(r[amountkey]),'source':datasets[key]['source'],'provenance':datasets[key].get('provenance','원본 사실'),'reply':override})
 results={}
 for sid,(arlabel,aplabel,collect,pay) in SCENARIOS.items():
  flows=defaultdict(int);schedule=[]
  def put(kind,r,idkey,datekey,amountkey,sign,include_overdue):
   raw=date.fromisoformat(r[datekey]); amount=int(r[amountkey]); key=kind+':'+r[idkey]
   reply=config['overrides'].get(key)
   effective=raw;basis='원본 사실';omitted=False
   if reply:
    effective=date.fromisoformat(reply['date']) if reply.get('date') else None
    basis='모의 회신' if reply.get('provenance')=='모의 회신' else '부서 주장'
    omitted=effective is None
   elif raw<AS_OF:
    effective=AS_OF if include_overdue else None;basis='참가자 가정';omitted=effective is None
   if effective and config['weekend_shift']:effective=next_business(effective)
   if effective and effective>=AS_OF:flows[effective]+=sign*amount
   schedule.append({'id':key,'original_date':iso(raw),'adjusted_date':iso(effective) if effective else None,'amount':amount,'direction':'유입' if sign>0 else '지급','provenance':basis,'weekend_policy':'다음 영업일 가정' if config['weekend_shift'] else '원본 일자 유지','excluded':omitted})
  for r in rows('ar'):put('ar',r,'ar_id','due_date','outstanding_krw',1,collect)
  for r in rows('ap'):
   if r['po_id']=='NONE':put('ap',r,'ap_id','payment_due_date','amount_krw',-1,pay)
  for r in rows('purchase'):put('po',r,'po_id','payment_due_date','amount_krw',-1,pay)
  from app.portfolio import cash_orders
  for r in cash_orders(datasets):put('recorded_order',r,'po_id','date','amount',-1,True)
  balance=opening;daily=[];breach=[];calendar=[]
  for i in range(90):
   d=AS_OF+timedelta(days=i);balance+=flows[d]
   item={'date':iso(d),'closing':balance,'net':flows[d],'cash_gap':run(datasets,'cash_gap',threshold=MIN_CASH,closing=balance),'business_day':d.weekday()<5,'provenance':'계산 결과'}
   calendar.append(item)
   if d.weekday()<5:
    daily.append(item)
    if balance<MIN_CASH:breach.append(iso(d))
  weekly=[]
  for f in datasets.get('forecast',{}).get('rows',[]):
   monday=date.fromisoformat(f['week']);end=monday+timedelta(days=4)
   obs=[x for x in calendar if monday<=date.fromisoformat(x['date'])<=end]
   if not obs:continue
   official=int(f['projected_closing_krw']);recalc=obs[-1]['closing']
   weekly.append({'week':f['week'],'official':official,'official_provenance':'부서 주장','recalculated':recalc,'provenance':'계산 결과','difference':run(datasets,'forecast_difference',recalculated=recalc,official=official),'arithmetic_difference':recalc-official,'difference_formula_provenance':'참가자 가정' if 'forecast_difference' in datasets.get('formula_settings',{}).get('entries',{}) else '계산 결과','official_basis':'공식 전망 주차값','recalculated_basis':'해당 주 금요일 일말 잔액','note':'공식 주차 잔액의 마감 정의가 미확인이라 동일 시점 대사에는 재무 확인 필요'})
  results[sid]={'id':sid,'ar_policy':arlabel,'ap_policy':aplabel,'cash_min':min(x['closing'] for x in daily),'first_breach':breach[0] if breach else None,'last_breach':breach[-1] if breach else None,'breach_dates':breach,'daily':daily,'calendar':calendar,'schedule':schedule,'weekly':weekly,'provenance':'계산 결과'}
 union=sorted(set(d for r in results.values() for d in r['breach_dates']))
 selected=config['selected'] if config['selected'] in results else 'exclude_pay'
 valid=bool(config.get('confirmed')) and not missing and not mismatch
 return {'recorded_new_commitments_total':sum(r['amount'] for r in cash_orders(datasets)),'opening':opening,'opening_source':datasets['cash']['source'],'opening_provenance':datasets['cash'].get('provenance','원본 사실'),'purchase_total':sum(int(r['amount_krw']) for r in purchases.values()),'linked_ap_excluded':len(linked),'double_counted_ap':0,'overdue':overdue,'ar_overdue_total':sum(x['amount'] for x in overdue if x['kind']=='ar'),'ap_overdue_total':sum(x['amount'] for x in overdue if x['kind']=='ap'),'scenarios':results,'union_breach_dates':union,'active_breach_dates':results[selected]['breach_dates'] if valid else union,'selected':selected,'confirmed':valid,'config':config,'validation_errors':(['연결 발주 없음: '+', '.join(missing)] if missing else [])+(['AP·발주 금액 불일치: '+', '.join(mismatch)] if mismatch else []),'comparison_notes':[{'text':'7/21 발주 지급 3,749,760,000원과 공식 전망 7/20 주 유출을 대조할 때 누락 가능성이 있으나, 공식 전망의 내부 산정내역이 없어 확정 원인은 아님.','provenance':'계산 결과','certainty':'추정','source':'sc_purchase_orders_ms; fin_cash_forecast_ms'}, {'text':'LC-0001 통보는 45→90일. CH-03 원본 만기는 8/23·8/30·9/6이며, 다음 영업일 가정 적용 시 8/24·8/31·9/7. 마스터의 45일을 다시 적용하거나 원본 만기에 45일을 추가하지 않음.','provenance':'원본 사실','adjustment_provenance':'참가자 가정','source':'lc0001_payment_term_notice.md; fin_ar_aging_ms; m_channel_ms'}]}

def routing(case,bundle):
 if case.get('marketing'):
  from app.marketing import route
  return route()
 assessment=case.get('financial_assessment') or {}
 kind=case.get('approval_type','재고발주');change=assessment.get('change')
 payment_date=assessment.get('payment_date') or case.get('requested_payment_date')
 amount=assessment.get('amount',case.get('requested_amount'))
 reason=[]
 if kind=='재고발주':normal='SCM 전결'
 elif kind=='캠페인집행':
  if amount is None or case.get('proposal_total') is None:return {'authority':'판정 불가','status':'판정 불가','blocked':True,'reason':['건별 금액과 소속 기안 총액 확인 필요'],'provenance':'계산 결과','rule_version':RULES['version']}
  normal='Masil 대표 승인 + 그룹 보고' if int(amount)>10_000_000 or int(case['proposal_total'])>100_000_000 else '마케팅팀 전결'
 else:
  if case.get('annual_amount') is None:return {'authority':'판정 불가','status':'판정 불가','blocked':True,'reason':['연간 계약액 확인 필요'],'provenance':'계산 결과','rule_version':RULES['version']}
  normal='CEO/이사회' if int(case['annual_amount'])>1_000_000_000 else 'Masil 대표 승인'
 # Never infer a missing outflow date, including existing contracts.
 if not payment_date:return {'authority':'판정 불가','status':'판정 불가','blocked':True,'reason':['유출일 미확인 · 재무 확인요청 필요'],'normal':normal,'provenance':'계산 결과','rule_version':RULES['version']}
 if payment_date<iso(AS_OF) or payment_date>iso(AS_OF+timedelta(days=89)):
  return {'authority':'판정 불가','status':'판정 불가','blocked':True,'reason':['유출일이 90일 재전망 범위 밖 · 재전망 갱신 필요'],'normal':normal,'provenance':'계산 결과','rule_version':RULES['version']}
 if bundle['validation_errors']:
  return {'authority':'판정 불가','status':'판정 불가','blocked':True,'reason':bundle['validation_errors'],'normal':normal,'provenance':'계산 결과','rule_version':RULES['version']}
 existing=bool(assessment) and change=='기존 약정'
 reduction=bool(assessment) and change in ['감량','지급일 연기','취소'] and kind=='재고발주'
 uncertain=not bool(assessment)
 new=uncertain or (change in ['추가발주','증량','지급일 앞당김','신규 계약'])
 if existing:reason.append('기존 약정: 하회 원인으로 표시하며 재라우팅하지 않음')
 elif reduction:normal='SCM 전결';reason.append('감량·연기·취소: 기존 의무 변경에 대한 평시 SCM 검토')
 elif new:reason.append('신규 약정' if not uncertain else '신규 여부 미확인: 보수적으로 신규 가능성 검토, 승인 차단')
 dates=set(bundle['active_breach_dates']);effective=next_business(date.fromisoformat(payment_date)) if bundle['config'].get('weekend_shift') else date.fromisoformat(payment_date)
 in_breach=iso(effective) in dates
 # An outflow can cause a new breach even when the pre-commitment baseline has none.
 incremental_breach=False
 if new and amount is not None:
  for sid in ([bundle['selected']] if bundle['confirmed'] else bundle['scenarios']):
   scenario=bundle['scenarios'][sid]
   daily=next((x for x in scenario['calendar'] if x['date']==iso(effective)),None)
   if daily and next_business(effective)<AS_OF+timedelta(days=90):
    nextday=next_business(effective)
    test=next((x for x in scenario['daily'] if x['date']==iso(nextday)),None)
    if test and test['closing']-int(amount)<MIN_CASH:incremental_breach=True
 authority='CEO/이사회' if new and (in_breach or incremental_breach) else normal
 if authority=='CEO/이사회' and new:
  status='CEO 상신 대상' if bundle['confirmed'] else 'CEO 상신 대상(재무 확정 대기)'
  reason.append('확정 시나리오 하회구간 적용' if bundle['confirmed'] else '재무 미확정: 4개 시나리오 하회구간 합집합 적용')
  if incremental_breach and not in_breach:reason.append('증가 유출분을 반영하면 신규 하회 발생 예상')
 else:status='재무 확인 대기' if uncertain or not bundle['confirmed'] else '평시 승인 대상'
 blocked=uncertain or not bundle['confirmed']
 return {'authority':authority,'normal':normal,'status':status,'blocked':blocked,'reason':reason,'payment_date':payment_date,'adjusted_payment_date':iso(effective),'new_commitment':new,'assessment_confirmed':bool(assessment),'scenario':bundle['selected'] if bundle['confirmed'] else '4개 합집합','provenance':'계산 결과','classification_provenance':'내부 통제','rule_version':RULES['version']}

def task_specs(case,bundle):
 tasks=[]
 for r in bundle['overdue']:
  if not r['reply'] or not r['reply'].get('date'):tasks.append({'key':'overdue:'+r['id'],'title':f"연체 {'회수' if r['kind']=='ar' else '지급'}일 확인 · {r['record_id']}",'role':'재무','record_id':r['id'],'provenance':'내부 통제'})
 if case:
  route=routing(case,bundle)
  if route['status']=='판정 불가':tasks.append({'key':'payment','title':'약정 유출일·금액 확인 및 재판정','role':'재무','provenance':'내부 통제'})
  if not case.get('financial_assessment'):tasks.append({'key':'classification','title':'신규약정 여부·유출일 확인','role':'재무','provenance':'내부 통제'})
  if not bundle['confirmed']:
   deadline=case.get('contract_deadline')
   urgent=bool(deadline and deadline<bundle['config'].get('next_review_date','2026-07-08'))
   tasks.append({'key':'forecast','title':'수시 재전망 시나리오 확정 요청' if urgent else '재전망 시나리오 확정 요청','role':'재무','due':deadline if urgent else bundle['config'].get('next_review_date'),'urgent':urgent,'provenance':'내부 통제'})
 return tasks
