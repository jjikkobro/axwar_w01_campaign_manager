"""Evidence-based demand review, two-department consultation and lasting follow-ups."""
import copy
from datetime import date,timedelta
from app.marketing import text,case_from
from app.portfolio import legacy_reservation
from app.formulas import run
from app.demand import assess,basis as demand_basis,signature

def consultation_basis(case):
 return signature({'plan':case.get('marketing'),'scm':case.get('scm',{}).get('review'),'finance_targets':case.get('finance_review',{}).get('targets')})
def consultation(case):
 c=case.get('operations',{}).get('consultation')
 if not c:return {'required':False,'ready':True}
 current=c['basis']==consultation_basis(case)
 return {**c,'required':True,'current':current,'ready':bool(current and c.get('resolution')),'state':'해결' if current and c.get('resolution') else '재확인 필요' if not current else '협의 중'}
def require_agreement(case):
 c=consultation(case)
 if c['required'] and not c['ready']:raise ValueError('SCM·재무 협의가 미완료이거나 검토 근거가 변경되었습니다. 두 부서 회신과 SCM의 합의 기록이 필요합니다.')
def pending_adjustment(case):
 return next((r for r in reversed(case.get('operations',{}).get('adjustments',[])) if r.get('status')=='대기'),None)
def complete_adjustment(case,role,at):
 request=pending_adjustment(case)
 if request and request['target']==role:request.update(status='처리 완료',completed_at=at,completion='해당 부서 검토·인계 기록')
def detect_disagreement(case,actor,at):
 if case.get('operations',{}).get('consultation'):return
 r=case.get('scm',{}).get('review',{});f=case.get('finance_review',{})
 mismatch=r.get('direction')=='공급 불가' and f.get('opinion') in ['승인','조건부 승인']
 if mismatch:
  case.setdefault('operations',{})['consultation']={'basis':consultation_basis(case),'subject':'SCM 공급 불가와 재무 추진 의견의 상충','alternatives':[{'id':'revise','title':'기간·판매량·상품 구성/조달 조건 재검토','marketing_effect':'캠페인 조건 변경 검토','scm_effect':'공급 확인 후 재대조','finance_effect':'유출일·금액·권한 재판정','provenance':'내부 통제 · 확인 요청'}],'replies':{},'opened_by':actor,'opened_at':at,'provenance':'계산 결과 · 불일치 감지'}
def performance(case,data,review_date):
 p=case.get('marketing',{});reservation=case.get('execution',{}).get('reservation') or {};out=[];missing=[]
 for item in p.get('items',[]):
  sid=item['sku_id'];start=date.fromisoformat(item['start']);end=date.fromisoformat(item['end']);w=start-timedelta(days=start.weekday())
  baseline=reservation.get('baselines',{}).get(sid)
  if baseline is None:
   hist=[r for r in data['sales']['rows'] if r['sku_id']==sid and date.fromisoformat(r['week'])+timedelta(days=7)<=date.fromisoformat(p['as_of'])]
   hist=sorted(hist,key=lambda r:r['week'])[-4:];baseline=run(data,'weekly_average',sales_total=sum(float(r['sold_qty']) for r in hist),weeks_count=len(hist)) if hist else None
  while w<=end:
   d=w.isoformat();actual=next((r for r in data['sales']['rows'] if r['sku_id']==sid and r['week']==d),None)
   if w+timedelta(days=7)>date.fromisoformat(review_date) or actual is None or baseline is None:missing.append(sid+' '+d+' 완료 주 실적/기초 판매 미확인')
   else:
    overlap=max(0,(min(w+timedelta(days=6),end)-max(w,start)).days+1);extra=run(data,'campaign_daily',total_quantity=float(item['total_quantity']),duration_days=(end-start).days+1)*overlap;expected=baseline+extra
    actual_qty=float(actual['sold_qty']);out.append({'sku_id':sid,'week':d,'baseline':baseline,'campaign_assumption':extra,'expected_company_qty':expected,'actual_company_qty':actual_qty,'difference':actual_qty-expected,'absolute_error':abs(actual_qty-expected),'source':data['sales']['source'],'data_version':data['sales'].get('version')})
   w+=timedelta(days=7)
 return {'ready':bool(out) and not missing,'rows':out,'missing':missing,'review_date':review_date,'provenance':'계산 결과','limitation':'회사 전체 SKU 주 판매와 기초+해당 검토 건 가정의 검산. 다른 캠페인·계절성 포함이며 캠페인의 인과 성과로 귀속하지 않음.'}
