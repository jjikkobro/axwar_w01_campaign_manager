"""Shared SKU-day ledger. A baseline/inbound is counted once, never per campaign."""
import copy,hashlib,json
from app.formulas import run
from datetime import date,timedelta

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def ident(case):return case.get('_case_id') or case.get('id')
def legacy_reservation(b):
 e=b.get('execution',{})
 if e.get('withdrawn') or e.get('rework'):return None
 approved=next((d for d in e.get('decisions',{}).values() if d.get('scope',{}).get('kind')=='캠페인집행' and d.get('decision')=='승인'),None)
 if not approved:return None
 return {'status':'legacy_pending','items':copy.deepcopy(b.get('marketing',{}).get('items',[])),'authority':approved['authority'],'approved_at':approved['at'],'evidence':approved['evidence'],'provenance':'내부 통제 · 기존 승인 범위 복원 확인 필요'}
def slim(cid,b):
 e=b.get('execution',{})
 return {'case_id':cid,'marketing':b.get('marketing'),'stage':b.get('marketing_stage'),'created_at':b.get('created_at'),'reservation':e.get('reservation') if e.get('reservation') is not None else legacy_reservation(b),'receipts':b.get('scm',{}).get('receipts',{}),'orders':e.get('orders',[]),'receipt':e.get('receipt'),'withdrawn':bool(e.get('withdrawn'))}
def records(data,case=None):
 rs={r['case_id']:r for r in data.get('portfolio',{}).get('rows',[])}
 if case and ident(case):rs[ident(case)]=slim(ident(case),case)
 return list(rs.values())
def supplies(data,case=None):
 originals={p['po_id']:p for p in data['purchase']['rows']};evidence={};conflicts=[];confirmed=[]
 for r in records(data,case):
  for pid,x in r['receipts'].items():
   po=originals.get(pid)
   if not po or x.get('po_fingerprint')!=digest(po):continue
   evidence.setdefault(pid,[]).append({**x,'sku_id':po['sku_id'],'source_case':r['case_id'],'stamp':x.get('at') or r.get('created_at') or ''})
 for pid,rs in evidence.items():
  stamp=max(r['stamp'] for r in rs);latest=[r for r in rs if r['stamp']==stamp]
  distinct={(r.get('status'),r.get('qty'),r.get('available_date')) for r in latest}
  if len(distinct)>1:conflicts.append({'po_id':pid,'reason':'동일 최신 시각의 회신 불일치','sources':[r['source_case'] for r in latest]});continue
  r=latest[0]
  if r.get('status')=='확인' and r.get('available_date') and r.get('qty') is not None:
   confirmed.append({'po_id':pid,'sku_id':r['sku_id'],'qty':float(r['qty']),'available_date':r['available_date'],'provenance':r['provenance'],'source_case':r['source_case'],'kind':'기존 PO 확인 회신','record':r})
 # New orders stay separate from original AP/PO and become supply only after a clear reply.
 seen=set(originals)
 for r in records(data,case):
  reply=r.get('receipt')
  if not reply or not reply.get('clear'):continue
  for line in reply.get('lines',[]):
   order=next((o for o in r['orders'] if o['po_id']==line['po_id']),None)
   if not order:continue
   if line['po_id'] in seen:conflicts.append({'po_id':line['po_id'],'reason':'중복 신규 발주 ID · 공급 제외'});continue
   seen.add(line['po_id'])
   if sum(s['qty'] for s in line['shipments'])!=order['order_qty']:continue
   for s in line['shipments']:confirmed.append({'po_id':line['po_id'],'sku_id':line['sku_id'],'qty':s['qty'],'available_date':s['available_date'],'provenance':reply['provenance'],'source_case':r['case_id'],'kind':'신규 PO 분할 확인 회신'})
 return {'confirmed':confirmed,'conflicts':conflicts}
def scope(case):
 p=case.get('marketing') or {};return p.get('scope_skus') or [i['sku_id'] for i in p.get('items',[])]
