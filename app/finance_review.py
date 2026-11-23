"""Screen 3: versioned human finance review, separate from approval execution."""
import copy,hashlib,json
from datetime import timedelta
from pathlib import Path
from app.finance import cash_bundle,routing,validate_commitment
from app.domain import day,number
from app.marketing import text

KINDS=['캠페인집행','재고발주','연간전속계약']
CHANGES=['신규 계약','추가발주','기존 약정','증량','지급일 앞당김','감량','지급일 연기','취소']

def basis(case,data,config):
 # Exclude this review itself; any upstream edit invalidates the packet.
 upstream={k:v for k,v in case.items() if k not in ['finance_review','routing','execution','execution_commands','status','approval','draft','_case_id','id','workflow','operations','operations_commands','demand_review','assistant_proposals']}
 from app.portfolio import context_basis,cash_context
 return hashlib.sha256(json.dumps({'case':upstream,'datasets':{k:v for k,v in data.items() if k!='portfolio'},'portfolio':context_basis(case,data),'other_cash':cash_context(case,data),'finance':config},sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()

def validate(raw,case,data):
 if not isinstance(raw,dict):raise ValueError('재무 검토 형식을 확인하세요.')
 r={k:text(raw.get(k,''),label,True) for k,label in [('decision_maker','재무 담당자'),('reason','검토 사유'),('evidence','검토 근거'),('opinion','재무 의견'),('alternatives','대안 또는 해당 없음 사유')]}
 r['performance_basis']=text(raw.get('performance_basis',''),'성과·비용 근거 또는 미확인 사유',True)
 r['targets']=[];seen=set();linked=set()
 if not isinstance(raw.get('targets'),list):raise ValueError('승인 대상 목록을 확인하세요.')
 for x in raw.get('targets',[]):
  if not isinstance(x,dict):raise ValueError('승인 대상 형식을 확인하세요.')
  ident=text(x.get('id',''),'승인 대상 ID',True,100)
  if ident in seen:raise ValueError('승인 대상 ID가 중복되었습니다.')
  seen.add(ident)
  kind=x.get('kind');change=x.get('change')
  if kind not in KINDS or change not in CHANGES:raise ValueError('승인 유형·약정 분류를 확인하세요.')
  t={'id':ident,'kind':kind,'change':change,'sku_id':x.get('sku_id') or None,'reference_po':x.get('reference_po') or None,'basis':text(x.get('basis',''),'대상별 근거',True),'cash_scope':x.get('cash_scope','미확인'),'payments':[]}
  if t['cash_scope'] not in ['전사 현금 반영 확인','표본·현금 합산 제외','미확인']:raise ValueError('현금 반영 범위를 확인하세요.')
  for key in ['proposal_total','annual_amount']:
   t[key]=None if x.get(key) in ('',None) else number(x[key],key)
  t['deadline']=x.get('deadline') or None
  if t['deadline']:day(t['deadline'])
  if not isinstance(x.get('payments',[]),list):raise ValueError('지급 일정 목록을 확인하세요.')
  for p in x.get('payments',[]):
   if not isinstance(p,dict):raise ValueError('지급 일정 형식을 확인하세요.')
   d=p.get('date') or None
   if d:day(d)
   amount=None if p.get('amount') in ('',None) else number(p['amount'],'지급액')
   t['payments'].append({'date':d,'amount':amount})
  if not t['payments']:t['payments']=[{'date':None,'amount':None}]
  if len(t['payments'])>30:raise ValueError('대상별 지급은 30건 이하입니다.')
  if change not in ['신규 계약','추가발주']:
   if kind!='재고발주' or len(t['payments'])!=1:raise ValueError('기존 발주 변경은 원본 PO별 단일 변경 일정으로 검토하세요.')
   p=t['payments'][0]
   if p['amount'] is None or not p['date']:raise ValueError('기존·변경 약정은 금액·일자를 원본과 대조하세요.')
   if t['reference_po'] in linked:raise ValueError('동일 원본 PO의 중복 변경을 분리 등록할 수 없습니다.')
   linked.add(t['reference_po'])
   original=json.loads((Path(__file__).resolve().parent.parent/'data/seed.json').read_text())['purchase']['rows']
   validate_commitment({'change':change,'reference_po':t['reference_po'],'amount':p['amount'],'payment_date':p['date']},original,t['sku_id'])
  r['targets'].append(t)
 if not 1<=len(r['targets'])<=40:raise ValueError('승인 대상을 1~40건 기록하세요.')
 r['requests']=[]
 if not isinstance(raw.get('requests',[]),list):raise ValueError('확인 요청 목록을 확인하세요.')
 for q in raw.get('requests',[]):
  if not isinstance(q,dict):raise ValueError('확인 요청 형식을 확인하세요.')
  role=q.get('role')
  if role not in ['마케팅','SCM','재무']:raise ValueError('확인 요청 담당자를 선택하세요.')
  r['requests'].append({'role':role,'question':text(q.get('question',''),'확인 질문',True),'answer':text(q.get('answer',''),'회신·근거'),'status':'완료' if text(q.get('answer',''),'회신·근거') else '대기'})
 if len(r['requests'])>40:raise ValueError('확인 요청은 40건 이하입니다.')
 return r

def related_influencer(case):
 from app.performance import for_case
 return case.get('marketing',{}).get('influencer_id') or (for_case(case).get('sample') or {}).get('influencer_id')

def initial_review(case):
 """Unsaved review inputs from the submitted plan/SCM; never an approval."""
 p=case.get('marketing')
 if not p:return None
 settlement=p.get('settlement_date') or (p.get('settlement_draft') or {}).get('date')
 settlement_basis='마케팅 기안 요청값 · 재무 확인 전'
 if not p.get('settlement_date') and settlement:settlement_basis+=' · 예측 지급일 '+settlement+' · '+(p.get('settlement_draft') or {}).get('basis','')
 targets=[{'id':'campaign','kind':'캠페인집행','change':'신규 계약','sku_id':None,'reference_po':None,'proposal_total':p.get('group_total') or p.get('budget'),'annual_amount':None,'deadline':p.get('contract_deadline'),'basis':settlement_basis,'cash_scope':'표본·현금 합산 제외','payments':[{'date':settlement,'amount':p.get('budget')}]}]
 for i in case.get('scm',{}).get('review',{}).get('items',[]):
  if i.get('procurement') not in ['신규 발주 검토','기존 발주 변경']:continue
  qty=i.get('requested_qty');price=i.get('requested_unit_price')
  targets.append({'id':'po-'+i['sku_id'],'kind':'재고발주','sku_id':i['sku_id'],'reference_po':i.get('reference_po'),'change':'증량' if i['procurement']=='기존 발주 변경' else '추가발주','proposal_total':None,'annual_amount':None,'basis':i.get('note') or 'SCM 발주안 · 재무 확인 전','cash_scope':'미확인','payments':[{'date':i.get('requested_payment_date'),'amount':qty*price if qty is not None and price is not None else None}]})
 return {'decision_maker':'','reason':'','evidence':'','opinion':'','alternatives':'','performance_basis':'','requests':[],'targets':targets}

def view(case,data,config,review=None):
 r=review or case.get('finance_review',{});bundle=cash_bundle(data,config);routes=[]
 from app.portfolio import without_own_orders,cash_orders
 route_bundle=cash_bundle(without_own_orders(case,data),config)
 scenarios=copy.deepcopy(bundle['scenarios'])
 additions={};errors=[]
 for t in r.get('targets',[]):
  total=sum(p['amount'] or 0 for p in t['payments'])
  for i,p in enumerate(t['payments']):
   fake={'approval_type':t['kind'],'proposal_total':t['proposal_total'],'annual_amount':t['annual_amount'],'requested_amount':total}
   # Campaign threshold is the whole target, never an installment.
   fake['financial_assessment']={'change':t['change'],'amount':total,'payment_date':p['date']}
   route=routing(fake,route_bundle)
   if t['cash_scope']!='전사 현금 반영 확인' and route.get('new_commitment') and route.get('adjusted_payment_date') not in bundle['active_breach_dates'] and route.get('normal'):
    route.update(authority=route['normal'],status='재무 확인 대기' if not bundle['confirmed'] else '평시 승인 대상')
    route['reason']=[x for x in route['reason'] if '신규 하회' not in x]

   if p['amount'] is None or not p['date']:route.update(status='판정 불가',blocked=True,reason=['유출일·금액 미확인'])
   routes.append({'id':t['id'],'installment':i+1,'kind':t['kind'],'payment':p,'route':route,'basis':t['basis'],'cash_scope':t['cash_scope']})
   if t['cash_scope']=='미확인':errors.append(t['id']+' 현금 반영 범위 미확인')
   if route['blocked']:
    label='캠페인 집행비' if t['kind']=='캠페인집행' else '발주대금 '+(t.get('sku_id') or t['id']) if t['kind']=='재고발주' else t['id']
    reasons=' / '.join(route.get('reason') or [route['status']])
    if any('전망 범위 밖' in why for why in route.get('reason',[])):
     calendar=next(iter(bundle['scenarios'].values()))['calendar']
     errors.append(label+' 지급예정일 '+str(p['date'])+'은 현금 전망 기간('+calendar[0]['date']+' ~ '+calendar[-1]['date']+') 밖입니다. 해당 지급일까지 현금 전망·근거 자료를 갱신한 후 다시 상신하세요. 재무 확인만으로 미래 잔액을 확정할 수 없습니다.')
    else:errors.append(label+' · '+reasons)
   if t['change'] in ['신규 계약','추가발주'] and t['cash_scope']=='전사 현금 반영 확인' and p['date'] and p['amount'] is not None:
    from app.finance import next_business
    d=next_business(day(p['date'])).isoformat() if config.get('weekend_shift') else p['date']
    # A transmitted own order is already in the shared baseline: replace, never add twice.
    own=next((o for o in case.get('execution',{}).get('orders',[]) if o['target_id']==t['id']),None)
    recorded=next((o for o in cash_orders(data,case) if own and o['po_id']==own['po_id']),None)
    if recorded:
     original=next_business(day(recorded['date'])).isoformat() if config.get('weekend_shift') else recorded['date']
     additions[original]=additions.get(original,0)-recorded['amount']
    additions[d]=additions.get(d,0)+p['amount']
   elif t['change'] not in ['기존 약정','신규 계약','추가발주']:
    # Replace original schedule, never subtract the whole PO twice.
    po=next((p for p in data['purchase']['rows'] if p['po_id']==t['reference_po']),None)
    if po and t['cash_scope']=='전사 현금 반영 확인' and p['date']:
     from app.finance import next_business
     effective=lambda d:next_business(day(d)).isoformat() if config.get('weekend_shift') else d
     additions[effective(po['payment_due_date'])]=additions.get(effective(po['payment_due_date']),0)-int(po['amount_krw'])
     additions[effective(p['date'])]=additions.get(effective(p['date']),0)+(p['amount'] or 0)
 for s in scenarios.values():
  cumulative=0;s['impact_daily']=[]
  for d in s['calendar']:
   cumulative+=additions.get(d['date'],0)
   if d['business_day']:s['impact_daily'].append({**d,'closing':d['closing']-cumulative})
  s['impact_min']=min(d['closing'] for d in s['impact_daily'])
  s['weekly_min']=[]
  for w in s['weekly']:
   start=day(w['week']);end=start+timedelta(days=4)
   rows=[d for d in s['daily'] if start<=day(d['date'])<=end]
   imp=[d for d in s['impact_daily'] if start<=day(d['date'])<=end]
   if rows:s['weekly_min'].append({**w,'minimum':min(d['closing'] for d in rows),'impact_minimum':min(d['closing'] for d in imp),'days':len(rows)})
 # Combined additions may create a breach even when individual targets do not.
 chosen=[scenarios[bundle['selected']]] if bundle['confirmed'] else list(scenarios.values())
 impact_breach={d['date'] for s in chosen for d in s['impact_daily'] if d['closing']<3000000000}
 for line in routes:
  t=next(t for t in r.get('targets',[]) if t['id']==line['id'])
  if line['route'].get('new_commitment') and line['route'].get('adjusted_payment_date') in impact_breach:
   line['route'].update(authority='CEO/이사회')
 errors+=['확인 요청 회신 대기'] if any(q['status']=='대기' for q in r.get('requests',[])) else []
 scm=case.get('scm',{}).get('review',{})
 if case.get('marketing') and (case.get('marketing_stage') not in ['재무 검토 요청','재무 검토 중','재무 상신 완료'] or not scm.get('valid') or __import__('app.scm',fromlist=['stale']).stale(case,data)):errors.append('② SCM 인계·유효 검토 필요')
 plan=case.get('marketing',{})
 if plan.get('budget') is not None:
  campaigns=[t for t in r.get('targets',[]) if t['kind']=='캠페인집행']
  if len(campaigns)!=1 or sum(p['amount'] or 0 for t in campaigns for p in t['payments'])!=plan['budget']:errors.append('캠페인 집행 대상·요청액 대조 필요')
  elif campaigns[0].get('proposal_total') is None or campaigns[0]['proposal_total']<(plan.get('group_total') or plan['budget']):errors.append('소속 기안 총액·근거 대조 필요')
  expected={i['sku_id'] for i in case.get('scm',{}).get('review',{}).get('items',[]) if i['procurement']=='신규 발주 검토'}
  actual=[t['sku_id'] for t in r.get('targets',[]) if t['kind']=='재고발주' and t['change']=='추가발주']
  if set(actual)!=expected or len(actual)!=len(expected):errors.append('SCM 신규 발주 대상 누락·중복 대조 필요')
 valid=bool(r.get('basis') and r['basis']==basis(case,data,config))
 return {'performance':__import__('app.performance',fromlist=['for_case']).for_case(case),'routes':routes,'scenarios':scenarios,'selected':bundle['selected'],'confirmed':bundle['confirmed'],'errors':sorted(set(errors)),'valid':valid,'basis':basis(case,data,config),'source_versions':{k:v.get('version') for k,v in data.items()},'recommendation':__import__('app.finance_advice',fromlist=['advise']).advise(case,r,routes,scenarios,bundle['selected'],bundle['confirmed'],sorted(set(errors))),'related_contract':{'id':'INF-001','annual_fixed_fee':2800000000,'deadline':'2026-07-17','authority':'CEO/이사회','source':'02_masil/marketing/inf001_exclusive_contract_notice.md','note':'성과 피 별도. 미통보 자동 갱신. 지급 스케줄 미확인. 캠페인 부결과 별도.'} if related_influencer(case)=='INF-001' else None}

def task_specs(case):
 r=case.get('finance_review',{});out=[]
 if related_influencer(case)=='INF-001' and case.get('marketing_stage')!='작성 중' and not case.get('execution',{}).get('obligations',{}).get('contract_notice'):out.append({'key':'finance:contract:INF-001','role':'마케팅','title':'INF-001 전속계약 별도 승인·7/17 통보 대응 증빙 확인 · 캠페인 상신과 별도','due':'2026-07-17','provenance':'내부 통제'})
 for i,q in enumerate(r.get('requests',[])):
  if q['status']=='대기':out.append({'key':'finance:request:'+str(i),'role':q['role'],'title':q['question'],'provenance':'내부 통제'})
 if r.get('operation')=='submit':out.append({'key':'finance:approval','role':'승인권자','title':'재무 상신 자료 확인 · 약정별 사람 승인','provenance':'내부 통제'})
 return out
