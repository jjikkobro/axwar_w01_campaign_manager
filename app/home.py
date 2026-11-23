"""Role landing projection. Campaign work only; administration is separate."""
import re
from app.execution import projection
OUTSIDE=re.compile(r'overdue:|finance:contract:|contract_notice|연간전속|전속계약|연체\s*(회수|확인)')
ENTRY={'마케팅':'MKT_1_Proposal','SCM':'SCM_1_Check','재무':'FIN_1_Review','승인권자':'APR_1_CEO'}
def campaign_task(task):
 return bool(task.get('case_id')) and not OUTSIDE.search(' '.join(str(task.get(k,'')) for k in ['id','key','title']))
def manual_event(e,role):
 name=e.get('event','')
 return e.get('role')==role and not OUTSIDE.search(name+' '+str(e.get('detail',{}).get('type',''))) and name.startswith(('마케팅 기안','마케팅 계획','캠페인 검토 요청','SCM 검토','기존 발주 회신','재무 검토 ','역할별 업무 ','운영 확장 ','협조 회신','계획 수정','근거 파일 첨부'))
def build(cases,tasks,events,data,config,role,project=projection):
 if role not in ENTRY:raise ValueError('담당 역할을 선택하세요.')
 todo=[];processed=[]
 for c in cases:
  if not c.get('marketing'):continue
  cid=c['id'];p=c['marketing'];x=project({**{k:v for k,v in c.items() if k not in ['id','version']},'_case_id':cid},data,config);closed=bool(x.get('closed') or x.get('withdrawn'));stage=x['stage']
  owner={1:'마케팅',2:'SCM',3:'재무',4:'승인권자',5:'SCM',6:'SCM',7:'마케팅'}[stage]
  if x['status']=='보류·재검토':owner='마케팅'
  if x['status'] in ['조건 이행·재승인 대기','SCM·재무 협의 대기']:owner='SCM'
  mine=[t for t in tasks if t.get('case_id')==cid and t.get('role')==role and t.get('status')=='대기' and campaign_task(t)]
  handled=any(e.get('case_id')==cid and manual_event(e,role) for e in events)
  # Handoff tasks remain visible as context, not as a second marketing turn.
  handed_off=role=='마케팅' and not closed and owner!=role and 2<=stage<=6
  if role=='마케팅' and stage>=2:handled=True
  pending=bool(mine or (not closed and owner==role)) and not handed_off
  if not pending and not handled:continue
  screen=ENTRY[role]
  if role=='SCM':screen='SCM_3_PO' if stage==5 else 'SCM_5_Receipt' if stage>=6 else 'SCM_1_Check'
  if role=='승인권자':screen='APR_1_CEO' if any(t['authority']=='CEO/이사회' and t['kind'] in ['캠페인집행','재고발주'] for t in x['targets']) else 'APR_2_Normal'
  if role=='마케팅' and stage>=7:screen='MKT_4_Close'
  if role=='마케팅' and x['status']=='보류·재검토':screen='MKT_3_Hold'
  waiting=role=='마케팅' and not closed and owner!=role and 2<=stage<=6
  if waiting:screen='MKT_2_Wait'
  if not pending:screen={'마케팅':'MKT_4_Close' if closed or stage==7 else 'MKT_2_Wait','SCM':'SCM_2_WaitApproval','재무':'FIN_2_Wait'}.get(role,screen)
  due=min([t['due'] for t in mine if t.get('due')] or [p.get('contract_deadline') or p['start']])
  row={'id':cid,'title':c['title'],'campaign_name':p.get('campaign_name') or c['title'],'start':p['start'],'end':p['end'],'deadline':due,'stage':stage,'status':x['status'],'owner':owner,'closed':closed,'screen':screen,'tasks':[{'id':t['id'],'title':t['title']} for t in mine],'action_tab':None,'handled':handled,'waiting':waiting}
  if pending:
   ids=' '.join(t['id'] for t in mine)
   row['action_tab']='demand' if 'demand:verify' in ids else 'consult' if any(k in ids for k in ['consult:','followup:','question:']) else 'portfolio' if 'portfolio:' in ids else None
   if waiting or (role=='마케팅' and stage==7 and not closed):row['action_tab']=None
   todo.append(row)
  else:processed.append(row)
 todo.sort(key=lambda r:(r['deadline'],r['start'],r['id']));processed.sort(key=lambda r:(r['closed'],r['deadline'],r['id']))
 return {'role':role,'todo':todo,'processed':processed,'review_date':config['review_date'],'role_mode':'시연용 부서 역할 선택 · 개인별 인증 아님'}
