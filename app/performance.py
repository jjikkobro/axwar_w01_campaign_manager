"""Reproducible sample campaign performance. Never scales into company cash."""
import csv,hashlib,json
from pathlib import Path
from decimal import Decimal
from functools import lru_cache
ROOT=Path(__file__).resolve().parent.parent/'01_참가자_배포용/04_원본데이터'
@lru_cache(maxsize=1)
def sample():
 snapshot=Path(__file__).resolve().parent.parent/'data/performance_reference.json'
 if not ROOT.exists() and snapshot.exists():return json.loads(snapshot.read_text())
 sources=[]
 def read(path):
  p=ROOT/path;sources.append({'file':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
  with p.open() as f:return list(csv.DictReader(f,delimiter='|'))
 orders=read('02_masil/marketing/mkt_orders_ms.csv');returns=read('02_masil/marketing/mkt_returns_ms.csv');spend=read('02_masil/marketing/mkt_ad_spend_ms.csv');cost=read('02_masil/marketing/mkt_cost_master_ms.csv');campaigns=read('02_masil/master/m_campaign_ms.csv')
 costs={(c['sku_id'],c['channel_id']):c for c in cost};refunds={};return_count={}
 for r in returns:
  if r['refund_completed_date']<='2026-07-01':
   key=r['order_id'];refunds[key]=refunds.get(key,0)+int(r['refund_amount_krw']);return_count[key]=return_count.get(key,0)+1
 stats={c['campaign_id']:{'campaign_id':c['campaign_id'],'influencer_id':c['influencer_id'],'gmv':0,'refund':0,'marketing_spend':0,'cost':Decimal(0),'orders':0,'missing_cost':0,'first_order':None,'last_order':None} for c in campaigns}
 for r in orders:
  if r['order_date']>'2026-07-01':continue
  s=stats[r['campaign_id']];s['orders']+=1;s['gmv']+=int(r['gmv_krw']);s['refund']+=refunds.get(r['order_id'],0)
  s['first_order']=min(s['first_order'] or r['order_date'],r['order_date']);s['last_order']=max(s['last_order'] or r['order_date'],r['order_date'])
  c=costs.get((r['sku_id'],r['channel_id']))
  if not c:s['missing_cost']+=1;continue
  # A05: GMV already includes coupon; refund once; one product/order assumption.
  s['cost']+=Decimal(c['product_cost_krw'])+Decimal(c['shipping_cost_krw'])+Decimal(r['gmv_krw'])*Decimal(c['channel_fee_pct'])/100+Decimal(c['return_logistics_cost_krw'])*return_count.get(r['order_id'],0)
 for r in spend:
  if r['spend_date']<='2026-07-01':stats[r['campaign_id']]['marketing_spend']+=int(r['ad_cost_krw'])
 for s in stats.values():
  contribution=Decimal(s['gmv']-s['refund']-s['marketing_spend'])-s.pop('cost')
  s['contribution']=float(contribution) if not s['missing_cost'] else None
  s['nominal_roas']=s['gmv']/s['marketing_spend'] if s['marketing_spend'] else None
  s['real_roas']=float(contribution/s['marketing_spend']) if s['marketing_spend'] and not s['missing_cost'] else None
  s['refund_rate']=s['refund']/s['gmv'] if s['gmv'] else None
 rank=sorted((s for s in stats.values() if s['real_roas'] is not None),key=lambda s:s['real_roas'],reverse=True)
 for i,s in enumerate(rank):s['rank']=i+1;s['rank_population']=len(rank)
 return {'campaigns':stats,'sources':sources,'as_of':'2026-07-01','provenance':'계산 결과','assumptions':['표본 주문 집단: 기준일까지 주문과 연결된 기준일까지 확인 환불. 캠페인별 실제 주문 시작/종료 표시.','주문당 제품 1개, 배송 1회. 반품 물류비는 반환 행당 1회.','채널 수수료는 쿠폰 반영 후 GMV 기준. 환불 시 원가·수수료 회수 없음 가정.','GMV에서 쿠폰을 재차 차감하지 않고 환불은 한 번 차감. ad_cost 전액 사용, 포함된 influencer_fee 재가산 금지.','표본 상대 비교이며 미래 성과 보장·전사 현금 환산 근거가 아님. 비용 가정이 달라지면 재계산 필요.']}

def for_case(case):
 p=case.get('marketing',{});ref=p.get('reference') or {};campaign=ref.get('plan',{}).get('campaign_id') or ref.get('campaign',{}).get('campaign_id')
 if not campaign and p.get('reference_plan_id'):
  from app.marketing import REFERENCE
  campaign=next((r['campaign_id'] for r in REFERENCE['plans']['rows'] if r['plan_id']==p['reference_plan_id']),None)
 data=sample()
 return {k:v for k,v in data.items() if k!='campaigns'}|{'sample':data['campaigns'].get(campaign),'reference_campaign':campaign}
