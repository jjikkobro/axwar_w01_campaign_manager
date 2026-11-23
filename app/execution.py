"""Human-led per-target decisions and simulated order/receipt/close workflow.
No supplier messages, payments or automatic approvals are performed.
"""
import copy,hashlib,json
from datetime import datetime,timezone
from app.domain import day,number,calculate
from app.marketing import text
from app.finance_review import view

DECISIONS=['승인','조건부 승인','보류','반려']
def now():return datetime.now(timezone.utc).isoformat()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def packet_key(case,data,config):
 v=view(case,data,config)
 return digest({'basis':v['basis'],'review':case.get('finance_review'), 'routes':v['routes']})
def targets(case,data,config):
 v=view(case,data,config);out=[];key=packet_key(case,data,config)
 for t in case.get('finance_review',{}).get('targets',[]):
  routes=[r for r in v['routes'] if r['id']==t['id']]
  authorities={r['route']['authority'] for r in routes}
  authority='CEO/이사회' if 'CEO/이사회' in authorities else next(iter(authorities),'판정 불가')
  d=case.get('execution',{}).get('decisions',{}).get(t['id'])
  out.append({**t,'authority':authority,'routes':routes,'decision':d,'current':bool(d and d['packet_key']==key and v['valid'] and not v['errors'])})
 return out

def projection(case,data,config):
 e=case.get('execution',{});ts=targets(case,data,config);v=view(case,data,config)
 adjustment=__import__('app.operations',fromlist=['pending_adjustment']).pending_adjustment(case)
 if e.get('closed'):stage=7;status='회차 종료'
 elif e.get('withdrawn'):stage=1;status='철회'
 elif adjustment:stage={'마케팅':1,'SCM':2,'재무':3}[adjustment['target']];status=adjustment['target']+' 조정 요청'
 elif e.get('rework'):stage=1;status='재작성 요청'
 elif __import__('app.operations',fromlist=['consultation']).consultation(case)['ready'] is False:stage=3;status='SCM·재무 협의 대기'
 elif any(t['current'] and t['decision']['decision'] in ['반려','보류'] for t in ts):stage=4;status='보류·재검토'
 elif any(t['current'] and t['decision']['decision']=='조건부 승인' for t in ts):stage=4;status='조건 이행·재승인 대기'
 elif e.get('receipt'):stage=7 if e['receipt'].get('clear') and v['valid'] else 3;status='마케팅 정리 대기' if stage==7 else '회신 변경 · 재무 재판정 필요'
 elif e.get('orders'):stage=6;status='공급처 회신 대기'
 elif ts and all(t['current'] and t['decision']['decision']=='승인' for t in ts):
  if any(t['kind']=='재고발주' and t['change']=='추가발주' for t in ts):stage=5;status='발주 작성 대기'
  elif e.get('supply_review',{}).get('packet_key')==packet_key(case,data,config):stage=7;status='마케팅 정리 대기'
  else:stage=6;status='입고예정 회신 확인 대기'
 elif case.get('finance_review',{}).get('operation')=='submit' and v['valid']:stage=4;status='승인 대기'
 elif case.get('scm',{}).get('review',{}).get('valid'):stage=3;status='재무 검토'
 elif case.get('marketing_stage')=='작성 중':stage=1;status='작성 중'
 else:stage=2;status='SCM 검토'
 return {'stage':stage,'status':status,'adjustment':adjustment,'targets':ts,'finance_valid':v['valid'],'orders':e.get('orders',[]),'receipt':e.get('receipt'),'closed':e.get('closed'),'notes':e.get('notes',[]),'rework':e.get('rework'),'withdrawn':e.get('withdrawn'),'supply_review':e.get('supply_review')}

def metadata(raw):
 return {**{k:text(raw.get(k,''),label,True) for k,label in [('decision_maker','담당자'),('reason','사유'),('evidence','근거')]},'at':now(),'provenance':'모의 회신'}