def context_basis(case,data):
 if 'portfolio' not in data:return None
 ids=set(scope(case));own=ident(case);s=supplies(data,case)
 allocations=[{'case_id':r['case_id'],'items':r['reservation']['items'],'status':r['reservation']['status']} for r in records(data,case) if r['case_id']!=own and (r.get('reservation') or {}).get('status') in ['active','legacy_pending'] and any(i['sku_id'] in ids for i in r['reservation']['items'])]
 supply=[{k:x[k] for k in ['po_id','sku_id','qty','available_date']} for x in s['confirmed'] if x['sku_id'] in ids and x['source_case']!=own]
 return digest({'allocations':sorted(allocations,key=lambda r:r['case_id']),'supply':sorted(supply,key=lambda r:(r['po_id'],r['available_date'])),'conflicts':s['conflicts']})
def simulate(data,case=None,asof=None,end=None,sku_ids=None):
 p=case.get('marketing',{}) if case else {};asof=asof or p.get('as_of') or '2026-07-01';start=date.fromisoformat(asof)
 end=end or p.get('end') or (start+timedelta(days=89)).isoformat();stop=min(date.fromisoformat(end),start+timedelta(days=180));own=ident(case) if case else None
 selected=set(sku_ids or (scope(case) if case else [s['sku_id'] for s in data['sku']['rows']]))
 ledger=[{'case_id':r['case_id'],**r['reservation']} for r in records(data,case) if r['case_id']!=own and (r.get('reservation') or {}).get('status') in ['active','legacy_pending']]
 supply=supplies(data,case);items=[];weekly=[];warnings=[]
 if stop<start:raise ValueError('통합 검토 기간의 종료일은 기준일 이후입니다.')
 for sku in data['sku']['rows']:
  sid=sku['sku_id']
  if sid not in selected:continue
  inv=next(i for i in data['inventory']['rows'] if i['sku_id']==sid)
  sales=sorted([r for r in data['sales']['rows'] if r['sku_id']==sid and date.fromisoformat(r['week'])+timedelta(days=7)<=start],key=lambda r:r['week'])[-4:]
  avg=run(data,'weekly_average',sales_total=sum(float(s['sold_qty']) for s in sales),weeks_count=len(sales)) if sales else 0
  own_items=[i for i in p.get('items',[]) if i['sku_id']==sid]
  allocations=[{'case_id':r['case_id'],'item':i} for r in ledger for i in r['items'] if i['sku_id']==sid]
  unknown=bool(case and sid in selected and not own_items)
  stock=float(inv['on_hand_qty']);days=[];first=None
  for offset in range((stop-start).days+1):
   d=start+timedelta(days=offset);ds=d.isoformat();inflow=sum(float(s['qty']) for s in supply['confirmed'] if s['sku_id']==sid and s['available_date']==ds)
   qty=lambda i:run(data,'campaign_daily',total_quantity=float(i['total_quantity']),duration_days=(date.fromisoformat(i['end'])-date.fromisoformat(i['start'])).days+1) if i['start']<=ds<=i['end'] else 0
   others=sum(qty(a['item']) for a in allocations);candidate=sum(qty(i) for i in own_items);opening=stock;base=run(data,'baseline_daily',weekly=avg);stock+=inflow-base-others-candidate
   if stock<-.000001 and first is None:first=ds
   days.append({'date':ds,'opening':round(opening,4),'inflow':round(inflow,4),'base':base,'other_campaign':others,'campaign':candidate,'closing':round(stock,4),'unknown_demand':unknown})
  byweek={}
  for row in days:
   d=date.fromisoformat(row['date']);w=(d-timedelta(days=d.weekday())).isoformat();byweek.setdefault(w,[]).append(row)
  for w,rs in byweek.items():weekly.append({'sku_id':sid,'week':w,'days':len(rs),'opening':rs[0]['opening'],'confirmed_inbound':sum(r['inflow'] for r in rs),'baseline':sum(r['base'] for r in rs),'approved_demand':sum(r['other_campaign'] for r in rs),'candidate_demand':sum(r['campaign'] for r in rs),'closing':rs[-1]['closing'],'minimum':min(r['closing'] for r in rs),'unknown_demand':unknown,'case_ids':sorted({a['case_id'] for a in allocations if a['item']['start']<=rs[-1]['date'] and a['item']['end']>=rs[0]['date']})})
  check=[r for r in days if p.get('start',asof)<=r['date']<=p.get('end',stop.isoformat())]
  complete=len(sales)==4 and date.fromisoformat(inv['snapshot_date'])+timedelta(days=1)==start
  if not complete:warnings.append(sid+' 기준 재고/완료 4주 확인 필요')
  if unknown:warnings.append(sid+' 추가 수요 미확인 · 0이 아닌 판정 불가')
  items.append({'sku_id':sid,'days':days,'weekly_average':avg,'first_short':first,'campaign_min':min(r['closing'] for r in check) if check else None,'unknown_demand':unknown,'data_complete':complete,'other_case_ids':sorted({a['case_id'] for a in allocations})})
 return {'as_of':asof,'end':stop.isoformat(),'items':items,'weekly':weekly,'reservations':ledger,'supply':supply,'warnings':warnings,'basis':context_basis(case,data) if case else digest(ledger),'provenance':'계산 결과','policy':'통합 기준 판매·현재고·PO 공급은 SKU별 한 번만 반영. 다른 확정 약속 + 검토 건 순증을 합산. 미확인은 0으로 확정하지 않음.'}
