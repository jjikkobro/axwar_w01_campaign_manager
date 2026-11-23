"""Marketing plan sharing, before SCM review. Does not approve procurement."""
import json
from pathlib import Path
from decimal import Decimal, InvalidOperation
from app.domain import day, number
from app.policy import PROJECT_POLICY

REFERENCE = json.loads((Path(__file__).resolve().parent.parent/'data/marketing_reference.json').read_text())

def text(value, label, required=False, limit=4000):
 if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):
  raise ValueError(label+' 입력을 확인하세요.')
 return value.strip()

def validate(plan, datasets):
 if not isinstance(plan,dict):raise ValueError('기안 형식을 확인하세요.')
 result={}
 mode=plan.get('submission_mode')
 if mode not in [None,'legacy','estimate_only']:raise ValueError('신청 유형을 확인하세요.')
 if mode:result['submission_mode']=mode
 labels={'title':'건명','author':'작성자','department':'작성 부서','purpose':'목적·배경','performance_unknown_reason':'성과 미확인 사유','budget':'요청 예산','expected_gmv':'예상 GMV','group_total':'소속 기안 총액'}
 required={'title','author','department','purpose'}
 if plan.get('performance_status','미확인')=='미확인':required.add('performance_unknown_reason')
 for key in ['title','author','department','purpose','target','method','country','sns_channel','sns_format','sales_channel','influencer_id','position','place','performance_evidence','performance_unknown_reason','gmv_basis','group_id','group_basis','budget_basis']:
  result[key]=text(plan.get(key,''),labels.get(key,key),key in required,120 if key=='title' else 4000)
 for key in ['as_of','start','end','written_date']:
  day(plan.get(key));result[key]=plan[key]
 if not day(result['as_of'])<=day(result['start'])<=day(result['end']) or (day(result['end'])-day(result['as_of'])).days>180:raise ValueError('기준일 ≤ 시작일 ≤ 종료일, 최대 180일입니다.')
 for key in ['settlement_date','contract_deadline']:
  result[key]=None if mode=='estimate_only' else plan.get(key) or None
  if result[key]:day(result[key])
 draft=plan.get('settlement_draft')
 if draft is not None:
  if not isinstance(draft,dict):raise ValueError('지급일 초안을 확인하세요.')
  draft_date=draft.get('date');day(draft_date)
  result['settlement_draft']={'date':draft_date,'basis':text(draft.get('basis',''),'지급일 초안 근거',True),'provenance':'참가자 가정 · 재무 확인 전'}
 else:result['settlement_draft']=None
 for key in ['budget','expected_gmv','group_total']:
  result[key]=None if plan.get(key) in ('',None) else number(plan[key],labels[key])
 result['expected_contribution']=None
 if plan.get('expected_contribution') not in ('',None):
  try:
   amount=Decimal(str(plan['expected_contribution']))
   if not amount.is_finite() or amount!=amount.to_integral_value():raise ValueError()
   result['expected_contribution']=int(amount)
  except (InvalidOperation,ValueError):raise ValueError('공헌이익은 유한한 정수 원 단위입니다.')
 media=plan.get('media',[])
 if not isinstance(media,list) or any(m not in ['인플루언서','퍼포먼스','오프라인','쿠폰·프로모션'] for m in media):raise ValueError('집행 매체를 확인하세요.')
 result['media']=list(dict.fromkeys(media))
 result['campaign_name']=text(plan.get('campaign_name',plan.get('title','')),'캠페인명',True)
 if media:
  for k in ['country','sales_channel','target']:
   if not result[k]:raise ValueError('국가·판매채널·제품라인을 입력하세요.')
  if '인플루언서' in media and result['influencer_id'] not in {i['influencer_id'] for i in REFERENCE['influencers']['rows']}:raise ValueError('인플루언서를 선택하세요.')
  if any(m in media for m in ['인플루언서','퍼포먼스']) and (not result['sns_channel'] or not result['sns_format']):raise ValueError('SNS 플랫폼·포맷을 입력하세요.')
 result['performance_status']=plan.get('performance_status','미확인')
 if result['performance_status'] not in ['미확인','검토 자료 있음']:raise ValueError('성과 확인 구분을 선택하세요.')
 if result['performance_status']=='검토 자료 있음' and not result['performance_evidence']:raise ValueError('성과·비용 범위·환불 가정의 근거를 작성하세요.')
 if result['performance_status']=='미확인' and result['expected_contribution'] is not None:raise ValueError('미확인 성과에 확정 공헌이익을 입력하지 마세요.')
 if result['group_total'] is not None and (not result['group_id'] or not result['group_basis'] or result['budget'] is not None and result['group_total']<result['budget']):raise ValueError('묶음 총액의 ID·근거·예산을 확인하세요.')
 ref_id=plan.get('reference_plan_id','')
 original=next((r for r in REFERENCE['plans']['rows'] if r['plan_id']==ref_id),None)
 if ref_id and not original:raise ValueError('원본 기안 ID를 확인하세요.')
 campaign=next((r for r in REFERENCE['campaigns']['rows'] if original and r['campaign_id']==original['campaign_id']),None)
 result['reference_plan_id']=ref_id
 result['reference']={'plan':original,'campaign':campaign,'provenance':'원본 사실','sources':{k:{'source':REFERENCE[k]['source'],'sha256':REFERENCE[k]['sha256']} for k in ['plans','campaigns']}} if original else None
 items=plan.get('items')
 if not isinstance(items,list) or not 0<=len(items)<=14:raise ValueError('제품은 최대 14개입니다.')
 scope=plan.get('scope_skus',[i.get('sku_id') for i in items])
 if not isinstance(scope,list) or len(scope)>14 or len(set(scope))!=len(scope) or any(s not in {r['sku_id'] for r in datasets['sku']['rows']} for s in scope):raise ValueError('대상 SKU 범위를 확인하세요.')
 if any(i.get('sku_id') not in scope for i in items):raise ValueError('수요 입력 SKU는 대상 범위에 있어야 합니다.')
 result['scope_skus']=scope;result['scope_basis']=text(plan.get('scope_basis',''),'대상 SKU 범위 근거')
 seen=set();result['items']=[]
 for item in items:
  if not isinstance(item,dict):raise ValueError('제품별 입력 형식을 확인하세요.')
  sku=item.get('sku_id')
  if sku in seen or not any(r['sku_id']==sku for r in datasets['sku']['rows']):raise ValueError('중복 또는 알 수 없는 SKU입니다.')
  seen.add(sku)
  unit=item.get('unit','EA/주')
  if unit not in ['EA/주','EA/기간']:raise ValueError('수요 단위를 선택하세요.')
  qty=number(item.get('demand'),'추가 수요')
  start=item.get('start');end=item.get('end')
  if not day(result['start'])<=day(start)<=day(end)<=day(result['end']):raise ValueError('제품별 수요 기간은 캠페인 기간 안이어야 합니다.')
  basis=text(item.get('basis',''),'수요 근거',True)
  confidence=item.get('confidence','미확인')
  if confidence not in ['낮음','보통','높음','미확인']:raise ValueError('수요 신뢰 수준을 확인하세요.')
  overlap=item.get('overlap','')
  if overlap not in ['기존 판매 제외한 순증','중복 여부 미확인']:raise ValueError('기존 판매와의 중복 여부를 확인하세요.')
  days=(day(end)-day(start)).days+1
  # Keep rational conversion; daily simulation uses float, never rounded into a commitment.
  total=qty*days/7 if unit=='EA/주' else qty
  result['items'].append({'sku_id':sku,'demand':qty,'unit':unit,'start':start,'end':end,'basis':basis,'confidence':confidence,'overlap':overlap,'total_quantity':total,'provenance':'참가자 가정','conversion_provenance':'계산 결과','conversion_basis':'기간에 균등 배분 · EA/주 × 적용일수 ÷ 7' if unit=='EA/주' else '기간 전체 EA를 적용일수에 균등 배분'})
 result['provenance']='참가자 가정';result['rule_id']=PROJECT_POLICY['id']
 return result

