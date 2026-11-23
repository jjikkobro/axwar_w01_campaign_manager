"""Transactional projections and persistent work items; no auto approvals."""
import copy
from datetime import datetime, timezone
from psycopg.types.json import Jsonb
from app import db
from app.marketing import route as marketing_route, tasks as marketing_tasks
from app.finance import cash_bundle, routing, task_specs
from app.scm import stale, invalidate, task_specs as scm_tasks

def now():return datetime.now(timezone.utc).isoformat()

def reconcile(c,actor='시스템',reason='근거 갱신'):
 data=db.datasets(c);config=db.finance(c);bundle=cash_bundle(data,config)
 desired={}
 desired['global:followup:weekly_cash']=(None,{'key':'followup:weekly_cash','role':'재무','title':'매주 Masil 단독 일별 현금 재전망 확인','due':config['next_review_date'],'provenance':'내부 통제'})
 for spec in task_specs(None,bundle):desired['global:'+spec['key']]=(None,spec)
 for cid,b in c.execute('SELECT id,body FROM w01_cases FOR UPDATE').fetchall():
  b['_case_id']=cid
  if b.get('marketing') and stale(b,data):
   invalidate(b,reason)
   c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
   db.event(c,cid,actor,'SCM 근거 변경 · 재검토 필요',{'reason':reason,'provenance':'내부 통제'})
  before=copy.deepcopy(b.get('routing'));route=marketing_route() if b.get('marketing') else routing(b,bundle)
  b['routing']=route
  if before!=route:
   if b['status'] in ['승인','승인 대기','조건부 승인']:
    b['status']='재검토 필요';b['approval']=None
   c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
   db.event(c,cid,actor,'결재선 재판정',{'before':before,'after':route,'reason':reason,'route_changed':bool(before and before.get('authority')!=route['authority']),'provenance':'계산 결과','at':now()})
  from app.execution import task_specs as execution_tasks, projection
  from app.operations import task_specs as operations_tasks
  for spec in operations_tasks(b,data,config):desired[cid+':'+spec['key']]=(cid,spec)
  if b.get('marketing'):
   state=projection(b,data,config);owner={1:'마케팅',2:'SCM',3:'재무',4:'승인권자',5:'SCM',6:'SCM',7:'마케팅'}[state['stage']]
   if state['status']=='보류·재검토':owner='마케팅'
   if state['status'] in ['조건 이행·재승인 대기','SCM·재무 협의 대기']:owner='SCM'
   previous=b.get('workflow');current={'stage':state['stage'],'status':state['status'],'owner':owner}
   if not previous or any(previous.get(k)!=v for k,v in current.items()):
    stamp=now();elapsed=None
    if previous:
     entered=datetime.fromisoformat(previous['entered_at']);elapsed=max(0,(datetime.fromisoformat(stamp)-entered).total_seconds())
    current.update(entered_at=stamp,reason=reason,provenance='사건 이력 · 계산 결과')
    b['workflow']=current;c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
    db.event(c,cid,actor,'업무 단계 전이',{'before':previous,'after':current,'duration_seconds':elapsed,'reason':reason})
  for spec in execution_tasks(b,data,config):desired[cid+':'+spec['key']]=(cid,spec)
  if b['status'] not in ['회신 기록 완료','발주 전달']:
   for spec in (marketing_tasks(b)+scm_tasks(b) if b.get('marketing') else task_specs(b,bundle)):
    if b.get('marketing') and spec['key']=='scm:finance' and b.get('finance_review',{}).get('operation')=='submit' and __import__('app.finance_review',fromlist=['view']).view(b,data,config)['valid']:continue
    desired[cid+':'+spec['key']]=(cid,spec)
   from app.finance_review import task_specs as finance_review_tasks,view as finance_review_view
   for spec in finance_review_tasks(b):
    if spec['key']=='finance:approval':
     ps=projection(b,data,config)
     if not finance_review_view(b,data,config)['valid'] or ps['stage']!=4 or ps['status']!='승인 대기':continue
    desired[cid+':'+spec['key']]=(cid,spec)
   if b['status']=='보완 필요':desired[cid+':rework']=(cid,{'key':'rework','title':'반려·보완 사항 확인 후 재상신','role':'SCM','provenance':'내부 통제'})
   if b['status']=='조건부 승인':desired[cid+':conditions']=(cid,{'key':'conditions','title':'승인 조건 이행 근거 확보 후 사람 재승인','role':'SCM','provenance':'내부 통제'})
 for tid,(cid,spec) in desired.items():
  old=c.execute('SELECT body,status FROM w01_tasks WHERE id=%s',(tid,)).fetchone()
  if not old:
   spec={**spec,'created_at':now()}
   c.execute('INSERT INTO w01_tasks(id,case_id,body) VALUES (%s,%s,%s)',(tid,cid,Jsonb(spec)))
   db.event(c,cid,'시스템','확인요청 작업 생성',{'task_id':tid,**spec})
  elif old[1]=='대기' and {**old[0],**spec}!=old[0]:
   c.execute('UPDATE w01_tasks SET body=%s WHERE id=%s',(Jsonb({**old[0],**spec}),tid))
   db.event(c,cid,'시스템','확인요청 작업 갱신',{'task_id':tid,'before':old[0],'after':spec,'reason':reason})
  elif old[1]!='대기':
   c.execute("UPDATE w01_tasks SET status='대기',body=%s WHERE id=%s",(Jsonb({**old[0],**spec}),tid))
   db.event(c,cid,'시스템','확인요청 작업 재개',{'task_id':tid,'reason':reason})
 for tid,cid in c.execute("SELECT id,case_id FROM w01_tasks WHERE status='대기'").fetchall():
  if tid not in desired:
   status='완료'
   if ':scm:' in tid:
    current=c.execute('SELECT body FROM w01_cases WHERE id=%s',(cid,)).fetchone()
    body=current[0] if current else {}
    if ':scm:request:' in tid:
     key=tid.split(':scm:request:',1)[1]
     q=next((q for q in body.get('scm',{}).get('review',{}).get('requests',[]) if q['id']==key),None)
     if not q or q['status']!='완료':status='종료(전제 변경)'
    elif ':scm:finance' in tid or ':scm:payment:' in tid:status='종료(재검토)'
   c.execute('UPDATE w01_tasks SET status=%s WHERE id=%s',(status,tid))
   db.event(c,cid,'시스템','확인요청 작업 '+status,{'task_id':tid,'reason':reason,'provenance':'계산 결과'})
 return bundle