def guard(case,data):
 if 'portfolio' not in data:return
 from app.demand import require_ready
 require_ready(case,data)
 result=simulate(data,case)
 if any(r['status']=='legacy_pending' and any(i['sku_id'] in set(scope(case)) for i in r['items']) for r in result['reservations']):raise ValueError('동일 SKU의 기존 승인 수요 약속을 먼저 복원 확인하거나 원 승인권자가 해제해야 합니다.')
 if result['supply']['conflicts']:raise ValueError('통합 공급 회신 불일치 확인이 필요합니다.')
 if any(i['unknown_demand'] or not i['data_complete'] for i in result['items']):raise ValueError('SKU 수요·재고 기준일·완료 4주 자료가 미확인입니다.')
 bad=[i for i in result['items'] if i['campaign_min'] is None or i['campaign_min']<-.000001]
 if bad:raise ValueError('통합 재고 약속 충돌/품절: '+', '.join(i['sku_id']+' (다른 기안 '+','.join(i['other_case_ids'])+')' for i in bad)+' · 수량·기간·확인 입고를 조정해 재검토하세요.')
def reserve(case,decision,data=None):
 baselines={}
 if data:
  for sid in scope(case):
   sales=sorted([r for r in data['sales']['rows'] if r['sku_id']==sid and date.fromisoformat(r['week'])+timedelta(days=7)<=date.fromisoformat(case['as_of'])],key=lambda r:r['week'])[-4:]
   if sales:baselines[sid]=run(data,'weekly_average',sales_total=sum(float(r['sold_qty']) for r in sales),weeks_count=len(sales))
 return {'status':'active','baselines':baselines,'items':copy.deepcopy(case['marketing']['items']),'approved_at':decision['at'],'decision_maker':decision['decision_maker'],'authority':decision['authority'],'evidence':decision['evidence'],'provenance':'부서 주장','control':'내부 통제 · 승인 수요 약속. 실제 출고·재고 차감 기록이 아님.'}

def cash_orders(data,case=None):
 result={}
 for r in records(data,case):
  for o in r['orders']:
   d=o['payment_due_date'];reply=r.get('receipt')
   if reply and reply.get('clear'):
    line=next((l for l in reply['lines'] if l['po_id']==o['po_id']),None)
    if line:d=line['payment_date']
   result[o['po_id']]={'po_id':o['po_id'],'case_id':r['case_id'],'date':d,'amount':o['amount_krw'],'sku_id':o['sku_id'],'provenance':o.get('provenance','모의 회신')}
 return sorted(result.values(),key=lambda x:x['po_id'])
def cash_context(case,data):return digest([r for r in cash_orders(data,case) if r['case_id']!=ident(case)]) if 'portfolio' in data else None
def without_own_orders(case,data):
 if 'portfolio' not in data:return data
 return {**data,'portfolio':{**data['portfolio'],'rows':[{**r,'orders':[]} if r['case_id']==ident(case) else r for r in data['portfolio']['rows']]}}
