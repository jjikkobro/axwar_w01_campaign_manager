"""Versioned, role-owned arithmetic models. No Python eval or approval actions."""
import ast,copy,hashlib,json,math,operator
from functools import lru_cache
from decimal import Decimal,ROUND_HALF_UP

def krw(x):return int(Decimal(str(x)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
FUNCTIONS={'min':min,'max':max,'abs':abs,'ceil':math.ceil,'floor':math.floor,'round_krw':krw}
BINARY={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}

def spec(title,role,stage,expr,variables,example,unit,source,negative=False):
 return dict(title=title,roles=role.split('/'),stage=stage,default=expr,variables=variables,example=example,unit=unit,source=source,negative=negative)
CATALOG={
 'marketing_fixed_budget':spec('마케팅 고정비 예상','마케팅','① 기안 · ③ 재무 · ④ 승인','round_krw(reference_fixed)',{'reference_fixed':'비교 캠페인의 포함 인플루언서비 중앙값 · 원'},{'reference_fixed':10000000},'원','mkt_ad_spend_ms: fee는 ad_cost에 이미 포함. 표본 기반 참가자 가정'),
 'marketing_variable_budget':spec('마케팅 기간비 예상','마케팅','① 기안 · ③ 재무 · ④ 승인','round_krw(reference_daily * campaign_days)',{'reference_daily':'(ad_cost−포함 fee)/캠페인일수의 중앙값 · 원/일','campaign_days':'새 캠페인 시작~종료 포함 · 일'},{'reference_daily':100000,'campaign_days':7},'원','mkt_ad_spend_ms, m_campaign_ms; 달력일 비례는 참가자 가정'),
 'marketing_execution_budget':spec('캠페인 마케팅 집행 예산','마케팅/재무','① 기안 · ③ 재무 · ④ 승인','round_krw(fixed_budget + variable_budget + other_cost)',{'fixed_budget':'선택 매체 고정비 합계 · 원','variable_budget':'선택 매체 기간비 합계 · 원','other_cost':'직접 반영한 별도 마케팅비 · 원'},{'fixed_budget':10000000,'variable_budget':700000,'other_cost':0},'원','마케팅 예상비만 합산. 상품 조달비·포함 influencer_fee 재가산 금지'),
 'campaign_total_requirement':spec('마케팅·상품 조달 참고 합계','마케팅/재무','① 기안 · ② SCM · ③ 재무 · ④ 승인','round_krw(marketing_budget + procurement_budget)',{'marketing_budget':'담당자가 입력·채택한 마케팅 집행 예산 · 원','procurement_budget':'별도 상품 조달 예상비 · 원'},{'marketing_budget':10700000,'procurement_budget':5000000},'원','서로 다른 규모의 참고 합계. 규모 확인 전 확정 현금/손익으로 사용 금지'),

 'lead_time_days':spec('입고 리드타임 일수','SCM','① 기안 · ② SCM · ③ 재무 · ④ 승인 · ⑤ 발주 · ⑥ 회신 · ⑦ 일정','lead_weeks * 7',{'lead_weeks':'원본 SKU 리드타임 · 주'},{'lead_weeks':6},'일','m_sku_ms; 원본 주 단위를 달력일로 환산. 계획에만 사용하며 확정 회신일은 보존'),
 'replenishment_trigger':spec('리드타임 반영 발주점','SCM','① 기안 · ② SCM','weekly * (lead_weeks + review_weeks + safety_weeks)',{'weekly':'완료 4주 평균 · EA/주','lead_weeks':'원본 SKU 리드타임 · 주','review_weeks':'다음 검토까지 · 1주','safety_weeks':'원본 최소 안전재고 · 주'},{'weekly':1000,'lead_weeks':6,'review_weeks':1,'safety_weeks':4},'EA','사용자 지정: 리드타임+1주 후 예상 재고가 안전재고 이하이면 이번 주 주문 · 참가자 가정'),
 'replenishment_target':spec('리드타임 반영 보충 목표','SCM','① 기안 · ② SCM','weekly * (lead_weeks + safety_weeks)',{'weekly':'완료 4주 평균 · EA/주','lead_weeks':'원본 SKU 리드타임 · 주','safety_weeks':'원본 최대 안전재고 · 주'},{'weekly':1000,'lead_weeks':6,'safety_weeks':6},'EA','calculation_definitions §1.3, m_sku_ms; 목표는 리드타임+최대 안전재고인 참가자 가정'),
 'weekly_average':spec('완료 주간 평균 판매','마케팅','① 기안 · ② SCM','sales_total / weeks_count',{'sales_total':'완료 4주 판매 합계 · EA','weeks_count':'완료 주 수 · 주'},{'sales_total':4000,'weeks_count':4},'EA/주','app/domain.py · app/portfolio.py; sku_weekly_sales_ms'),
 'campaign_daily':spec('캠페인 일별 추가 수요','마케팅','① 기안 · ② SCM · ⑥ 회신','total_quantity / duration_days',{'total_quantity':'입력 수요의 기간 전체 환산량 · EA','duration_days':'시작~종료 포함 일수 · 일'},{'total_quantity':12000,'duration_days':7},'EA/일','app/domain.py · app/portfolio.py; 마케팅 SKU 수요 가정'),
 'baseline_daily':spec('기본 일별 판매','SCM','② SCM · ⑥ 회신','weekly / 7',{'weekly':'계산된 주간 평균 · EA/주'},{'weekly':1000},'EA/일','app/domain.py · app/portfolio.py; 일별 균등 배분 가정'),
 'inventory_cover':spec('현재고 커버','SCM','② SCM','on_hand / weekly',{'on_hand':'현재고 · EA','weekly':'주간 평균 판매 · EA/주'},{'on_hand':3000,'weekly':1000},'주','calculation_definitions.md; app/domain.py'),
 'campaign_cover':spec('추가 수요 반영 커버','SCM','② SCM','on_hand / (weekly + weekly_extra)',{'on_hand':'현재고 · EA','weekly':'주간 평균 · EA/주','weekly_extra':'추가 수요 주간 환산 · EA/주'},{'on_hand':3000,'weekly':1000,'weekly_extra':500},'주','app/domain.py; 캠페인 수요는 참가자 가정'),
 'safety_target':spec('안전재고 참고량','SCM','② SCM','weekly * safety_weeks',{'weekly':'주간 평균 · EA/주','safety_weeks':'원본 최소 안전재고 주수 · 주'},{'weekly':1000,'safety_weeks':3},'EA','m_sku_ms · app/domain.py'),
 'ax_replenishment_gap':spec('기안 예측 재고 보충량','SCM','① 기안 사전검토 · ② SCM','max(safety_target - minimum_projected, 0)',{'safety_target':'안전재고 참고량 · EA','minimum_projected':'캠페인 기간 최소 예상 재고 · EA (음수 가능)'},{'safety_target':12000,'minimum_projected':3000},'EA','app/ax_planning.py; 예측 모델 가정, 확인 입고·타 캠페인 수요 포함'),
 'procurement_gap':spec('목표 대비 부족 수량','SCM','② SCM','max(target - on_hand - in_transit, 0)',{'target':'담당자 입력 목표 · EA','on_hand':'현재고 · EA','in_transit':'운송 중 · EA (목표 대비 계산에만 사용)'},{'target':10000,'on_hand':3000,'in_transit':1000},'EA','app/scm.py; 실제 입고 계산은 확인 회신만 사용'),
 'procurement_moq':spec('MOQ 반영 제안량','SCM','② SCM','max(gap, moq)',{'gap':'양수 부족 수량 · EA','moq':'원본 최소 발주량 · EA'},{'gap':6000,'moq':10000},'EA','app/scm.py; 0일 때 제안량 0, 원본 MOQ 미만 금지'),
 'purchase_amount':spec('발주안 예상 금액','SCM/재무','② SCM · ③ 재무','round_krw(qty * unit_price)',{'qty':'SCM 검토 발주 수량 · EA','unit_price':'검토 단가 · 원/EA'},{'qty':16000,'unit_price':12600},'원','app/scm.py; 승인·전달 금액은 승인 수량×단가로 별도 대조'),
 'cash_gap':spec('30억 기준 부족액','재무','③ 재무','max(threshold - closing, 0)',{'threshold':'고정 약정 기준 · 원','closing':'재계산 일말 잔액 · 원'},{'threshold':3000000000,'closing':1467664440},'원','covenant_terms_ms.md; 참고 계산이며 하회 여부·결재선 변경 불가'),
 'forecast_difference':spec('공식 전망과의 차이','재무','③ 재무','recalculated - official',{'recalculated':'해당 주 금요일 재계산 잔액 · 원','official':'부서 공식 전망 주차값 · 원'},{'recalculated':1467664440,'official':5469000000},'원','fin_cash_forecast_ms; 마감 정의 미확인',True),
}
LOCKED=[
 {'title':'일별 재고 수지','expression':'전일 재고 + 확인 입고 − 기본 판매 − 검토 수요 − 타 캠페인 승인 수요','source':'app/domain.py · app/portfolio.py','reason':'실제 수지와 승인 수요를 보존하는 고정 통제'},
 {'title':'일별 현금 수지','expression':'전일 잔액 + AR 회수 − AP(po_id=NONE) − 기존 PO 지급 − 신규 지급','source':'calculation_definitions.md §1.2','reason':'PO 연결 AP 중복 차감 금지 · 표본 캠페인 금액 합산 금지'},
 {'title':'하회 및 결재선','expression':'영업일 일말 30억 미만 · 구간 내 신규 약정은 CEO/이사회','source':'covenant_terms_ms.md · approval_authority_policy.md','reason':'AI·시스템의 자동 승인 금지. 규정 변경은 별도 검토'},
 {'title':'수요 단위 환산','expression':'EA/주 × 적용일수 ÷ 7 또는 기간 전체 EA','source':'app/marketing.py','reason':'단위 변환 · 미입력 수요는 0으로 확정하지 않음'},
 {'title':'발주 전달 승인 범위','expression':'승인 수량 × 단가 = 승인 금액 · 승인 지급일 일치','source':'app/execution.py','reason':'수정한 예상 금액이 승인 범위를 자동 변경하지 않음'},
 {'title':'표본 성과 지표','expression':'명목 ROAS = GMV / 마케팅비 · 실질 ROAS = 공헌이익 / 마케팅비 · 반품률 = 환불액 / GMV','source':'app/performance.py · 원본 표본 거래/비용','reason':'원본 표본의 고정 비교 지표. 회사 전체 SKU 수요로 환산하지 않음'},
 {'title':'발주 일정 가정','expression':'계획 미입력 시 기준일 + 공통 리드타임 일수 · 회신기한 3영업일','source':'app/planning.py','reason':'가정으로 표시하며 발주서에서 담당자가 직접 날짜 수정. 지급일 자동 추정 금지'},
 {'title':'성과·종료 판정','expression':'검토 회차 종료 ≠ 실제 입고·판매·지급 완료','source':'W01 · app/execution.py · app/operations.py','reason':'성과 표본 원본 지표와 업무 종료 조건을 보존'},
]

PAGES=['마케팅 기획','SCM 검토','재무 검토','승인 근거','SCM 발주','입고 회신 검산','마케팅 일정','통합 SKU 계획']
def consumers(key):
 return ['재무 검토','공식 전망 비교'] if key in ['cash_gap','forecast_difference'] else PAGES

def entries(data):return data.get('formula_settings',{}).get('entries',{})
def token(data):
 # Include defaults as well as overrides: a newly added/changed formula is a model change.
 effective={k:entries(data).get(k,{}).get('expression',v['default']) for k,v in CATALOG.items()}
 return hashlib.sha256(json.dumps({'engine':'W01-SHARED-PLANNING-1','expressions':effective},sort_keys=True).encode()).hexdigest()

def revision(data,config):
 return {'formula_revision':token(data),'revision':hashlib.sha256(json.dumps({'formula':token(data),'datasets':{k:v.get('version') for k,v in data.items() if k not in ['formula_settings','portfolio']},'finance_version':config.get('version'),'shared_supply':[{k:r.get(k) for k in ['case_id','reservation','receipts','orders','receipt','withdrawn']} for r in sorted(data.get('portfolio',{}).get('rows',[]),key=lambda r:r['case_id'])]},sort_keys=True,default=str).encode()).hexdigest(),'model':'W01-SHARED-PLANNING-1'}

@lru_cache(maxsize=256)
def parse(key,expression):
 if key not in CATALOG:raise ValueError('수정 가능한 산식을 선택하세요.')
 if not isinstance(expression,str) or not 1<=len(expression.strip())<=300:raise ValueError('산식은 1~300자입니다.')
 try:root=ast.parse(expression.strip(),mode='eval')
 except (SyntaxError,RecursionError):raise ValueError('산식 문법을 확인하세요.')
 nodes=list(ast.walk(root))
 if len(nodes)>80:raise ValueError('산식이 너무 복잡합니다.')
 for n in nodes:
  if isinstance(n,ast.Name):
   if n.id not in CATALOG[key]['variables'] and n.id not in FUNCTIONS:raise ValueError('사용할 수 없는 변수: '+n.id)
  elif isinstance(n,ast.Call):
   if not isinstance(n.func,ast.Name) or n.func.id not in FUNCTIONS or n.keywords or not 1<=len(n.args)<=8:raise ValueError('허용된 함수만 사용할 수 있습니다.')
  elif isinstance(n,ast.Constant):
   if type(n.value) not in [int,float] or not math.isfinite(n.value) or abs(n.value)>1e15:raise ValueError('유한한 숫자 상수만 사용할 수 있습니다.')
  elif not isinstance(n,(ast.Expression,ast.BinOp,ast.UnaryOp,ast.Load,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.UAdd,ast.USub)):raise ValueError('사칙연산·변수·허용 함수만 사용할 수 있습니다.')
 return root.body

def evaluate(key,expression,values):
 if not isinstance(key,str) or key not in CATALOG or not isinstance(expression,str):raise ValueError('산식 이름·표현식을 확인하세요.')
 if not isinstance(values,dict):raise ValueError('시험 변수는 숫자 항목으로 입력하세요.')
 root=parse(key,expression)
 if set(values)!=set(CATALOG[key]['variables']):raise ValueError('시험 변수 목록을 확인하세요.')
 if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e15 for v in values.values()):raise ValueError('변수는 유한한 숫자여야 합니다.')
 def bounded(v):
  if not math.isfinite(v) or abs(v)>1e15:raise ValueError('계산 결과가 허용 범위를 벗어났습니다.')
  return v
 def walk(n):
  if isinstance(n,ast.Constant):return n.value
  if isinstance(n,ast.Name):return values[n.id]
  if isinstance(n,ast.UnaryOp):return bounded((-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand))
  if isinstance(n,ast.BinOp):return bounded(BINARY[type(n.op)](walk(n.left),walk(n.right)))
  return bounded(FUNCTIONS[n.func.id](*(walk(a) for a in n.args)))
 try:result=bounded(walk(root))
 except (ZeroDivisionError,OverflowError,TypeError,KeyError,ValueError) as e:raise ValueError('산식 계산 실패: '+str(e))
 if result<0 and not CATALOG[key]['negative']:raise ValueError('이 산식의 결과는 음수일 수 없습니다.')
 if key=='procurement_moq' and result<values['moq']:raise ValueError('원본 MOQ보다 작게 제안할 수 없습니다.')
 if key in ['purchase_amount','marketing_fixed_budget','marketing_variable_budget','marketing_execution_budget','campaign_total_requirement'] and result!=int(result):raise ValueError('발주안 금액은 정수 원 단위여야 합니다.')
 return result

def run(data,key,**values):return evaluate(key,entries(data).get(key,{}).get('expression',CATALOG[key]['default']),values)
def context(data,config):
 e=config.get('formulas',{})
 if not e:return data
 return {**data,'formula_settings':{'entries':e,'rows':[],'source':'역할별 산식 설정','provenance':'참가자 가정','version':hashlib.sha256(json.dumps(e,sort_keys=True).encode()).hexdigest()}}

def catalog(config,role):
 return [{'id':k,**v,'consumers':consumers(k),'expression':config.get('formulas',{}).get(k,{}).get('expression',v['default']),'custom':k in config.get('formulas',{}),'editable':role in v['roles'],'last_change':config.get('formulas',{}).get(k)} for k,v in CATALOG.items()]

def candidate(config,raw,role):
 key=raw.get('formula_id');expression=raw.get('expression')
 if not isinstance(key,str) or key not in CATALOG or role not in CATALOG[key]['roles']:raise ValueError('현재 역할은 이 산식을 수정할 수 없습니다.')
 for k in ['decision_maker','reason','evidence']:
  if not isinstance(raw.get(k),str) or not 1<=len(raw[k].strip())<=4000:raise ValueError('수정자·사유·근거를 입력하세요.')
 evaluate(key,expression,CATALOG[key]['example'])
 f=copy.deepcopy(config);f.pop('version',None);f.setdefault('formulas',{})
 if expression.strip()==CATALOG[key]['default']:f['formulas'].pop(key,None)
 else:f['formulas'][key]={'expression':expression.strip(),'role':role,**{k:raw[k].strip() for k in ['decision_maker','reason','evidence']},'provenance':'참가자 가정'}
 f['confirmed']=False
 return f

def preview_key(config,raw,role):return hashlib.sha256(json.dumps([config['version'],role,raw.get('formula_id'),raw.get('expression'),raw.get('decision_maker'),raw.get('reason'),raw.get('evidence')],ensure_ascii=False).encode()).hexdigest()

def impact(config,raw,role,data,cases):
 """Recalculate the real cases without saving decisions or records."""
 from app.domain import calculate
 from app.scm import analysis
 from app.finance import cash_bundle
 proposed=candidate(config,raw,role);newdata=context({k:v for k,v in data.items() if k!='formula_settings'},proposed)
 changes=[]
 for cid,b in cases:
  if not b.get('marketing') or b.get('execution',{}).get('closed'):continue
  before=analysis(b,data,config);after=analysis(b,newdata,proposed)
  def summary(result):return [{'sku_id':i['sku_id'],'weekly':i['weekly'],'cover':i['cover'],'campaign_min':i['campaign_min'],'proposed_qty':i['procurement']['effective_proposal_qty'],'estimated_amount':i['procurement']['estimated_amount']} for i in result['items']]
  from app.marketing_cost import estimate as marketing_estimate
  p=b['marketing'];raw_cost=b.get('ax_plan',{}).get('inputs',{}).get('marketing_cost_inputs') or {'media':p.get('media',[]),'product_line':p.get('target'),'country':p.get('country'),'platform':p.get('sns_channel'),'sns_format':p.get('sns_format'),'influencer_id':p.get('influencer_id'),'other_cost':0}
  cost_before=marketing_estimate(raw_cost,data,p['as_of'],p['start'],p['end'])
  cost_after=marketing_estimate(raw_cost,newdata,p['as_of'],p['start'],p['end'])
  changes.append({'id':cid,'title':b['title'],'before':summary(before),'after':summary(after),'marketing_budget_before':cost_before['recommended_budget'],'marketing_budget_after':cost_after['recommended_budget'],'planning_before':before['planning']['items'],'planning_after':after['planning']['items'],'recheck_required':True})
 # Exercise financial diagnostics under all four scenarios as well.
 cash=cash_bundle(newdata,proposed);oldcash=cash_bundle(data,config)
 diagnostics=[]
 for sid,scenario in cash['scenarios'].items():
  old=oldcash['scenarios'][sid]
  diagnostics.append({'scenario':sid,'gap_before':max(d['cash_gap'] for d in old['daily']),'gap_after':max(d['cash_gap'] for d in scenario['daily']),'weekly_difference_before':[{'week':w['week'],'difference':w['difference']} for w in old['weekly']],'weekly_difference_after':[{'week':w['week'],'difference':w['difference']} for w in scenario['weekly']]})
 return {'candidate':proposed,'cases':changes,'diagnostics':diagnostics,'cash_min':{k:v['cash_min'] for k,v in cash['scenarios'].items()},'sample_result':evaluate(raw['formula_id'],raw['expression'],raw.get('sample_values',CATALOG[raw['formula_id']]['example'])),'note':'적용하면 진행 건은 새 산식 기준 재검토합니다. 기존 승인 기록은 보존하되 재사용하지 않습니다. 완료 기록은 보존합니다.'}