def case_from(plan,datasets):
 p=validate(plan,datasets);first=p['items'][0] if p['items'] else {'sku_id':None,'total_quantity':0}
 # Legacy aliases refer only to the first product, never summed demand from other SKUs.
 return {'title':p['title'],'sku_id':first['sku_id'],'quantity':first['total_quantity'],'start':p['start'],'end':p['end'],'as_of':p['as_of'],'demand_status':'가정','evidence':p['purpose'],'marketing':p,'record_kind':'marketing_plan','approval_type':None,'requested_amount':None,'requested_payment_date':None,'contract_deadline':p['contract_deadline'],'value_provenance':{'request':'참가자 가정','original_reference':'원본 사실','rules':'내부 통제'}}

def route():
 return {'authority':'SCM 검토 후 승인 대상 구분','status':'계획 공유 · 승인 미확정','blocked':True,'provenance':'계산 결과','classification_provenance':'내부 통제','rule_version':PROJECT_POLICY['version'],'scenario':'후속 재무 검토 필요','reason':['마케팅 계획 공유는 캠페인 집행 또는 발주 승인이 아닙니다.','예산을 약정 유출액으로 자동 반영하지 않습니다.','SCM 공급 검토 및 재무 유출일·신규 여부 확인 전 승인·발주를 진행할 수 없습니다.']}