def stock_check(case,data,config,start,end,skus):
 calc=calculate(case,data,config);receipt=case.get('execution',{}).get('receipt') or {};rows=[]
 for x in calc.get('items',[]):
  sid=x['sku']['sku_id']
  if sid not in skus:continue
  stock=x['stock']
  if not stock or end>stock[-1]['date'] or start<case['as_of']:raise ValueError('확정 일정이 재고 검토 범위 밖입니다. 마케팅·SCM 재검토가 필요합니다.')
  ships=[s for r in receipt.get('lines',[]) if r['sku_id']==sid for s in r['shipments']]
  if 'portfolio' in data:
   period=[d for d in stock if start<=d['date']<=end];rows.append({'sku_id':sid,'minimum':min(d['closing'] for d in period) if period else None,'provenance':'계산 결과 · 통합 계획'});continue
  # Rebase additional campaign demand to the proposed confirmed period.
  old={d['date']:d for d in stock};total=next(i['total_quantity'] for i in case['marketing']['items'] if i['sku_id']==sid)
  days=(day(end)-day(start)).days+1;balance=float(x['inventory']['on_hand_qty']);minimum=None
  for d in stock:
   date=d['date'];balance+=d['inflow']+sum(s['qty'] for s in ships if s['available_date']==date)-d['base']-(total/days if start<=date<=end else 0)
   if start<=date<=end:minimum=balance if minimum is None else min(minimum,balance)
  rows.append({'sku_id':sid,'minimum':minimum,'provenance':'계산 결과'})
 return rows

