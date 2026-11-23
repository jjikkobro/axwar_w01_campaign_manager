"""Company-scale, descriptive demand evidence; never scales sample marketing orders."""
import copy,hashlib,json,math
from functools import lru_cache
from datetime import date,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def signature(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def scope(case):
 p=case.get('marketing',{})
 return p.get('scope_skus') or [i['sku_id'] for i in p.get('items',[])]
@lru_cache(maxsize=1)
def reference():return json.loads((ROOT/'data/demand_reference.json').read_text())
def quantile(xs,q):
 if not xs:return None
 s=sorted(xs);k=(len(s)-1)*q;a=int(k);return s[a]+(s[min(a+1,len(s)-1)]-s[a])*(k-a)
def evidence(sid,data,asof):
 return cached_evidence(sid,asof,json.dumps({k:data[k] for k in ['sales','sku']},sort_keys=True,ensure_ascii=False))
@lru_cache(maxsize=128)
def cached_evidence(sid,asof,payload):
 data=json.loads(payload)
 ref=reference();line=next((s['sku_name'].split(' ')[0] for s in data['sku']['rows'] if s['sku_id']==sid),'')
 merged={(r['week'],r['sku_id']):r for r in ref['sales']}
 merged.update({(r['week'],r['sku_id']):r for r in data['sales']['rows']})
 rows=sorted([{'week':r['week'],'sold_qty':int(r['sold_qty'])} for r in merged.values() if r['sku_id']==sid and date.fromisoformat(r['week'])+timedelta(days=7)<=date.fromisoformat(asof)],key=lambda r:r['week'])
 campaigns=[c for c in ref['campaigns'] if c['product_line']==line and c['start_date']<asof]
 byweek={};excluded=[]
 for c in campaigns:
  # Full historical weeks within campaign; preceding four full weeks, never future data.
  baseline=[r for r in rows if date.fromisoformat(r['week'])+timedelta(days=7)<=date.fromisoformat(c['start_date'])][-4:]
  if len(baseline)<4:excluded.append({'campaign_id':c['campaign_id'],'reason':'사전 완료 4주 부족'});continue
  avg=sum(r['sold_qty'] for r in baseline)/4
  for r in rows:
   if r['week']<c['start_date'] or (date.fromisoformat(r['week'])+timedelta(days=6)).isoformat()>c['end_date']:continue
   x=byweek.get(r['week'])
   # Several campaigns share the same observation: count each SKU-week once.
   if not x or x['campaign_start']<c['start_date']:
    byweek[r['week']]={'week':r['week'],'actual_qty':r['sold_qty'],'baseline_qty':avg,'increment':r['sold_qty']-avg,'baseline_weeks':[b['week'] for b in baseline],'campaign_start':c['start_date'],'campaign_ids':[c['campaign_id']]}
   elif x['campaign_start']==c['start_date']:x['campaign_ids'].append(c['campaign_id'])
 observations=list(byweek.values());deltas=[r['increment'] for r in observations];recent=rows[-4:]
 return {'sku_id':sid,'product_line':line,'baseline_weekly':sum(r['sold_qty'] for r in recent)/len(recent) if recent else None,'recent_weeks':recent,'observations':observations,'observation_count':len(observations),'range_low':max(0,quantile(deltas,.1)) if deltas else None,'range_high':max(0,quantile(deltas,.9)) if deltas else None,'signed_p10':quantile(deltas,.1),'signed_p90':quantile(deltas,.9),'excluded':excluded,'sources':ref['sources']+[{'file':data['sales']['source'],'version':data['sales'].get('version'),'provenance':data['sales'].get('provenance','원본 사실')}],'provenance':'계산 결과','method':'동일 제품라인 과거 캠페인 안의 완료 주 판매 − 캠페인 직전 완료 4주 평균. SKU×주 중복 제거. 증가량 P10~P90은 참고 범위. 최근 완료 4주 평균을 기초 수요로 사용.','limitations':['동시 캠페인·계절성·가격/유통 효과가 섞여 있어 캠페인의 인과 효과나 미래 보장이 아님.','표본 주문·GMV를 회사 전체 EA로 환산하지 않음.','미입력 수요는 0이 아니며, 0도 담당자 근거가 있는 명시적 가정이어야 함.']}
def basis(case,data):
 p=case.get('marketing',{});ref=reference()
 return signature({'scope':scope(case),'plan':p,'sales':data['sales'],'sku':data['sku'],'history':ref['sources']})
def assess(case,data):
 if not case.get('marketing'):return {'enabled':False,'ready':True,'items':[],'warnings':[]}
 p=case['marketing'];items={i['sku_id']:i for i in p.get('items',[])};out=[];warnings=[]
 for sid in scope(case):
  ev=evidence(sid,data,p['as_of']);i=items.get(sid);qty=None
  if i:
   days=(date.fromisoformat(i['end'])-date.fromisoformat(i['start'])).days+1
   qty=float(i['demand']) if i['unit']=='EA/주' else float(i['demand'])*7/days
  missing=i is None;outside=qty is not None and ev['range_low'] is not None and not ev['range_low']<=qty<=ev['range_high']
  uncertainty=ev['observation_count']<4
  out.append({'sku_id':sid,'input_weekly':qty,'missing':missing,'outside_range':outside,'insufficient_evidence':uncertainty,'evidence':ev})
  if missing:warnings.append(sid+' 수요 미입력 · 0으로 확정하지 않음')
  elif outside:warnings.append(sid+' 과거 참고 범위 밖 · 사유 확인 필요')
  if uncertainty:warnings.append(sid+' 비교 관측 부족 · 명시적 보완 근거 필요')
 if not out:warnings.append('대상 SKU·수요 범위 미확인')
 review=case.get('demand_review',{});current=review.get('basis')==basis(case,data)
 needs_override=any(i['outside_range'] or i['insufficient_evidence'] for i in out)
 ready=bool(out) and not any(i['missing'] for i in out) and current and (not needs_override or bool(review.get('override_reason')))
 return {'enabled':True,'basis':basis(case,data),'items':out,'warnings':warnings,'review':review,'review_current':current,'ready':ready,'scope':scope(case),'provenance':'계산 결과','rule':'U1-2026-11-10: 통계는 검증 보조, 담당자 확인 전 수요 확정/승인 없음'}
def require_ready(case,data):
 if 'portfolio' in data and not assess(case,data)['ready']:raise ValueError('수요 가정 검증 필요: 대상 SKU의 미입력·참고 범위·근거를 확인하고 마케팅/SCM 검토를 기록하세요.')