def apply(case,data,config,raw,role,metadata):
 b=copy.deepcopy(case);op=raw.get('operation');m=metadata(raw);o=b.setdefault('operations',{})
 if not b.get('marketing'):raise ValueError('마케팅 검토 건을 선택하세요.')
 legacy=legacy_reservation(b)
 if legacy and b.get('execution',{}).get('reservation') is None:b.setdefault('execution',{})['reservation']=legacy
 if op=='adjust_request':
  from app.execution import projection
  if role not in ['마케팅','SCM','재무','승인권자']:raise ValueError('캠페인 담당 역할을 확인하세요.')
  target=raw.get('target')
  if target not in ['마케팅','SCM','재무'] or target==role:raise ValueError('조정할 다른 담당 부서를 선택하세요.')
  if pending_adjustment(b):raise ValueError('진행 중인 조정 요청을 먼저 처리하세요.')
  if b.get('execution',{}).get('orders') or b.get('execution',{}).get('closed'):raise ValueError('발주 전달 또는 종료 후에는 기존 발주를 유지하고 별도 변경 기안으로 조정하세요.')
  if target=='재무' and not b.get('scm',{}).get('review',{}).get('valid'):raise ValueError('SCM 검토를 먼저 완료한 후 재무에 요청하세요.')
  stage=projection(b,data,config)['stage']
  o.setdefault('adjustments',[]).append({**m,'from_role':role,'target':target,'source_stage':stage,'status':'대기','provenance':'부서 요청 · 기존 기록 보존'})
  if b.get('finance_review'):b.setdefault('finance_review_history',[]).append(b.pop('finance_review'))
  if target in ['마케팅','SCM']:
   from app.scm import invalidate
   invalidate(b,'조정 요청 · '+m['reason'])
  b['marketing_stage']={'마케팅':'작성 중','SCM':'SCM 검토 요청','재무':'재무 검토 요청'}[target];b['status']='재검토 필요';b['approval']=None
 elif op=='update_demand':
  if role not in ['마케팅','SCM']:raise ValueError('마케팅 또는 SCM이 수요 가정을 보완합니다.')
  if b.get('execution',{}).get('orders') or b.get('execution',{}).get('closed'):raise ValueError('발주 전달·종료 후 수요 변경은 별도 변경 기안으로 검토하세요. 기존 수요 약속은 자동 해제하지 않습니다.')
  plan={**b['marketing'],'items':raw.get('items'),'scope_skus':raw.get('scope_skus'),'scope_basis':m['reason']}
  normalized=case_from(plan,data);b.update(normalized);b['status']='재검토 필요';b['marketing_stage']='SCM 검토 요청';b.pop('demand_review',None)
  from app.scm import invalidate
  invalidate(b,'수요 가정·대상 범위 변경')
 elif op=='demand_review':
  if role not in ['마케팅','SCM']:raise ValueError('마케팅/SCM 담당자가 수요 근거를 검토합니다.')
  a=assess(b,data)
  if raw.get('basis')!=a['basis']:raise ValueError('수요 검증 근거가 변경되었습니다. 다시 조회하세요.')
  if not a['items'] or any(i['missing'] for i in a['items']):raise ValueError('대상 SKU의 미입력 수요를 보완하거나 근거를 남겨 대상 범위를 수정하세요. 미입력을 0으로 확인할 수 없습니다.')
  override=text(raw.get('override_reason',''),'참고 범위 이탈/관측 부족 보완 사유',any(i['outside_range'] or i['insufficient_evidence'] for i in a['items']))
  b['demand_review']={**m,'role':role,'basis':a['basis'],'override_reason':override,'source_versions':{k:data[k].get('version') for k in ['sales','sku']},'reference_ranges':[{k:i['evidence'][k] for k in ['sku_id','range_low','range_high','observation_count']} for i in a['items']],'note':'수요 가정 검토. 실제 수요 관측·승인 행위 아님.'}
 elif op=='consult_open':
  if role not in ['SCM','재무']:raise ValueError('SCM 또는 재무가 협의를 요청합니다.')
  alts=raw.get('alternatives')
  if not isinstance(alts,list) or not 1<=len(alts)<=5:raise ValueError('비교 대안을 1~5개 작성하세요.')
  clean=[]
  for i,a in enumerate(alts):clean.append({'id':str(i),'title':text(a.get('title',''),'대안',True),**{k:text(a.get(k,''),k,True) for k in ['marketing_effect','scm_effect','finance_effect']},'provenance':'참가자 가정'})
  o['consultation']={'basis':consultation_basis(b),'subject':text(raw.get('subject',''),'협의 쟁점',True),'alternatives':clean,'replies':{},'opened_by':m['decision_maker'],'opened_at':m['at'],'reason':m['reason'],'evidence':m['evidence'],'provenance':'부서 주장'}
 elif op=='consult_reply':
  c=o.get('consultation')
  if role not in ['SCM','재무'] or not c:raise ValueError('해당 SCM·재무 협의 건에서 회신하세요.')
  if c['basis']!=consultation_basis(b):raise ValueError('협의 대상 계획·SCM 판단·재무 대상이 변경되었습니다. 협의를 다시 여세요.')
  if raw.get('position') not in ['동의','이견']:raise ValueError('동의 또는 이견을 선택하세요.')
  if raw.get('alternative_id') not in {a['id'] for a in c['alternatives']}:raise ValueError('협의 대안을 선택하세요.')
  c['replies'][role]={**m,'position':raw['position'],'alternative_id':raw['alternative_id']};c.pop('resolution',None)
 elif op=='consult_resolve':
  c=o.get('consultation')
  if role!='SCM' or not c:raise ValueError('전체 관리자인 SCM이 합의 근거를 기록합니다.')
  if c['basis']!=consultation_basis(b):raise ValueError('협의 근거 변경 · 재확인 필요')
  replies=c['replies']
  if any(replies.get(r,{}).get('position')!='동의' for r in ['SCM','재무']) or replies['SCM']['alternative_id']!=replies['재무']['alternative_id']:raise ValueError('두 부서가 같은 대안에 동의해야 합의를 기록할 수 있습니다. 미응답·이견은 동의가 아닙니다.')
  c['resolution']={**m,'alternative_id':replies['SCM']['alternative_id'],'note':'합의 기록은 승인이나 계획 변경 실행이 아닙니다. 조건을 바꾸면 원본 검토·사람 승인이 다시 필요합니다.'}
 elif op=='followup':
  kind=raw.get('kind');e=b.get('execution',{})
  if kind=='physical_receipt':
   if role!='SCM':raise ValueError('SCM이 실제 입고 확인 증빙을 기록합니다.')
   order=next((r for r in e.get('orders',[]) if r['po_id']==raw.get('po_id')),None)
   if not order:raise ValueError('전달된 발주를 선택하세요.')
   from app.domain import number,day
   qty=number(raw.get('received_qty'),'누적 입고 확인량');d=raw.get('actual_date');day(d)
   if qty>order['order_qty'] or d<order['order_date']:raise ValueError('발주 수량·일자 범위를 확인하세요.')
   o.setdefault('followups',{})['physical_receipt:'+order['po_id']]={**m,'received_qty':qty,'actual_date':d,'complete':qty==order['order_qty'],'note':'누적 입고 확인 증빙. 원본 현재고를 자동 증액하지 않음. 모의 회신은 실제 외부 증빙이 아님.'}
  elif kind=='performance':
   if role!='마케팅':raise ValueError('마케팅이 성과 검산을 확인합니다.')
   report=performance(b,data,config['review_date'])
   if not report['ready']:raise ValueError('완료 주 실제 판매 자료가 부족합니다. 미확인을 0 실적으로 완료하지 않습니다.')
   o.setdefault('followups',{})['performance']={**m,'complete':True,'report':report}
  else:raise ValueError('후속 의무 유형을 확인하세요.')
 else:raise ValueError('지원하지 않는 운영 처리입니다.')
 return b,{'operation':op,**m,'before':{'operations':case.get('operations'),'demand_review':case.get('demand_review'),'marketing':case.get('marketing')},'after':{'operations':b.get('operations'),'demand_review':b.get('demand_review'),'marketing':b.get('marketing')}}