def tasks(case):
 stage=case.get('marketing_stage')
 if stage=='작성 중' or not stage:return []
 p=case['marketing'];result=[{'key':'marketing:scm','title':'캠페인 계획의 재고·입고표 대조','role':'SCM','provenance':'내부 통제','source':'세계관_BPMN/W01.html · 계획 공유 후 SCM 대조','human_review_required':True}] if stage in ['SCM 검토 요청','SCM 추가 확인 대기','SCM 재검토 필요'] else []
 if p['performance_status']=='미확인':result.append({'key':'marketing:performance','title':'기존 실질 성과·비용 범위 확인','role':'마케팅','provenance':'내부 통제','source':'mkt_meeting_notes_ms.md; approval_authority_policy.md','reason':p['performance_unknown_reason']})
 if p['settlement_date'] and p['contract_deadline'] and p['settlement_date']<p['contract_deadline']:result.append({'key':'marketing:dates','title':'정산일이 계약기한보다 빠른 원본·요청 날짜 확인','role':'마케팅','provenance':'내부 통제'})
 return result

def validate_submission(plan):
 """An explicit 0 KRW budget is valid; missing or invalid amounts are not."""
 if not plan.get('media'):raise ValueError('집행 매체를 선택하세요.')
 if plan.get('budget') in [None,'']:raise ValueError('캠페인 집행 예산을 입력하세요. 추가 비용이 없으면 0원을 입력할 수 있습니다.')
 number(plan['budget'],'캠페인 집행 예산')


def submission_cash_window(plan,bundle):
 """Submission guard only; draft saving and original dates remain unchanged."""
 calendar=next(iter(bundle['scenarios'].values()))['calendar']
 start,end=calendar[0]['date'],calendar[-1]['date']
 payment=plan.get('settlement_date') or (plan.get('settlement_draft') or {}).get('date')
 for label,value in [('캠페인 시작일',plan.get('start')),('캠페인 종료일',plan.get('end')),('집행비 지급예정일',payment)]:
  if not value:raise ValueError(label+'을 입력하세요. 예측일도 직접 확인·수정할 수 있습니다.')
  day(value)
  if not start<=value<=end:raise ValueError(label+' '+value+'은 현금 전망 기간('+start+' ~ '+end+') 밖입니다. 현재 자료로 재무 판정이 불가능하여 신청할 수 없습니다. 일정을 검토하거나 해당 기간 현금 자료와 전망 범위를 갱신하세요.')
 return {'start':start,'end':end,'payment_date':payment}
