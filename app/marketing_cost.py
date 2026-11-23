"""Sample-grounded marketing budget drafts, never company-wide cash extrapolation."""
import json,math,statistics
from datetime import date
from functools import lru_cache
from pathlib import Path
from app.formulas import run
MODEL='MARKETING-COST-1'
@lru_cache(maxsize=1)
def reference():return json.loads((Path(__file__).resolve().parent.parent/'data/marketing_cost_reference.json').read_text())
def estimate(raw,data,asof,start,end):
 if raw is None:return {'enabled':False,'recommended_budget':None,'items':[],'provenance':'미산정'}
 if not isinstance(raw,dict):raise ValueError('마케팅 비용 산정 조건을 확인하세요.')
 media=raw.get('media',[])
 if not isinstance(media,list) or any(not isinstance(m,str) for m in media) or len(media)!=len(set(media)) or any(m not in ['인플루언서','퍼포먼스','오프라인','쿠폰·프로모션'] for m in media):raise ValueError('마케팅 비용의 집행 매체를 확인하세요.')
 from app.domain import number
 mode=raw.get('budget_mode')
 if mode not in [None,'items','direct']:raise ValueError('마케팅 예산 입력 방식을 확인하세요.')
 extra=number(raw.get('other_cost',0),'별도 마케팅비')
 manual=raw.get('manual_costs',{})
 if not isinstance(manual,dict) or any(k not in media for k in manual):raise ValueError('마케팅 비용 항목의 매체를 확인하세요.')
 clean={}
 for medium,parts in manual.items():
  if not isinstance(parts,dict) or any(k not in ['fixed','variable'] for k in parts):raise ValueError('마케팅 비용 항목을 확인하세요.')
  clean[medium]={k:number(v,medium+' '+k+' 비용') for k,v in parts.items() if v not in [None,'']}
 days=(date.fromisoformat(end)-date.fromisoformat(start)).days+1
 ref=reference();campaigns={c['campaign_id']:c for c in ref['campaigns'] if c['end_date']<=asof and c['product_line']==raw.get('product_line') and (not raw.get('country') or c['country']==raw['country'])};items=[];missing=[]
 for medium in media:
  spend=[s for s in ref['spend'] if s['campaign_id'] in campaigns and s['media']==medium and s['spend_date']<=asof]
  if medium in ['인플루언서','퍼포먼스']:
   if raw.get('platform'):spend=[s for s in spend if s['platform']==raw['platform']]
   if raw.get('sns_format'):spend=[s for s in spend if s['sns_format']==raw['sns_format']]
  if medium=='인플루언서' and raw.get('influencer_id'):spend=[s for s in spend if campaigns[s['campaign_id']]['influencer_id']==raw['influencer_id']]
  grouped={}
  for s in spend:
   c=campaigns[s['campaign_id']];g=grouped.setdefault(s['campaign_id'],{'campaign_id':s['campaign_id'],'start':c['start_date'],'end':c['end_date'],'duration_days':(date.fromisoformat(c['end_date'])-date.fromisoformat(c['start_date'])).days+1,'cost':0,'included_fee':0,'spend_ids':[]})
   fee=s['influencer_fee_krw']
   if fee=='NONE' and medium=='인플루언서':raise ValueError('인플루언서 비용의 포함 범위를 확인하세요.')
   fee=0 if fee=='NONE' else int(fee);cost=int(s['ad_cost_krw'])
   if fee>cost:raise ValueError('광고비보다 큰 포함 수수료가 있습니다. 원본 범위를 확인하세요.')
   g['cost']+=cost;g['included_fee']+=fee;g['spend_ids'].append(s['spend_id'])
  observations=list(grouped.values())
  if not observations:
   missing.append(medium+' 비교 자료 없음 · 직접 입력 또는 견적 필요')
   m=clean.get(medium,{})
   items.append({'media':medium,'available':False,'observations':[],'chosen_fixed':m.get('fixed'),'chosen_variable':m.get('variable'),'fixed_manual':'fixed' in m,'variable_manual':'variable' in m});continue
  fixed=statistics.median(g['included_fee'] for g in observations);daily=statistics.median((g['cost']-g['included_fee'])/g['duration_days'] for g in observations)
  fixed_budget=run(data,'marketing_fixed_budget',reference_fixed=fixed)
  variable_budget=run(data,'marketing_variable_budget',reference_daily=daily,campaign_days=days)
  m=clean.get(medium,{})
  items.append({'chosen_fixed':m.get('fixed',fixed_budget),'chosen_variable':m.get('variable',variable_budget),'fixed_manual':'fixed' in m,'variable_manual':'variable' in m,'media':medium,'available':True,'campaign_count':len(observations),'reference_fixed':fixed,'reference_daily':daily,'fixed_budget':fixed_budget,'variable_budget':variable_budget,'subtotal':fixed_budget+variable_budget,'observations':observations,'confidence':'참고 관측 부족' if len(observations)<3 else '참고 비교 가능'})
 fixed_total=sum(i.get('fixed_budget',0) for i in items);variable_total=sum(i.get('variable_budget',0) for i in items)
 total=run(data,'marketing_execution_budget',fixed_budget=fixed_total,variable_budget=variable_total,other_cost=extra) if media and not missing else None
 complete=bool(media) and all(i['chosen_fixed'] is not None and i['chosen_variable'] is not None for i in items)
 adopted=run(data,'marketing_execution_budget',fixed_budget=sum(i['chosen_fixed'] for i in items),variable_budget=sum(i['chosen_variable'] for i in items),other_cost=extra) if complete else None
 needs_reference=any(i['available'] and (not i['fixed_manual'] or not i['variable_manual']) for i in items)
 return {'enabled':True,'model':MODEL,'inputs':{k:raw.get(k) for k in ['media','product_line','country','platform','sns_format','influencer_id']}|{'other_cost':extra,'manual_costs':clean,**({'budget_mode':mode} if mode else {})},'recommended_budget':total,'adopted_budget':adopted,'scope_requires_confirmation':needs_reference,'items':items,'fixed_budget':fixed_total,'variable_budget':variable_total,'other_cost':extra,'missing':missing,'campaign_days':days,'sources':ref['sources'],'provenance':'참가자 가정 / 계산 결과','method':'동일 제품라인·국가·선택 매체(해당 시 플랫폼·포맷·인플루언서)의 종료된 캠페인 비교. 포함 인플루언서비의 캠페인별 중앙값을 고정비로, 나머지 광고비/캠페인 달력일수의 중앙값×신규 기간을 변동비로 사용. ad_cost에 포함된 fee를 재가산하지 않음.','limitations':['마케팅 자료는 대표 표본. 회사 전체 규모나 실제 견적을 입증하지 않음. 기안의 적용 범위·가격·매체 횟수 확인 필요.','기간에 비례하는 변동비와 캠페인당 고정비 구분은 참가자 가정. 인과 추정이나 계약 조건이 아님.','쿠폰·제작비·추가 행사비는 자료 부족 시 직접 입력. 상품 조달·물류·반품·채널 수수료와 구분.','캠페인 집행 예산은 마케팅 비용. 상품 조달비는 별도 표시·발주 검토하며 원가/조달비를 마케팅비로 중복 합산하지 않음.']}