def task_specs(case,data,config):
 if not case.get('marketing'):return []
 out=[];e=case.get('execution',{});ops=case.get('operations',{})
 if case.get('marketing_stage')!='작성 중' and not e.get('closed') and not e.get('withdrawn'):
  a=assess(case,data)
  if not a['ready']:
   missing=not a['items'] or any(i['missing'] for i in a['items'])
   out.append({'key':'demand:verify','role':'마케팅' if missing else 'SCM','title':'대상 SKU 수요 입력 보완' if missing else '수요 근거 확인 · SCM 대조 결과 전달에서 함께 기록','due':case['marketing'].get('contract_deadline'),'provenance':'내부 통제'})
 from app.portfolio import simulate
 if not e.get('closed') and not e.get('withdrawn'):
  combined=simulate(data,case)
  conflicts=[i for i in combined['items'] if i['campaign_min'] is not None and i['campaign_min']<0 and i['other_case_ids']]
  if conflicts:out.append({'key':'portfolio:conflict','role':'SCM','title':'공유 SKU 통합 수요 약속 충돌 · '+', '.join(i['sku_id'] for i in conflicts),'due':case['marketing'].get('contract_deadline'),'provenance':'계산 결과'})
 if legacy_reservation(case) and e.get('reservation') is None:out.append({'key':'portfolio:legacy','role':'SCM','title':'기존 승인 수요 범위 복원 확인 · 미확인 약속을 자동 해제하지 않음','provenance':'내부 통제'})
 c=consultation(case)
 if c['required'] and not c['ready']:
  for r in ['SCM','재무']:
   if not c.get('current') or c.get('replies',{}).get(r,{}).get('position')!='동의':out.append({'key':'consult:'+r,'role':r,'title':c['subject']+' · '+c['state'],'provenance':'부서 주장'})
  if c.get('current') and all(c.get('replies',{}).get(r,{}).get('position')=='동의' for r in ['SCM','재무']):out.append({'key':'consult:resolve','role':'SCM','title':'두 부서의 선택 대안 대조·합의 기록','provenance':'내부 통제'})
 for order in e.get('orders',[]):
  f=ops.get('followups',{}).get('physical_receipt:'+order['po_id'],{})
  if not f.get('complete'):
   reply=e.get('receipt',{});reply=reply or {};ss=[s['available_date'] for l in reply.get('lines',[]) if l['po_id']==order['po_id'] for s in l['shipments']]
   out.append({'key':'followup:receipt:'+order['po_id'],'role':'SCM','title':order['po_id']+' 실제 입고 확인 (예정 회신과 별도)','due':max(ss) if ss else order['wanted_date'],'provenance':'내부 통제'})
 if (e.get('closed') or e.get('reservation')) and not ops.get('followups',{}).get('performance',{}).get('complete'):
  out.append({'key':'followup:performance','role':'마케팅','title':'종료 후 실제 SKU 주간 판매와 수요 가정 검산','due':(date.fromisoformat(case['marketing']['end'])+timedelta(days=7)).isoformat(),'provenance':'내부 통제'})
 return out
