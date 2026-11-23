"""Grounded optional AI drafts -> human-selected, typed follow-up work. Never approval."""
import copy,uuid
from app.demand import assess,signature
from app.portfolio import simulate
from app.finance_review import basis
from app.insights import forecast_comparison
from app.drafts import generate

def context(case,data,config):
 d=assess(case,data);p=simulate(data,case);f=forecast_comparison(case,data,config)
 return {'basis':signature({'finance':basis(case,data,config),'demand':d['basis'],'consultation':case.get('operations',{}).get('consultation')}),'demand':{'ready':d['ready'],'warnings':d['warnings'],'ranges':[{'sku_id':i['sku_id'],'input_weekly':i['input_weekly'],'low':i['evidence']['range_low'],'high':i['evidence']['range_high'],'observations':i['evidence']['observation_count']} for i in d['items']]},'portfolio':{'policy':p['policy'],'warnings':p['warnings'],'items':[{k:i[k] for k in ['sku_id','campaign_min','unknown_demand','other_case_ids']} for i in p['items']]},'forecast':f,'sources':['A01 §3·5','W01 미해결 지점 U1/U2/U3','sku_weekly_sales_ms','m_campaign_ms','w01_cases 수요 약속','w01_events 사건 이력'],'human_boundary':'제안 채택은 확인 요청/협의만 생성. 계획·결재선·승인·발주·지급을 AI가 확정하지 않음.'}
def propose(case,data,config,calculation,metadata):
 c=context(case,data,config);actions=[]
 if not c['demand']['ready']:actions.append({'id':'demand','type':'request','label':'수요 가정·대상 SKU·참고 범위 근거 확인 요청','to_role':'마케팅','reason':' / '.join(c['demand']['warnings']) or '수요 검토 미확정'})
 if any(i['campaign_min'] is not None and i['campaign_min']<0 and i['other_case_ids'] for i in c['portfolio']['items']):actions.append({'id':'consult','type':'consult','label':'SCM·재무 공동 수요/공급 조정 협의 열기','to_role':'SCM','reason':'동일 SKU의 승인 약속과 검토 수요를 합산할 때 공급 부족'})
 if any(r['reforecast_authority']=='CEO/이사회' for r in c['forecast']['rows']):actions.append({'id':'finance','type':'request','label':'하회구간 약정·대안 재무 확인 요청','to_role':'재무','reason':'금액·유출일·확정 시나리오 및 조정 대안 확인 필요'})
 if not actions:actions.append({'id':'review','type':'request','label':'상신 패킷·미확인 근거 담당자 검토 요청','to_role':'SCM','reason':'근거를 사람이 확인하고 후속 상신 여부 판단'})
 result=generate(case,{**calculation,'operational_context':c})
 return {'id':str(uuid.uuid4()),**metadata,'basis':c['basis'],'context':c,'text':result['text'],'mode':result['mode'],'model':result.get('model'),'unverified':True,'actions':actions,'status':'검토 대기','provenance':'계산 결과 · 미검증 보조 초안','note':'명시적 사람 채택 전 업무 상태/승인/계획 변경 없음.'}
def accept(case,data,config,proposal_id,action_id,role,metadata):
 b=copy.deepcopy(case);p=next((p for p in b.get('assistant_proposals',[]) if p['id']==proposal_id),None)
 if not p:raise ValueError('제안을 선택하세요.')
 if p.get('status')!='검토 대기':raise ValueError('이미 채택한 제안입니다.')
 if p['basis']!=context(b,data,config)['basis']:raise ValueError('제안 근거가 변경되었습니다. 최신 자료로 다시 생성하세요.')
 action=next((a for a in p['actions'] if a['id']==action_id),None)
 if not action:raise ValueError('허용된 제안 중 하나를 선택하세요.')
 if action['type']=='consult':
  if role not in ['SCM','재무']:raise ValueError('SCM/재무가 협의 개설을 채택합니다.')
  from app.operations import apply
  raw={**metadata,'operation':'consult_open','subject':action['reason'],'alternatives':[{'title':'현재 약속 유지하며 캠페인 수량·기간 재검토','marketing_effect':'수량·기간·상품 구성 조정안 검토','scm_effect':'기존 약속·확인 입고 대조','finance_effect':'신규 지급·분할·권한 재검토'}]}
  b,_=apply(b,data,config,raw,role,lambda _:metadata)
 else:
  b.setdefault('execution',{}).setdefault('notes',[]).append({**metadata,'role':role,'to_role':action['to_role'],'type':'보조 제안 채택 · '+action['label'],'reason':metadata['reason']+' / '+action['reason'],'proposal_id':proposal_id})
 p=next(p for p in b['assistant_proposals'] if p['id']==proposal_id);p.update(status='사람 채택',accepted_action=action_id,accepted_by=metadata)
 return b