def apply(case,data,config,raw,role):
 b=copy.deepcopy(case);e=b.setdefault('execution',{});op=raw.get('operation');m=metadata(raw)
 if not b.get('marketing'):raise ValueError('역할별 마케팅 기안을 선택하세요.')
 if (e.get('closed') or e.get('withdrawn')) and op not in ['obligation','answer','reservation_release']:raise ValueError('종료된 회차입니다. 새 기안으로 요청하세요.')
 campaign_level=op=='campaign_decide'
 if campaign_level:
  if role!='승인권자':raise ValueError('승인권자 역할에서만 캠페인을 결정합니다.')
  scope=[t for t in targets(b,data,config) if t['kind'] in ['캠페인집행','재고발주'] and t['authority']==raw.get('authority')]
  if not scope:raise ValueError('현재 결재권한에 해당하는 캠페인 승인 범위가 없습니다.')
  raw={**raw,'decisions':[{'id':t['id'],'decision':raw.get('decision'),'condition':raw.get('condition','')} for t in scope]};op='decide'
 if op=='obligation':
  if role!='마케팅':raise ValueError('마케팅이 상대방 통보·그룹 보고 기록을 확인합니다.')
  kind=raw.get('type')
  if kind=='contract_notice':
   if not view(b,data,config)['related_contract']:raise ValueError('연결 전속계약이 없습니다.')
  elif kind=='group_report':
   if not any(t['current'] and t['decision']['decision']=='승인' and t['authority']=='Masil 대표 승인 + 그룹 보고' for t in targets(b,data,config)):raise ValueError('그룹 보고가 필요한 유효 대표 승인 건이 없습니다.')
  else:raise ValueError('통보·보고 구분을 확인하세요.')
  e.setdefault('obligations',{})[kind]={**m,'note':'사람이 기록한 모의 이행 증빙. 실제 메시지 발송 없음.'}
 elif op=='answer':
  idx=raw.get('index')
  if not isinstance(idx,int) or idx<0 or idx>=len(e.get('notes',[])):raise ValueError('확인 요청을 선택하세요.')
  q=e['notes'][idx]
  if role!=q.get('to_role'):raise ValueError('지정 담당 부서가 회신합니다.')
  if q.get('answer'):raise ValueError('이미 회신된 확인 요청입니다.')
  q['answer']=m
 elif op=='note':
  target=raw.get('to_role') or role
  if target not in ['SCM','마케팅','재무','승인권자']:raise ValueError('요청할 담당 부서를 선택하세요.')
  e.setdefault('notes',[]).append({**m,'role':role,'to_role':target,'type':text(raw.get('type','문의'),'문의 유형',True)})
 elif op=='reservation_release':
  reservation=e.get('reservation') or __import__('app.portfolio',fromlist=['legacy_reservation']).legacy_reservation(b)
  if role!='승인권자' or not reservation or reservation.get('status') not in ['active','legacy_pending'] or raw.get('authority')!=reservation['authority']:raise ValueError('이전 약속의 승인권자가 근거를 남겨 해제합니다.')
  reservation.update(status='released',release=m);e['reservation']=reservation
 elif op=='decide':
  if role!='승인권자':raise ValueError('승인권자 역할에서만 결정합니다.')
  from app.operations import require_agreement
  require_agreement(b)
  v=view(b,data,config)
  if b.get('finance_review',{}).get('operation')!='submit' or not v['valid'] or v['errors']:raise ValueError('유효한 재무 상신과 미확인 항목 해소가 필요합니다.')
  ts=targets(b,data,config);requested=raw.get('decisions')
  if not isinstance(requested,list) or not requested:raise ValueError('본인 결재 대상의 결정을 입력하세요.')
  seen=set()
  for x in requested:
   t=next((t for t in ts if t['id']==x.get('id')),None)
   if not t or t['id'] in seen:raise ValueError('중복 또는 없는 승인 대상입니다.')
   seen.add(t['id']);authority=raw.get('authority')
   if authority!=t['authority']:raise ValueError('계산된 결재권한과 선택한 결재권한이 다릅니다.')
   if authority=='마케팅팀 전결' and m['decision_maker']==b['marketing']['author']:raise ValueError('마케팅 전결은 기안자와 결재자를 분리합니다. 내부 통제입니다.')
   d=x.get('decision')
   if d not in DECISIONS:raise ValueError('승인·조건부 승인·보류·반려 중 선택하세요.')
   previous=e.get('decisions',{}).get(t['id'])
   proof=text(raw.get('condition_evidence',''),'조건 이행 근거',bool(previous and previous.get('packet_key')==packet_key(b,data,config) and previous['decision']=='조건부 승인' and d=='승인'))
   condition=text(x.get('condition',''),'조건',d=='조건부 승인')
   e.setdefault('decisions',{})[t['id']]={**m,'decision':d,'condition':condition,'condition_evidence':proof,'authority':authority,'scope':{k:copy.deepcopy(t[k]) for k in ['id','kind','sku_id','payments','change']},'packet_key':packet_key(b,data,config),'group_report':authority=='Masil 대표 승인 + 그룹 보고'}
   if t['kind']=='캠페인집행':
    if d=='승인' and 'portfolio' in data:
     from app.portfolio import reserve,simulate
     inventory=simulate(data,b)
     e['decisions'][t['id']]['supply_risk']={'items':[{'sku_id':i['sku_id'],'campaign_min':i['campaign_min'],'unknown_demand':i['unknown_demand'],'data_complete':i['data_complete'],'other_case_ids':i['other_case_ids']} for i in inventory['items']],'supply_conflicts':inventory['supply']['conflicts'],'basis':inventory['basis'],'provenance':'계산 결과 · 승인 시점 참고; 확보 재고 또는 발주 아님'}
     e['reservation']=reserve(b,e['decisions'][t['id']],data)
    elif e.get('reservation') and d in ['반려','보류','조건부 승인']:e['reservation'].update(status='released',release=m)
  e.pop('rework',None)
 elif op=='order':
  if role!='SCM':raise ValueError('SCM만 발주서를 작성·전달 기록합니다.')
  if e.get('orders'):raise ValueError('이미 전달한 발주입니다. 공급 회신 또는 별도 변경 기안으로 진행하세요.')
  ts=targets(b,data,config);campaign=[t for t in ts if t['kind']=='캠페인집행']
  if any(not t['current'] or t['decision']['decision']!='승인' for t in campaign):raise ValueError('연결 캠페인의 유효한 승인이 필요합니다. 조건부·보류·반려 건은 재상신하세요.')
  lines=raw.get('lines')
  if not isinstance(lines,list) or not lines:raise ValueError('발주 항목을 입력하세요.')
  expected={t['id'] for t in ts if t['kind']=='재고발주' and t['change']=='추가발주'}
  if {x.get('target_id') for x in lines}!=expected or len(lines)!=len(expected):raise ValueError('승인된 신규 발주 대상을 빠짐없이 한 번씩 연결하세요.')
  orders=[]
  for x in lines:
   t=next(t for t in ts if t['id']==x['target_id'])
   if not t['current'] or t['decision']['decision']!='승인':raise ValueError('발주 대상의 유효한 사람 승인이 필요합니다. 조건부 승인은 전달할 수 없습니다.')
   if len(t['payments'])!=1:raise ValueError('분할 지급 발주서는 별도 변경 검토가 필요합니다. 자동 합치지 않습니다.')
   s=next((s for s in b['scm']['review']['items'] if s['sku_id']==t['sku_id']),None)
   qty=number(x.get('qty'),'발주 수량');price=s.get('requested_unit_price') if s else None
   if not s or price is None or not qty or qty!=s.get('requested_qty'):raise ValueError('SCM·재무가 검토한 수량·단가와 동일해야 합니다. 변경 시 재상신하세요.')
   due=x.get('payment_date');day(due)
   amount=qty*price
   if due!=t['payments'][0]['date'] or amount!=t['payments'][0]['amount']:raise ValueError('지급일·금액이 승인 범위와 다릅니다. 재무 재판정·사람 재승인이 필요합니다.')
   od=x.get('order_date');want=x.get('wanted_date');reply=x.get('reply_deadline')
   for date in [od,want,reply]:day(date)
   if od<b['as_of'] or want<od or reply<od:raise ValueError('발주일·희망 입고일·회신기한 순서를 확인하세요.')
   orders.append({**m,'po_id':'W01-'+text(raw.get('case_id',''),'기안 ID',True)[:8]+'-'+str(len(orders)+1),'target_id':t['id'],'sku_id':t['sku_id'],'order_qty':qty,'unit_price':price,'amount_krw':amount,'order_date':od,'wanted_date':want,'payment_due_date':due,'reply_deadline':reply,'channel':text(x.get('channel',''),'전달 방식',True),'supplier':'Corevia','transmission':'모의 전달','approval':copy.deepcopy(t['decision'])})
  e['orders']=orders
 elif op=='confirm_supply':
  if role!='SCM':raise ValueError('SCM이 입고예정 회신 대상을 확인합니다.')
  ts=targets(b,data,config)
  if not ts or any(not t['current'] or t['decision']['decision']!='승인' for t in ts):raise ValueError('유효한 승인 후 입고예정 회신을 확인하세요.')
  if e.get('orders') or any(t['kind']=='재고발주' and t['change']=='추가발주' for t in ts):raise ValueError('신규 발주는 전달 후 실제 공급 회신을 등록해야 합니다.')
  mode=raw.get('mode')
  if mode not in ['stock_only','confirmed_po']:raise ValueError('현재 재고 또는 등록된 공급 회신 확인을 선택하세요.')
  p=b['marketing'];calc=calculate(b,data,config)
  if not calc.get('items'):raise ValueError('제품·수요 자료를 먼저 확인하세요.')
  for item in calc['items']:
   cumulative=0;checked=[]
   for d in item['stock']:
    cumulative+=d['inflow']
    if p['start']<=d['date']<=p['end']:checked.append(d['closing']-(cumulative if mode=='stock_only' else 0))
   if len(item['weeks'])<4 or not checked or min(checked)<-0.000001:raise ValueError('캠페인 공급이 부족하거나 근거가 미확인입니다. SCM에서 수요·입고를 재검토하세요.')
  from app.portfolio import supplies
  ids={i['sku_id'] for i in p['items']};receipts=[r for r in supplies(data,b)['confirmed'] if r['sku_id'] in ids and r['available_date']<=p['end']]
  if mode=='confirmed_po' and not receipts:raise ValueError('현재 유효한 공급 확인 회신이 없습니다. 회신을 먼저 등록하세요.')
  e['supply_review']={**m,'mode':mode,'packet_key':packet_key(b,data,config),'po_ids':sorted({r['po_id'] for r in receipts}) if mode=='confirmed_po' else [],'note':'SCM 입고예정 대상 확인. 재고 기준 진행은 외부 공급 회신·실제 입고 완료를 뜻하지 않음.'}
 elif op=='receipt':
  if role!='SCM' or not e.get('orders'):raise ValueError('발주 전달 기록 후 SCM이 공급 회신을 입력합니다.')
  lines=raw.get('lines');orders=e['orders']
  if not isinstance(lines,list) or len(lines)!=len(orders) or {x.get('po_id') for x in lines}!={o['po_id'] for o in orders}:raise ValueError('모든 발주의 회신을 한 번씩 입력하세요.')
  clean=[];changed=False
  for x in lines:
   o=next(o for o in orders if o['po_id']==x['po_id']);ships=x.get('shipments')
   if not isinstance(ships,list) or not 1<=len(ships)<=20:raise ValueError('발주별 분할 회신은 1~20건입니다.')
   ss=[]
   for s in ships:
    d=s.get('available_date');day(d);qty=number(s.get('qty'),'회신 수량')
    if not qty or d<o['order_date']:raise ValueError('회신 수량·판매가능일을 확인하세요.')
    ss.append({'available_date':d,'qty':qty})
   due=x.get('payment_date');day(due)
   mismatch=sum(s['qty'] for s in ss)!=o['order_qty'];changed|=due!=o['payment_due_date'] or mismatch
   clean.append({'po_id':o['po_id'],'sku_id':o['sku_id'],'shipments':ss,'payment_date':due,'quantity_mismatch':mismatch,'delayed':max(s['available_date'] for s in ss)>o['wanted_date']})
  e['receipt']={**m,'lines':clean,'message':text(raw.get('message',''),'마케팅 회신문',True),'judgment':text(raw.get('judgment',''),'SCM 판단',True),'clear':not changed}
  if changed:b['financial_change']={'receipt':copy.deepcopy(e['receipt']),'reason':'공급 회신의 지급일/수량 변경 · 재무 재판정 필요'}
 elif op=='clear_receipt':
  if role!='재무' or not e.get('receipt'):raise ValueError('재무가 변경 회신을 대조합니다.')
  v=view(b,data,config)
  if not v['valid'] or v['errors']:raise ValueError('회신 변경을 반영한 유효한 재무 검토·상신이 필요합니다.')
  for r in e['receipt']['lines']:
   o=next(o for o in e['orders'] if o['po_id']==r['po_id']);t=next(t for t in targets(b,data,config) if t['id']==o['target_id'])
   if r['quantity_mismatch']:raise ValueError('회신 수량 불일치는 별도 변경 기안으로 처리하세요.')
   if len(t['payments'])!=1 or t['payments'][0]['date']!=r['payment_date'] or t['payments'][0]['amount']!=o['amount_krw'] or not t['current'] or t['decision']['decision']!='승인':raise ValueError('확정 지급일·금액 대조와 변경 후 사람 재승인이 필요합니다.')
  e['receipt']['clear']=True;e['receipt']['finance_confirmation']=m
 elif op=='close':
  if role!='마케팅':raise ValueError('마케팅이 일정·기록을 정리합니다.')
  ts=targets(b,data,config)
  if not ts or any(not t['current'] or t['decision']['decision']!='승인' for t in ts):raise ValueError('모든 연결 약정의 유효한 사람 승인 후 정리하세요.')
  if any(t['kind']=='재고발주' and t['change']=='추가발주' for t in ts) and (not e.get('receipt') or not e['receipt']['clear']):raise ValueError('공급 회신과 재판정 확인이 필요합니다.')
  if not any(t['kind']=='재고발주' and t['change']=='추가발주' for t in ts) and e.get('supply_review',{}).get('packet_key')!=packet_key(b,data,config):raise ValueError('⑥ SCM 입고예정 회신 대상 확인을 먼저 기록하세요.')
  if raw.get('notified') is not True:raise ValueError('상대방 통보 기록을 확인하세요.')
  p=b['marketing'];start=raw.get('start');end=raw.get('end');day(start);day(end)
  selected=raw.get('sku_ids')
  if not isinstance(selected,list) or not selected or set(selected)!={i['sku_id'] for i in p['items']}:raise ValueError('상품 구성 변경은 마케팅·SCM 재검토로 진행하세요.')
  if start!=p['start'] or end!=p['end'] or number(raw.get('budget'),'확정 요청액')!=p['budget']:raise ValueError('일정·요청액 변경은 기안 수정과 재검토·재승인 후 정리하세요.')
  stock=stock_check(b,data,config,start,end,selected)
  if any(s['minimum'] is None or s['minimum']<0 for s in stock):raise ValueError('캠페인 기간 공급 부족이 남아 있습니다. SCM·마케팅 재검토가 필요합니다.')
  e['closed']={**m,'start':start,'end':end,'sku_ids':selected,'budget':p['budget'],'notified':True,'stock':stock,'note':'검토 회차 종료. 실제 판매·입고·지급 완료가 아닙니다.'}
 elif op in ['rework','withdraw']:
  if role!='마케팅':raise ValueError('마케팅이 보류 건을 재검토·철회합니다.')
  if not any(t['current'] and t['decision']['decision'] in ['보류','반려','조건부 승인'] for t in targets(b,data,config)):raise ValueError('보류·반려·조건부 결정 후 진행하세요.')
  if raw.get('notified') is not True:raise ValueError('확정기한 전 상대방 통보 기록을 확인하세요.')
  if e.get('orders'):raise ValueError('전달된 발주는 철회할 수 없습니다. 별도 변경 기안으로 처리하세요.')
  e['withdrawn' if op=='withdraw' else 'rework']={**m,'notified':True}
 else:raise ValueError('지원하지 않는 업무 처리입니다.')
 if campaign_level:
  e.setdefault('campaign_reviews',{})[raw['authority']]={**m,'decision':raw['decision'],'condition':raw.get('condition',''),'scope_ids':[t['id'] for t in scope],'authority':raw['authority'],'packet_key':packet_key(b,data,config),'note':'이번 캠페인 단일 결정 · 해당 결재권한 범위만 적용'}
 return b,{'operation':'campaign_decide' if campaign_level else op,**m,'before':case.get('execution'),'after':e}

