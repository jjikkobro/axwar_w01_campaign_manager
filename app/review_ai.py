"""Read-only stage review: authoritative calculations -> GPT text, never business actions."""
from app import db,scm
from app.ai_settings import public
from app.prompt_settings import STAGES,effective
from app.drafts import complete
from app.execution import projection
from app.finance_review import view,initial_review
from app.formulas import revision

def context(conn,raw,role):
 stage=raw.get('stage')
 if stage not in STAGES or STAGES[stage]['role']!=role:raise ValueError('현재 담당 단계에서 GPT 검토를 요청하세요.')
 data=db.datasets(conn);config=db.finance(conn);cid=raw.get('id')
 if raw.get('calculation_revision') and raw['calculation_revision']!=revision(data,config)['revision']:raise ValueError('공통 계산 기준이 변경되었습니다. 새로고침 후 다시 검토하세요.')
 if not cid or stage=='marketing' and raw.get('inputs'):
  if stage!='marketing':raise ValueError('검토할 캠페인을 선택하세요.')
  from app.ax_planning import preview
  plan=preview(raw.get('inputs'),data,config)
  c=raw.get('campaign') or {}
  if not isinstance(c,dict):raise ValueError('캠페인 정보를 확인하세요.')
  c={k:str(c.get(k,''))[:200] for k in ['title','name','country','sales','pl']}
  result={'stage':stage,'campaign':c,'as_of':plan['inputs']['as_of'],'period':[plan['inputs']['start'],plan['inputs']['end']],'marketing_cost':plan['marketing_cost'],'items':[{k:r.get(k) for k in ['sku_id','name','chosen_weekly_extra','chosen_qty','chosen_unit_price','estimated_cost','regular_condition_required','campaign_min_before','campaign_min_after_assumption','price_source','evidence']} for r in plan['items']],'issues':plan['issues'],'pending':plan['scm_pending']+plan['finance_pending'],'cash':plan['cash']}
  version=None
  if cid:
   row=conn.execute('SELECT version FROM w01_cases WHERE id=%s',(cid,)).fetchone()
   if not row or row[0]!=raw.get('version'):raise ValueError('캠페인이 변경되었습니다. 새로고침 후 검토하세요.')
   version=row[0]
 else:
  row=conn.execute('SELECT body,version FROM w01_cases WHERE id=%s',(cid,)).fetchone()
  if not row or not row[0].get('marketing'):raise ValueError('캠페인 기안을 확인하세요.')
  case,version=row
  if raw.get('version')!=version:raise ValueError('캠페인이 변경되었습니다. 새로고침 후 검토하세요.')
  case={**case,'_case_id':cid};s=scm.analysis(case,data,config);financial=view(case,data,config,case.get('finance_review') or initial_review(case));flow=projection(case,data,config)
  result={'stage':stage,'campaign':case['marketing'],'workflow':{'stage':flow['stage'],'status':flow['status']},'department_reviews':{'scm':{k:case.get('scm',{}).get('review',{}).get(k) for k in ['direction','reason','evidence','alternatives','items','supply_plan']},'finance':{k:case.get('finance_review',{}).get(k) for k in ['opinion','reason','evidence','alternatives']}},'supply':{'recommendation':s['recommendation'],'items':[{k:r[k] for k in ['sku_id','weekly','campaign_min','first_short_in_campaign','data_complete','procurement','sources']} for r in s['items']]},'finance':{'recommendation':financial['recommendation'],'routes':financial['routes'],'confirmed':financial['confirmed'],'selected':financial['selected'],'errors':financial['errors']},'approved_scope':flow['targets'],'orders':flow['orders'],'supplier_reply':flow['receipt']}
 screen=raw.get('screen_draft') or {}
 if not isinstance(screen,dict) or len(__import__('json').dumps(screen,ensure_ascii=False))>24000:raise ValueError('작성 중인 검토 내용의 길이를 확인하세요.')
 result['screen_draft']={k:v for k,v in screen.items() if k in ['scm_proposal','finance_proposal','approval_choice','order_draft','receipt_draft']}
 result['screen_draft_provenance']='화면 작성 중인 담당자 가정 · 아직 저장·승인되지 않음'
 result['sources']={k:{'source':v.get('source'),'version':v.get('version'),'provenance':v.get('provenance','원본 사실')} for k,v in data.items() if k in ['sku','sales','inventory','purchase','cash','ar','ap','forecast']}
 result['calculation_context']=revision(data,config)
 return result,version

def generate(conn,raw,role):
 if not public()['configured']:raise ValueError('관리자에서 OpenAI API 키를 설정한 뒤 GPT 검토를 사용하세요.')
 packet,version=context(conn,raw,role);prompt=effective(conn,raw['stage'])
 result=complete(packet,prompt['prompt'])
 return {**result,'stage':raw['stage'],'case_version':version,'prompt_version':prompt['version'],'basis':scm.fingerprint(packet),'calculation_context':packet['calculation_context'],'boundary':'초안만 생성했습니다. 검토·승인·발주·금액·일정은 담당자가 결정합니다.'}
