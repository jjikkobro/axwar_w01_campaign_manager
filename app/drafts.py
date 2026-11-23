"""Optional Responses API draft; text never drives workflow mutations."""
import json,os
from urllib.request import Request,urlopen
from app.policy import PROJECT_POLICY

def packet(case,calculation):
 finance=calculation['finance'];route=calculation['routing'];a=case.get('financial_assessment') or {}
 active=finance['active_breach_dates']
 return {'operational_context':calculation.get('operational_context'),'project_policy':PROJECT_POLICY,'evidence_sources':calculation.get('evidence_sources',{}),'calculation_basis':{'sales_weeks':calculation.get('weeks',[]),'assumptions':calculation.get('assumptions',[]),'case_as_of':case['as_of'],'demand_evidence':case.get('evidence','미확인')},'marketing_plan':case.get('marketing'),'product_results':[{'sku_id':x['sku']['sku_id'],'cover':x['cover'],'first_short':x['first_short'],'weeks':x['weeks'],'demand':x.get('demand')} for x in calculation.get('items',[])],'title':case['title'],'sku_id':case['sku_id'],'stock_cover':calculation.get('cover'),'first_short':calculation.get('first_short'),'cash_scenario':route.get('scenario'),'breach_start':active[0] if active else None,'breach_end':active[-1] if active else None,'routing':route,'applicable_clause':'approval_authority_policy: 하회 예상 구간 신규 약정 우선 / 승인 유형별 전결','finance_opinion':a.get('opinion','미확인'),'alternatives':a.get('alternatives','지급일 분할 협의·발주 감량 등은 담당자 확인 필요'),'replies':[{'role':r['role'],'result':r['result'],'message':r['message'],'provenance':r.get('provenance','모의 회신')} for r in case.get('replies',[])][-8:],'suggested_state':('SCM 재고·입고표 대조 요청' if case.get('marketing') else '재무 확인 요청' if route['blocked'] else '사람의 상신·승인 검토'),'provenance':'계산 결과','auto_approved':False}

def complete(payload_data,instructions):
 from app.ai_settings import load,public
 from app.prompt_settings import BOUNDARY,FORMAT
 from urllib.error import HTTPError
 config=load()
 if not public(config)['configured']:raise ValueError('관리자에서 OpenAI API 키와 사용 모델을 설정하세요.')
 payload={'model':config['model'],'store':False,'instructions':BOUNDARY+'\n'+FORMAT+'\n단계별 검토 지침:\n'+instructions,'input':json.dumps(payload_data,ensure_ascii=False),'max_output_tokens':3000}
 if config['model'].startswith('gpt-5'):payload['reasoning']={'effort':'low'}
 request=Request(config['base_url']+'/responses',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+config['api_key']})
 try:
  with urlopen(request,timeout=30) as response:result=json.loads(response.read(200000))
  text='\n'.join(part.get('text','') for item in result.get('output',[]) for part in item.get('content',[]) if part.get('type')=='output_text')
  if not text.strip():raise ValueError('GPT가 검토 문장을 반환하지 않았습니다. 모델과 출력 한도를 확인하세요.')
 except HTTPError as e:
  raise ValueError({401:'OpenAI API 키를 확인하세요.',403:'해당 API 키의 모델 사용 권한을 확인하세요.',404:'OpenAI에서 사용할 수 있는 모델명을 확인하세요.',429:'OpenAI 사용 한도 또는 결제 상태를 확인하세요.'}.get(e.code,'OpenAI 연결에 실패했습니다. 잠시 후 다시 시도하세요.')) from None
 except ValueError:raise
 except Exception:raise ValueError('GPT 응답을 받지 못했습니다. 연결 상태를 확인하고 다시 시도하세요.') from None
 return {'mode':'GPT 검토 초안 · 사람 확인 필요','text':text[:12000],'provenance':'AI 생성 · 미검증 초안','model':config['model'],'unverified':True}

def generate(case,calculation):
 p=packet(case,calculation)
 from app.ai_settings import public
 if not public()['configured']:
  return {'mode':'규칙 기반 초안 · AI 미연결','packet':p,'text':f"{'제품별 검토 패킷 참조 · 대표 SKU ' if case.get('marketing') else ''}{p['sku_id']} 검토. 커버 {p['stock_cover']}주, 첫 부족 {p['first_short'] or '기간 내 없음'}. 결재선 {p['routing']['authority']}. 재무 의견: {p['finance_opinion']}. 대안: {p['alternatives']}. 제안 상태: {p['suggested_state']}. 사람의 확인 전 승인·발주·상태 변경 없음. 근거 파일·계산 기간·가정은 아래 패킷에서 확인하세요.",'provenance':'계산 결과'}
 return {**complete(p,calculation.get('review_prompt') or '캠페인 근거를 검토하여 위험·대안·확인 질문을 제안한다.'),'packet':p}