def task_specs(case,data,config):
 if not case.get('marketing'):return []
 p=projection(case,data,config);out=[]
 if not p['closed'] and not p['withdrawn']:
  owner={1:'마케팅',2:'SCM',3:'재무',4:'승인권자',5:'SCM',6:'SCM',7:'마케팅'}[p['stage']]
  if p['status']=='보류·재검토':owner='마케팅'
  if p['status'] in ['조건 이행·재승인 대기','SCM·재무 협의 대기']:owner='SCM'
  out.append({'key':'execution:next','role':owner,'title':p['status'],'provenance':'계산 결과'})
  for o in p['orders']:
   if not p['receipt']:out.append({'key':'execution:reply:'+o['po_id'],'role':'SCM','title':o['po_id']+' 공급처 회신 확인','due':o['reply_deadline'],'provenance':'내부 통제'})
 for i,q in enumerate(case.get('execution',{}).get('notes',[])):
  if not q.get('answer'):out.append({'key':'execution:question:'+str(i),'role':q['to_role'],'title':q['type']+' · '+q['reason'],'provenance':'부서 주장'})
 if any(t['current'] and t['decision']['decision']=='승인' and t['authority']=='Masil 대표 승인 + 그룹 보고' for t in p['targets']) and not case.get('execution',{}).get('obligations',{}).get('group_report'):
  out.append({'key':'execution:group_report','role':'마케팅','title':'Masil 대표 승인 건 그룹 보고 이행 증빙 확인','provenance':'내부 통제'})
 return out

