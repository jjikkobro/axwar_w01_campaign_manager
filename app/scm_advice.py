"""Evidence-based SCM recommendations and checked counterfactuals; no mutations."""
import copy,math
from datetime import date,timedelta
from app.portfolio import simulate,supplies
from app.planning import lead_days

def shifted(case,start):
 b=copy.deepcopy(case);p=b['marketing'];delta=date.fromisoformat(start)-date.fromisoformat(p['start'])
 for k in ['start','end']:p[k]=(date.fromisoformat(p[k])+delta).isoformat();b[k]=p[k]
 for i in p['items']:
  for k in ['start','end']:i[k]=(date.fromisoformat(i[k])+delta).isoformat()
 return b

def project(case,data):return simulate(data,case,end=case['marketing']['end'])
def minimum(plan):return min((i['campaign_min'] for i in plan['items'] if i['campaign_min'] is not None),default=None)
def recommend(case,data,items,replenishment=None):
 b=copy.deepcopy(case);b['_case_id']=b.get('_case_id') or b.get('id') or '__scm_preview__';p=b['marketing'];why=[];actions=[]
 if not items or any(not i['data_complete'] for i in items):return {'kind':'missing','label':'수요·재고 근거 확인 필요','why':['완료된 최근 4주 판매와 SKU 수요·재고 기준일을 확인하세요. 미입력은 0으로 판단하지 않습니다.'],'actions':[]}
 current=project(b,data)
 if any(i['unknown_demand'] for i in current['items']):return {'kind':'missing','label':'대상 SKU 수요 입력 보완','why':['수요가 비어 있는 SKU가 있습니다. 같은 화면에서 수요와 근거를 보완하세요. 미입력은 0으로 확정하지 않습니다.'],'actions':[]}
 bad=[i for i in current['items'] if i['campaign_min'] is None or i['campaign_min']<-.000001]
 baseline=copy.deepcopy(b)
 for i in baseline['marketing']['items']:i['demand']=0;i['total_quantity']=0
 base=project(baseline,data);base_by={i['sku_id']:i for i in base['items']}
 for item in items:
  if item.get('first_short_before_campaign'):why.append(item['sku_id']+'는 캠페인 시작 전 '+item['first_short_before_campaign']+'부터 기초 판매·기존 약속에 따른 부족이 있습니다. 캠페인 기간 공급과 구분해 대응하세요.')
 if not bad:
  why.insert(0,p['start']+'~'+p['end']+' 캠페인 기간에는 현재고·확인 입고·다른 승인 수요를 합산해도 부족하지 않습니다. 기간 최소 재고 '+str(round(minimum(current),2))+'EA.')
  return {'kind':'ready','label':'캠페인 기간 공급 가능','why':why,'actions':[]}
 for i in bad:
  x=next(x for x in items if x['sku_id']==i['sku_id']);first=next(d['date'] for d in i['days'] if p['start']<=d['date']<=p['end'] and d['closing']<0)
  why.append(i['sku_id']+'는 '+first+'부터 캠페인 기간 재고가 부족합니다. 최소 '+str(round(i['campaign_min'],2))+'EA, 같은 기간 이번 캠페인 제외 시 최소 '+str(round(base_by[i['sku_id']]['campaign_min'],2))+'EA.')
 # A long-range request is a procurement-planning problem, not a supply refusal.
 if replenishment and replenishment['feasible'] and all((date.fromisoformat(p['start'])-date.fromisoformat(p['as_of'])).days>lead_days(data,i['lead_time_weeks']) for i in replenishment['items']):
  extra=any((i['incremental_qty'] or 0)>0 for i in replenishment['items'])
  label='정기 보충·캠페인 추가 발주 검토' if extra else '재고로 가능 · 정기 보충 반영'
  why.insert(0,'현재 확인된 공급만으로는 부족합니다. 미확인 기존 발주와 정기 보충 계산안'+(' 및 캠페인 추가 조달' if extra else '')+'이 예정대로 입고된다는 가정에서만 캠페인 기간 공급이 가능합니다. 공급능력·입고일·지급일은 별도 확인이 필요합니다.')
  for i in replenishment['items']:
   pipeline=sum(x['qty'] for x in i['pipeline_assumptions'] if x['date']<=p['end'])
   why.append(i['sku_id']+' 미확인 기존 발주 예상 입고 '+str(round(pipeline))+'EA, 정기 보충 계산안 '+str(i['regular_qty'])+'EA, 캠페인 추가 '+str(i['incremental_qty'])+'EA. 리드타임 '+str(i['lead_time_weeks'])+'주, 가정 반영 기간 최소 '+str(round(i['campaign_min_with_extra'],2))+'EA.')
   actions.append({'type':'replenishment','sku_id':i['sku_id'],'text':i['sku_id']+' 정기 보충 계산안의 수량·일정과 공급능력을 확인하세요. 캠페인 추가분은 '+str(i['incremental_qty'])+'EA, 역산 발주 검토일 '+i['latest_order_date']+'. 지급일·재무 검토·사람 승인 후 실제 발주합니다.'})
  return {'kind':'procurement','label':label,'campaign_extra_required':extra,'why':why,'actions':actions,'scenario':[{'sku_id':i['sku_id'],'minimum':i['campaign_min_with_extra']} for i in replenishment['items']],'provenance':'참가자 가정 / 계산 결과'}
 # Assumptions are a separate what-if ledger, never confirmed inventory.
 hypothetical=copy.deepcopy(data);candidate=copy.deepcopy(b);candidate.setdefault('scm',{}).setdefault('receipts',{});assumed=[]
 from app.scm import fingerprint
 for x in items:
  q=x['procurement'].get('effective_proposal_qty');arrival=x['procurement'].get('proposed_available_date') or x['procurement'].get('lead_time_arrival_assumption')
  if q and arrival and arrival>=p['as_of']:
   pid='ASSUMPTION-'+x['sku_id'];po={'po_id':pid,'sku_id':x['sku_id'],'order_qty':q,'amount_krw':0,'payment_due_date':None};hypothetical['purchase']['rows'].append(po)
   candidate['scm']['receipts'][pid]={'status':'확인','qty':q,'available_date':arrival,'po_fingerprint':fingerprint(po),'provenance':'참가자 가정 · 시나리오 전용'};assumed.append(x['sku_id']+' '+arrival+' '+str(q)+'EA')
 if assumed:
  forecast=project(candidate,hypothetical)
  if all(i['campaign_min'] is not None and i['campaign_min']>=-.000001 for i in forecast['items']):
   why.insert(0,'신청 예상안의 입고 가정('+', '.join(assumed)+')을 반영하면 캠페인 기간 최소 재고 '+str(round(minimum(forecast),2))+'EA로 공급 가능합니다. 현재 대조는 확인 회신만 반영하므로 SCM이 해당 입고 조건을 확인해야 합니다.')
   return {'kind':'conditional','label':'신청 예상안 공급 가능 · 입고 조건 확인','why':why,'scenario':[{'sku_id':i['sku_id'],'minimum':i['campaign_min']} for i in forecast['items']],'actions':[{'type':'confirm_inbound','text':'신청 예상안의 수량·판매가능일을 공급처에 확인하고 회신 근거를 등록하세요. 확인 전에는 실제 공급으로 합산하지 않습니다.','source':assumed}]}
 confirmed=supplies(data,b)['confirmed'];candidate_dates=sorted({r['available_date'] for r in confirmed if r['sku_id'] in {i['sku_id'] for i in bad} and p['start']<r['available_date']})[:6]
 duration=(date.fromisoformat(p['end'])-date.fromisoformat(p['start'])).days
 for start in candidate_dates:
  if (date.fromisoformat(start)+timedelta(days=duration)-date.fromisoformat(p['as_of'])).days>180:continue
  proposed=shifted(b,start);after=project(proposed,data)
  if any(i['campaign_min'] is None or i['campaign_min']<-.000001 for i in after['items']):continue
  refs=sorted({r['po_id'] for r in confirmed if r['available_date']==start});text='캠페인을 확인된 기존 입고('+start+', '+', '.join(refs)+') 이후 '+start+'~'+proposed['marketing']['end']+'로 옮기면, 입고 전 부족 구간과 캠페인 수요가 겹치지 않습니다. 변경 기간 최소 재고 '+str(round(minimum(after),2))+'EA로 재검산했습니다.'
  actions.append({'type':'shift_campaign','text':text,'start':start,'end':proposed['marketing']['end'],'minimum':minimum(after),'source':refs});break
 for i in bad:
  first=next(d['date'] for d in i['days'] if p['start']<=d['date']<=p['end'] and d['closing']<0)
  qty=math.ceil(-i['campaign_min']);actions.append({'type':'required_inbound','sku_id':i['sku_id'],'needed_by':first,'required_qty':qty,'text':i['sku_id']+'는 '+first+'까지 최소 '+str(qty)+'EA의 추가 판매가능 입고가 확인되어야 캠페인 기간 부족을 메울 수 있습니다. 해당 수량이 첫 부족일 전에 한 번에 추가되고 다른 수요·공급이 유지된다는 계산 가정입니다.'})
  if base_by[i['sku_id']]['campaign_min']<0:
   actions.append({'type':'baseline_shortage','text':i['sku_id']+'는 캠페인 수요를 0으로 해도 기간 중 부족합니다. 캠페인 축소만으로 해결되지 않으므로 추가 확인 입고 또는 다른 SKU 구성을 검토하세요.','sku_id':i['sku_id']});continue
  original=next(x for x in p['items'] if x['sku_id']==i['sku_id']);low=0;high=int(original['demand'])
  while low<high:
   mid=(low+high+1)//2;trial=copy.deepcopy(b);line=next(x for x in trial['marketing']['items'] if x['sku_id']==i['sku_id']);line['demand']=mid;line['total_quantity']=mid*((date.fromisoformat(line['end'])-date.fromisoformat(line['start'])).days+1)/7 if line['unit']=='EA/주' else mid
   observed=next(x for x in project(trial,data)['items'] if x['sku_id']==i['sku_id'])
   if observed['campaign_min'] is not None and observed['campaign_min']>=-.000001:low=mid
   else:high=mid-1
  actions.append({'type':'reduce_demand','sku_id':i['sku_id'],'max_demand':low,'unit':original['unit'],'text':i['sku_id']+'의 추가 수요를 '+str(original['demand'])+'→'+str(low)+original['unit']+' 이하로 낮추면 현재 확인 공급 기준으로 해당 SKU의 캠페인 기간 음수 재고를 피할 수 있습니다. 다른 SKU는 별도 확인하세요.'})
 if not any(a['type']=='shift_campaign' for a in actions):actions.append({'type':'confirm_inbound','text':'현재 확인된 입고만으로 기간 조정 시 공급이 충분해지는 대안을 찾지 못했습니다. 공급처의 수량·판매가능일 확인 또는 SKU 구성을 재검토하세요.'})
 return {'kind':'adjust','label':'캠페인 수요와 공급 일정 조정 필요','why':why,'actions':actions}