def operational_schedule(case,data):
 """Marketing's read-only dates from SCM records, never dates invented at application."""
 e=case.get('execution',{});receipt=e.get('receipt') or {};out=[]
 names={s['sku_id']:s['sku_name'] for s in data['sku']['rows']}
 for order in e.get('orders',[]):
  line=next((r for r in receipt.get('lines',[]) if r['po_id']==order['po_id']),None);confirmed=bool(line and receipt.get('clear'))
  out.append({'po_id':order['po_id'],'sku_id':order['sku_id'],'name':names.get(order['sku_id'],order['sku_id']),'qty':order['order_qty'],'order_date':order['order_date'],'payment_date':line['payment_date'] if confirmed else order['payment_due_date'],'payment_basis':'공급 회신 확인' if confirmed else 'SCM 발주서 기준','available':[dict(s) for s in line['shipments']] if confirmed else [],'status':'입고예정 회신 확인' if confirmed else '변경 회신 재확인 중' if line else '입고예정 회신 대기','provenance':receipt.get('provenance') if confirmed else order.get('transmission','SCM 기록')})
 # Existing PO confirmations attached by SCM also count as sources, once per PO.
 from app.scm import fingerprint
 scope={i['sku_id'] for i in case.get('marketing',{}).get('items',[])}
 for pid,r in case.get('scm',{}).get('receipts',{}).items():
  po=next((p for p in data['purchase']['rows'] if p['po_id']==pid and p['sku_id'] in scope),None)
  if not po or any(x['po_id']==pid for x in out) or r.get('status')!='확인' or r.get('po_fingerprint')!=fingerprint(po):continue
  out.append({'po_id':pid,'sku_id':po['sku_id'],'name':names.get(po['sku_id'],po['sku_id']),'qty':r['qty'],'order_date':po.get('order_date'),'payment_date':po['payment_due_date'],'payment_basis':'기존 발주서 기준','available':[{'available_date':r['available_date'],'qty':r['qty']}],'status':'기존 발주 입고예정 확인','provenance':r.get('provenance','부서 주장')})
 return {'rows':out,'source':'SCM 발주 기록·확인된 공급 회신','note':'예정 일정입니다. 실제 입고·출고·지급 완료를 뜻하지 않습니다.'}
