"""Small PostgreSQL-backed prototype server; role selection is explicitly a demo."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from http.cookies import SimpleCookie
import base64, hashlib, hmac, json, os, secrets, time, uuid
from app import db
from app.marketing import REFERENCE, case_from
from app.policy import PROJECT_POLICY
from app import scm,formulas
from app.finance import cash_bundle, routing, RULES, SCENARIOS, PROVENANCE, AS_OF, validate_commitment
from app.workflow import reconcile, now
from app.domain import ROLES, SCHEMAS, parse_dataset, validate_case, validate_reply, calculate, transition
from psycopg.types.json import Jsonb

ROOT=Path(__file__).resolve().parent.parent
PASSWORD=os.environ.get('PROTOTYPE_PASSWORD','')
PUBLIC_ACCESS=os.environ.get('PUBLIC_ACCESS','').lower()=='true'
SESSION_KEY=os.environ.get('SESSION_SECRET') or secrets.token_hex(32)

class Conflict(Exception): pass

class Handler(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args): pass
 def respond(self,status,data,content_type='application/json; charset=utf-8',headers=None):
  payload=json.dumps(data,ensure_ascii=False,default=str).encode() if content_type.startswith('application/json') else data
  self.send_response(status);self.send_header('Content-Type',content_type)
  self.send_header('Content-Length',str(len(payload)));self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Cache-Control','no-store')
  self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
  for k,v in (headers or {}).items():self.send_header(k,v)
  self.end_headers();self.wfile.write(payload)
 def authorized(self):
  if PUBLIC_ACCESS:return True
  if not PASSWORD:return self.client_address[0] in ('127.0.0.1','::1')
  cookie=SimpleCookie()
  try:
   cookie.load(self.headers.get('Cookie','')); token=cookie['w01session'].value; expiry,signature=token.split('.')
   return int(expiry)>time.time() and hmac.compare_digest(signature,hmac.new(SESSION_KEY.encode(),expiry.encode(),hashlib.sha256).hexdigest())
  except (KeyError,ValueError):return False
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/healthz':return self.respond(200,{'ok':True})
  if path=='/api/session':
   authenticated=self.authorized()
   return self.respond(200,{'authenticated':authenticated,'mode':'누구나 접속' if PUBLIC_ACCESS else '공유 비밀번호' if PASSWORD else '로컬 전용','user':{'display_name':os.environ.get('PROTOTYPE_USER_NAME','').strip()[:120] if authenticated else '', 'provenance':'시연 프로필','individual_authentication':False}},headers={'Cache-Control':'no-store'})
  if path.startswith('/api/'):
   if not self.authorized():return self.respond(401,{'error':'먼저 접속 비밀번호를 입력하세요.'})
   try:
    with db.connect() as c:
     if path=='/api/ai-settings':
      from app.ai_settings import public
      return self.respond(200,public())
     if path=='/api/calculation-version':
      return self.respond(200,formulas.revision(db.datasets(c),db.finance(c)),headers={'Cache-Control':'no-store'})
     if path=='/api/case-version':
      cid=parse_qs(urlparse(self.path).query).get('id',[''])[0]
      row=c.execute('SELECT version FROM w01_cases WHERE id=%s',(cid,)).fetchone()
      if not row:return self.respond(404,{'error':'캠페인을 찾을 수 없습니다.'})
      return self.respond(200,{'id':cid,'version':row[0]})
     if path=='/api/prompt-settings':
      from app.prompt_settings import catalog,BOUNDARY
      role=parse_qs(urlparse(self.path).query).get('role',['마케팅'])[0]
      if role not in ROLES:raise ValueError('역할을 선택하세요.')
      return self.respond(200,{'prompts':catalog(c,role),'boundary':BOUNDARY,'runtime_applied':True})
     if path=='/api/formulas':
      from app.formulas import catalog,LOCKED
      role=parse_qs(urlparse(self.path).query).get('role',['마케팅'])[0]
      if role not in ROLES:raise ValueError('역할을 선택하세요.')
      config=db.finance(c)
      history=[{'role':r,'detail':d,'at':str(t)} for r,d,t in c.execute("SELECT role,detail,created_at FROM w01_events WHERE event='계산 산식 변경' ORDER BY seq DESC LIMIT 30")]
      return self.respond(200,{'version':config['version'],'role':role,'formulas':catalog(config,role),'locked':LOCKED,'history':history,'auth_mode':'공유 비밀번호 · 역할 선택은 시연용이며 개인별 부서 인증이 아님'})
     if path=='/api/operations':
      from app.insights import overview
      cases=[{**b,'_case_id':i,'id':i,'version':v} for i,b,v in c.execute('SELECT id,body,version FROM w01_cases')]
      events=[{'case_id':i,'role':r,'event':e,'detail':d,'at':str(t)} for i,r,e,d,t in c.execute('SELECT case_id,role,event,detail,created_at FROM w01_events ORDER BY seq')]
      return self.respond(200,overview(cases,db.tasks(c),events,db.datasets(c),db.finance(c)))
     if path=='/api/finance-preview':
      from app.finance_review import initial_review,view as financial_view
      import copy
      query=parse_qs(urlparse(self.path).query);cid=query.get('id',[''])[0];scenario=query.get('scenario',['union'])[0]
      if scenario not in ['union','exclude_pay','collect_pay','collect_exclude','exclude_exclude']:return self.respond(400,{'error':'계산 가정을 선택하세요.'})
      row=c.execute('SELECT body FROM w01_cases WHERE id=%s',(cid,)).fetchone()
      if not row or not row[0].get('marketing'):return self.respond(404,{'error':'캠페인을 찾을 수 없습니다.'})
      b={**row[0],'_case_id':cid};actual=db.finance(c);config=copy.deepcopy(actual)
      config['confirmed']=scenario!='union'
      if scenario!='union':config['selected']=scenario
      review=b.get('finance_review') or initial_review(b);result=financial_view(b,db.datasets(c),config,review)
      hypothetical=(scenario=='union' and actual.get('confirmed')) or (scenario!='union' and (not actual.get('confirmed') or scenario!=actual['selected']))
      result['hypothetical']=bool(hypothetical)
      if hypothetical:
       result['recommendation']['ready_to_request']=False
       result['recommendation']['blockers'].append('선택 가정의 재무 확정 필요')
       result['recommendation']['why'].append('선택 가정 계산 · 공식 재무 기준은 아직 변경하지 않음')
       if result['recommendation']['opinion']=='ok':result['recommendation']['opinion']='cond'
      return self.respond(200,result)
     if path=='/api/home':
      from app.home import build
      role=parse_qs(urlparse(self.path).query).get('role',['마케팅'])[0]
      if role not in ['마케팅','SCM','재무','승인권자']:return self.respond(400,{'error':'담당 역할을 선택하세요.'})
      cases=[{**b,'id':i,'_case_id':i,'version':v} for i,b,v in c.execute('SELECT id,body,version FROM w01_cases')]
      events=[{'case_id':i,'role':r,'event':e,'detail':d} for i,r,e,d in c.execute('SELECT case_id,role,event,detail FROM w01_events ORDER BY seq')]
      return self.respond(200,build(cases,db.tasks(c),events,db.datasets(c),db.finance(c),role))
     if path=='/api/state':
      data=db.datasets(c)
      if not set(SCHEMAS)<=set(data):return self.respond(503,{'error':'초기 데이터가 없습니다. 초기 자료를 등록하세요.'})
      cases=[{**b,'id':i,'version':v} for i,b,v in c.execute('SELECT id,body,version FROM w01_cases ORDER BY body->>\'created_at\' DESC')]
      events=[{'seq':s,'case_id':i,'role':r,'event':e,'detail':d,'at':str(t)} for s,i,r,e,d,t in c.execute('SELECT seq,case_id,role,event,detail,created_at FROM w01_events ORDER BY seq DESC LIMIT 150')]
      return self.respond(200,{'planning_catalog':__import__('app.planning',fromlist=['catalog']).catalog(data),'calculation_context':formulas.revision(data,db.finance(c)),'project_policy':PROJECT_POLICY,'marketing_reference':REFERENCE,'performance_reference':__import__('app.performance',fromlist=['sample']).sample(),'datasets':data,'cases':cases,'events':events,'schemas':{k:{'label':v[0],'role':v[1],'columns':v[2]} for k,v in SCHEMAS.items()},'finance':cash_bundle(data,db.finance(c)),'finance_version':db.finance(c)['version'],'tasks':db.tasks(c),'rules':RULES,'ai_configured':__import__('app.ai_settings',fromlist=['public']).public()['configured']})
     if path.startswith('/api/documents/'):
      doc=c.execute('SELECT name,content FROM w01_documents WHERE id=%s',(path.split('/')[-1],)).fetchone()
      if not doc:return self.respond(404,{'error':'첨부 파일이 없습니다.'})
      from urllib.parse import quote
      return self.respond(200,bytes(doc[1]),'application/octet-stream',{'Content-Disposition':"attachment; filename*=UTF-8''"+quote(doc[0])})
     if path.startswith('/api/cases/'):
      cid=path.split('/')[-1]; row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s',(cid,)).fetchone()
      if not row:return self.respond(404,{'error':'검토 건이 없습니다.'})
      docs=[{'id':i,'name':n,'role':r,'provenance':p,'at':str(t)} for i,n,r,p,t in c.execute('SELECT id,name,role,provenance,created_at FROM w01_documents WHERE case_id=%s ORDER BY created_at',(cid,))]
      row=({**row[0],'_case_id':cid},row[1]);data=db.datasets(c);calculation=calculate(row[0],data,db.finance(c))
      from app.finance_review import initial_review,view as financial_view
      initial=initial_review(row[0]) if not row[0].get('finance_review',{}).get('targets') else None
      initial_view=financial_view(row[0],data,db.finance(c),initial) if initial else None
      return self.respond(200,{'calculation_context':formulas.revision(data,db.finance(c)),'case':{**row[0],'id':cid,'version':row[1]},'calculation':calculation,'scm_calculation':scm.analysis(row[0],data,db.finance(c),calculation=calculation) if row[0].get('marketing') else None,'operational_schedule':__import__('app.execution',fromlist=['operational_schedule']).operational_schedule(row[0],data),'documents':docs,'tasks':[t for t in db.tasks(c) if t['case_id'] in (None,cid)],'execution':__import__('app.execution',fromlist=['projection']).projection(row[0],data,db.finance(c)) if row[0].get('marketing') else None,'history':[{'role':r,'event':e,'detail':d,'at':str(t)} for r,e,d,t in c.execute('SELECT role,event,detail,created_at FROM w01_events WHERE case_id=%s ORDER BY seq',(cid,))],'demand_validation':__import__('app.demand',fromlist=['assess']).assess(row[0],data),'portfolio':__import__('app.portfolio',fromlist=['simulate']).simulate(data,row[0]) if row[0].get('marketing') else None,'consultation':__import__('app.operations',fromlist=['consultation']).consultation(row[0]),'forecast_comparison':__import__('app.insights',fromlist=['forecast_comparison']).forecast_comparison(row[0],data,db.finance(c)),'performance_review':__import__('app.operations',fromlist=['performance']).performance(row[0],data,db.finance(c)['review_date']) if row[0].get('marketing') else None,'finance_review_view':__import__('app.finance_review',fromlist=['view']).view(row[0],data,db.finance(c)),'finance_review_initial':initial_view,'finance_review_draft':initial})
    return self.respond(404,{'error':'경로가 없습니다.'})
   except Exception:
    return self.respond(503,{'error':'서버 DB 연결 또는 초기화 상태를 확인하세요. 입력은 저장되지 않았습니다.'})
  files={'/review-presentation.js':'review-presentation.js','/budget-receipt.js':'budget-receipt.js','/marketing-cost.js':'marketing-cost.js','/calculation-sync.js':'calculation-sync.js','/scm-context.js':'scm-context.js','/identity.js':'identity.js',**{f'/fonts/ibm-plex-sans-kr/{p.name}':f'fonts/ibm-plex-sans-kr/{p.name}' for p in (ROOT/'web/fonts/ibm-plex-sans-kr').iterdir() if p.is_file()},**{f'/references/{p.name}':f'references/{p.name}' for p in (ROOT/'web/references').glob('*.html')},'/settings':'settings.html','/settings.js':'settings.js','/settings.css':'settings.css','/campaign':'campaign.html','/admin':'admin.html','/admin.js':'admin.js','/admin.css':'admin.css','/review-ai.js':'review-ai.js','/ax-planning.js':'ax-planning.js','/ax-planning.css':'ax-planning.css','/marketing-ux.js':'marketing-ux.js','/marketing-ux.css':'marketing-ux.css','/home.js':'home.js','/home.css':'home.css','/hub':'hub.html','/campaign-scope.js':'campaign-scope.js','/hub.js':'hub.js','/hub.css':'hub.css','/source-components.js':'source-components.js','/screen-adapter.js':'screen-adapter.js','/operations':'operations.html','/operations.js':'operations.js','/operations.css':'operations.css',**{f'/screens/{p.stem}.html':f'screens/{p.name}' for p in (ROOT/'web/screens').glob('*.html')},'/screens/manifest.json':'screens/manifest.json','/scm.js':'scm.js','/finance-screen.js':'finance-screen.js','/design.js':'design.js','/design.css':'design.css','/design-runtime.js':'design-runtime.js','/':'index.html','/fonts/NanumGothic-Regular.ttf':'fonts/NanumGothic-Regular.ttf'}
  if path not in files:return self.respond(404,{'error':'경로가 없습니다.'})
  p=ROOT/'web'/files[path]
  if p.suffix=='.json':return self.respond(200,json.loads(p.read_text()))
  mime='application/json' if p.suffix=='.json' else 'font/ttf' if p.suffix=='.ttf' else 'text/html' if p.suffix=='.html' else 'text/css' if p.suffix=='.css' else 'application/javascript'
  return self.respond(200,p.read_bytes(),mime+'; charset=utf-8')
 def do_POST(self):
  path=urlparse(self.path).path
  origin=self.headers.get('Origin')
  if origin and urlparse(origin).netloc!=self.headers.get('Host'):return self.respond(403,{'error':'다른 사이트의 요청은 허용하지 않습니다.'})
  try:
   length=int(self.headers.get('Content-Length',0))
   if length<1 or length>2_100_000:raise ValueError('요청 크기는 2MB 이하이어야 합니다.')
   body=json.loads(self.rfile.read(length))
   if not isinstance(body,dict):raise ValueError('입력 형식을 확인하세요.')
   if path=='/api/login':
    if not PASSWORD or not hmac.compare_digest(str(body.get('password','')),PASSWORD):return self.respond(401,{'error':'비밀번호를 확인하세요.'})
    expiry=str(int(time.time()+28800)); sig=hmac.new(SESSION_KEY.encode(),expiry.encode(),hashlib.sha256).hexdigest()
    secure='; Secure' if self.headers.get('X-Forwarded-Proto')=='https' else ''
    return self.respond(200,{'ok':True},headers={'Set-Cookie':f'w01session={expiry}.{sig}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{secure}'})
   if not self.authorized():return self.respond(401,{'error':'먼저 접속 비밀번호를 입력하세요.'})
   role=body.get('role')
   if role not in ROLES:raise ValueError('담당 역할을 선택하세요.')
   with db.connect() as c:
    # Serialise all changes with a transaction lock: a decision cannot race a dataset upload.
    c.execute('SELECT pg_advisory_xact_lock(7101245)')
    if path=='/api/ai-settings':
     from app.ai_settings import save
     result=save(body,role)
     db.event(c,None,role,'GPT 연결 설정 변경',{'provider':'OpenAI','model':result['model'],'enabled':result['enabled'],'key_changed':bool(body.get('api_key')),'key_cleared':body.get('clear_key') is True,'version':result['version']});c.commit()
     return self.respond(200,result)
    if path=='/api/ai-settings/test':
     if role!='SCM':raise ValueError('SCM 관리자 역할에서 연결을 확인하세요.')
     from app.drafts import complete
     result=complete({'purpose':'연결 확인 · 업무자료 없음'},'연결 확인 결과를 - OpenAI 연결 확인 한 줄로 답하세요.')
     return self.respond(200,{'ok':True,'model':result['model'],'message':'OpenAI 연결을 확인했습니다.'})
    if path=='/api/review-draft':
     from app.review_ai import generate
     result=generate(c,body,role)
     if body.get('id'):
      db.event(c,body['id'],role,'GPT 검토 초안 생성',{'stage':result['stage'],'model':result['model'],'prompt_version':result['prompt_version'],'basis':result['basis'],'case_version':result['case_version'],'text':result['text'],'provenance':'AI 생성 · 미검증 초안'})
      c.commit()
     return self.respond(200,result)
    if body.get('expected_calculation_revision') and path not in ['/api/formulas/test','/api/formulas/preview','/api/formulas/apply']:
     if body['expected_calculation_revision']!=formulas.revision(db.datasets(c),db.finance(c))['revision']:raise ValueError('계산 기준이 변경되었습니다. 최신 산식으로 재계산한 뒤 처리하세요.')
    if path=='/api/ax-planning':
     from app.ax_planning import preview
     cid=body.get('id') or None
     if cid and not c.execute('SELECT id FROM w01_cases WHERE id=%s',(cid,)).fetchone():raise ValueError('기안을 확인하세요.')
     return self.respond(200,preview(body.get('inputs'),db.datasets(c),db.finance(c),cid))
    if path=='/api/ax-confirm':
     from app.ax_planning import confirm
     cid=body.get('id');row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s FOR UPDATE',(cid,)).fetchone()
     if not row:raise ValueError('기안을 선택하세요.')
     b,v=row;b['_case_id']=cid;command=str(body.get('mutation_id',''))
     try:uuid.UUID(command)
     except ValueError:raise ValueError('중복 방지 키를 확인하세요.')
     hashed=scm.fingerprint({k:x for k,x in body.items() if k not in ['version','mutation_id']});old=b.get('operations',{}).get('ax_commands',{}).get(command)
     if old:
      if old!=hashed:raise ValueError('같은 요청 키의 내용이 다릅니다.')
      return self.respond(200,{'id':cid,'replayed':True})
     if v!=body.get('version'):raise Conflict()
     updated,event=confirm(b,db.datasets(c),db.finance(c),body,role)
     updated.setdefault('operations',{}).setdefault('ax_commands',{})[command]=hashed
     c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(updated),cid))
     db.event(c,cid,role,'SCM 검토 간편 확인 · 재무 인계' if role=='SCM' else '재무 검토 간편 확인 · 승인 요청',event)
     reconcile(c,body['decision_maker'],'사전검토 부서 확인');c.commit()
     return self.respond(200,{'id':cid,'ok':True})
    if path=='/api/prompt-settings':
     from app.prompt_settings import validate,EVENT
     clean=validate(body,role)
     previous=c.execute("SELECT seq,detail FROM w01_events WHERE event=%s AND detail->>'prompt_id'=%s ORDER BY seq DESC LIMIT 1",(EVENT,clean['prompt_id'])).fetchone()
     revision=previous[0] if previous else 0
     if body.get('version')!=revision:raise Conflict()
     db.event(c,None,role,EVENT,{**clean,'at':now(),'before':previous[1].get('prompt') if previous else None})
     c.commit()
     return self.respond(200,{'ok':True,'runtime_applied':True})
    if path in ['/api/formulas/test','/api/formulas/preview','/api/formulas/apply']:
     config=db.finance(c)
     if path=='/api/formulas/test':
      key=body.get('formula_id')
      if not isinstance(key,str) or key not in formulas.CATALOG or role not in formulas.CATALOG[key]['roles']:raise ValueError('현재 역할의 산식만 시험할 수 있습니다.')
      return self.respond(200,{'result':formulas.evaluate(key,body.get('expression'),body.get('values',{})),'saved':False})
     if body.get('version')!=config['version']:raise Conflict()
     data=db.datasets(c);cases=c.execute('SELECT id,body FROM w01_cases ORDER BY id').fetchall()
     result=formulas.impact(config,body,role,data,cases)
     stamp=formulas.preview_key(config,body,role)
     stamp=hashlib.sha256((stamp+json.dumps({'datasets':{k:v.get('version') for k,v in data.items()},'cases':cases},sort_keys=True,default=str)).encode()).hexdigest()
     if path=='/api/formulas/preview':return self.respond(200,{k:v for k,v in result.items() if k!='candidate'}|{'preview_key':stamp,'saved':False})
     if body.get('preview_key')!=stamp or body.get('human_confirmed') is not True:raise ValueError('최신 영향 미리보기를 확인한 후 직접 적용하세요.')
     f=result['candidate'];key=body['formula_id']
     if key in f['formulas']:f['formulas'][key]['at']=now()
     c.execute('UPDATE w01_finance SET body=%s,version=version+1 WHERE id=1',(Jsonb(f),))
     db.event(c,None,role,'계산 산식 변경',{'formula_id':key,'before':config.get('formulas',{}).get(key,{}).get('expression',formulas.CATALOG[key]['default']),'after':body['expression'].strip(),'decision_maker':body['decision_maker'],'reason':body['reason'],'evidence':body['evidence'],'at':now(),'version_before':config['version'],'version_after':config['version']+1,'affected_cases':[x['id'] for x in result['cases']],'provenance':'참가자 가정','human_confirmed':True})
     reconcile(c,body['decision_maker'],'계산 산식 변경: '+formulas.CATALOG[key]['title']);c.commit()
     return self.respond(200,{'ok':True,'version':config['version']+1,'recheck_cases':len(result['cases'])})
    if path=='/api/assistant':
     from app import assistant
     from app.execution import metadata
     cid=body.get('id');row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s FOR UPDATE',(cid,)).fetchone()
     if not row:raise ValueError('기안을 선택하세요.')
     b,v=row;b['_case_id']=cid
     if v!=body.get('version'):raise Conflict()
     data=db.datasets(c);config=db.finance(c);m=metadata(body)
     if body.get('operation')=='propose':
      if len(b.get('assistant_proposals',[]))>=20:raise ValueError('한 검토 건의 보조 제안은 최대 20개입니다.')
      prompt=__import__('app.prompt_settings',fromlist=['effective']).effective(c,{'마케팅':'marketing','SCM':'scm','재무':'finance','승인권자':'approval'}[role]);proposal=assistant.propose(b,data,config,{**calculate(b,data,config),'review_prompt':prompt['prompt']},m);b.setdefault('assistant_proposals',[]).append(proposal);event={'proposal':proposal,'note':'제안 생성 · 승인/계획/지급 변경 없음'}
     elif body.get('operation')=='accept':
      before=b.get('execution');b=assistant.accept(b,data,config,body.get('proposal_id'),body.get('action_id'),role,m);event={'proposal_id':body.get('proposal_id'),'action_id':body.get('action_id'),'before':before,'after':b.get('execution'),'decision_maker':m['decision_maker'],'evidence':m['evidence']}
     else:raise ValueError('보조 제안 생성/사람 채택을 선택하세요.')
     c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid));db.event(c,cid,role,'보조 판단 '+body['operation'],event);reconcile(c,role,'보조 판단 '+body['operation']);c.commit()
     return self.respond(200,{'id':cid,'ok':True})
    if path=='/api/operations':
     from app.operations import apply
     from app.execution import metadata
     cid=body.get('id');row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s FOR UPDATE',(cid,)).fetchone()
     if not row:raise ValueError('기안을 선택하세요.')
     b,v=row;b['_case_id']=cid;command=str(body.get('mutation_id',''))
     try:uuid.UUID(command)
     except ValueError:raise ValueError('중복 방지 키를 확인하세요.')
     hashed=scm.fingerprint({k:val for k,val in body.items() if k not in ['version','mutation_id']})
     old=b.get('operations_commands',{}).get(command)
     if old:
      if old!=hashed:raise ValueError('같은 요청 키의 내용이 다릅니다.')
      return self.respond(200,{'id':cid,'replayed':True})
     if v!=body.get('version'):raise Conflict()
     updated,event=apply(b,db.datasets(c),db.finance(c),body,role,metadata)
     updated.setdefault('operations_commands',{})[command]=hashed
     c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(updated),cid))
     db.event(c,cid,role,'운영 확장 '+body['operation'],event);reconcile(c,role,'운영 확장 '+body['operation']);c.commit()
     return self.respond(200,{'id':cid,'ok':True})
    if path=='/api/execution':
     from app.execution import apply
     cid=body.get('id');row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s FOR UPDATE',(cid,)).fetchone()
     if not row:raise ValueError('기안을 선택하세요.')
     b,v=row;b['_case_id']=cid;command=str(body.get('mutation_id',''))
     try:uuid.UUID(command)
     except ValueError:raise ValueError('중복 방지 키를 확인하세요.')
     hashed=scm.fingerprint({k:val for k,val in body.items() if k not in ['version','mutation_id']})
     if command in b.get('execution_commands',{}):
      if b['execution_commands'][command]!=hashed:raise ValueError('같은 요청 키의 내용이 다릅니다.')
      return self.respond(200,{'id':cid,'replayed':True})
     if v!=body.get('version'):raise Conflict()
     updated,event=apply(b,db.datasets(c),db.finance(c),{**body,'case_id':cid},role)
     updated.setdefault('execution_commands',{})[command]=hashed
     c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(updated),cid))
     db.event(c,cid,role,'역할별 업무 '+body['operation'],event)
     reconcile(c,role,'역할별 업무 '+body['operation']);c.commit()
     return self.respond(200,{'id':cid,'ok':True})
    if path in ['/api/datasets','/api/datasets/preview']:
     kind=body.get('kind')
     if kind not in SCHEMAS or role not in ('SCM',SCHEMAS[kind][1]):raise ValueError('담당 부서 또는 SCM만 수정할 수 있습니다.')
     if body.get('admin_update'):
      for key in ['decision_maker','reason','evidence']:
       if not isinstance(body.get(key),str) or not 1<=len(body[key].strip())<=4000:raise ValueError('수정자·사유·근거를 입력하세요.')
     rows=parse_dataset(kind,body.get('csv'))
     current=db.datasets(c)
     if kind in ['inventory','sales','purchase']:
      skuids={x['sku_id'] for x in current['sku']['rows']}
      if any(x['sku_id'] not in skuids for x in rows):raise ValueError('SKU 마스터에 없는 상품이 포함되어 있습니다.')
     if kind=='sku':
      skuids={x['sku_id'] for x in rows}
      if any(x['sku_id'] not in skuids for key in ['inventory','sales','purchase'] for x in current[key]['rows']):raise ValueError('사용 중인 SKU를 마스터에서 제거할 수 없습니다.')
     old=c.execute('SELECT body,version FROM w01_datasets WHERE kind=%s FOR UPDATE',(kind,)).fetchone()
     if old[1]!=body.get('version'):raise Conflict()
     source=str(body.get('source','담당자 업로드'))[:200]
     if body.get('provenance') not in PROVENANCE:raise ValueError('자료 성격 6종 중 하나를 선택하세요.')
     data={'rows':rows,'source':source,'provenance':body['provenance']}
     if path=='/api/datasets/preview':return self.respond(200,{'kind':kind,'before_rows':len(old[0]['rows']),'after_rows':len(rows),'version':old[1],'saved':False,'note':'시스템의 현재 자료 사본을 교체합니다. 원본 파일은 변경하지 않으며 진행 건은 재검토됩니다.'})
     c.execute('UPDATE w01_datasets SET body=%s,version=version+1 WHERE kind=%s',(Jsonb(data),kind))
     f=db.finance(c);f.pop('version');f['confirmed']=False
     c.execute('UPDATE w01_finance SET body=%s,version=version+1 WHERE id=1',(Jsonb(f),))
     db.event(c,None,role,'데이터 수정',{'kind':kind,'before':old[0],'after':data,'reason':str(body.get('reason',''))[:1000],'decision_maker':str(body.get('decision_maker',''))[:120],'evidence':str(body.get('evidence',''))[:4000]})
     for cid,b in c.execute('SELECT id,body FROM w01_cases FOR UPDATE').fetchall():
      b['status']='재검토 필요';b['approval']=None;b['replies']=[];b['financial_assessment']=None
      if kind in scm.DATA_KINDS:scm.invalidate(b,'기준 자료 '+kind+' 변경')
      c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
      db.event(c,cid,role,'기준 자료 변경 · 기존 회신/승인 재확인',{'kind':kind,'note':'이전 회신은 사건 이력에 보존됩니다.'})
     reconcile(c,role,'기준 자료 변경')
     return self.respond(200,{'ok':True})
    if path in ['/api/scm','/api/scm/preview']:
     if role!='SCM':raise ValueError('SCM 담당자만 SCM 검토·회신을 기록합니다.')
     cid=body.get('id');row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s FOR UPDATE',(cid,)).fetchone()
     if not row or not row[0].get('marketing'):raise ValueError('마케팅 계획 공유 건을 선택하세요.')
     b,v=row;b['_case_id']=cid;data=db.datasets(c)
     if b.get('execution',{}).get('closed') or b.get('execution',{}).get('orders'):raise ValueError('발주 전달·종료 후 검토 변경은 새 기안으로 요청하세요. 공급 회신은 ⑥ 화면을 사용하세요.')
     if path=='/api/scm/preview':
      if v!=body.get('version'):raise Conflict()
      r=scm.validate_review(body.get('review'),b,data,preview=True)
      return self.respond(200,{'calculation':scm.analysis(b,data,db.finance(c),review=r)})
     operation=body.get('operation')
     if operation not in ['save','handoff','receipt']:raise ValueError('SCM 처리 유형을 확인하세요.')
     command=str(body.get('mutation_id',''))
     try:uuid.UUID(command)
     except ValueError:raise ValueError('중복 방지 키를 확인하세요.')
     hashed=scm.fingerprint({k:val for k,val in body.items() if k not in ['version','mutation_id']})
     old=b.get('scm_commands',{}).get(command)
     if old:
      if old!=hashed:raise ValueError('같은 요청 키의 내용이 다릅니다.')
      return self.respond(200,{'id':cid,'replayed':True})
     if v!=body.get('version'):raise Conflict()
     if b.get('marketing_stage')=='작성 중':raise ValueError('마케팅이 SCM 검토를 요청한 뒤 진행하세요.')
     before=json.loads(json.dumps(b.get('scm',{})));b.setdefault('scm',{});demand_event=None
     if operation=='receipt':
      receipt=scm.validate_receipt(body.get('receipt'),b,data);receipt['at']=now()
      b['scm'].setdefault('receipts',{})[receipt['po_id']]=receipt
      scm.invalidate(b,'공급 회신 변경')
      for q in b['scm'].get('review',{}).get('requests',[]):
       if q.get('po_id')==receipt['po_id']:
        q.update(status='완료' if receipt['status'] in ['확인','불가'] else '대기',answer=receipt['reason'],evidence=receipt['evidence'])
      event='SCM 공급 회신 기록';actor=receipt['decision_maker']
     else:
      r=scm.validate_review(body.get('review'),b,data);calc=scm.analysis(b,data,db.finance(c),review=r)
      if operation=='handoff':
       from app.demand import require_ready
       b,demand_event=scm.handoff_demand(b,data,db.finance(c),r,body.get('demand_confirmation'))
       scm.can_handoff(r,calc)
       if calc['recommendation']['kind']=='procurement':
        if body.get('replenishment_checked') is not True:raise ValueError('정기 보충 계획 검토를 확인하세요. 미확정 입고·지급일은 후속 확인 대상입니다.')
        r['supply_plan']={'basis':calc['replenishment']['basis'],'policy':calc['replenishment']['policy'],'items':[{k:x[k] for k in ['sku_id','regular_orders','pipeline_assumptions','regular_qty','regular_cost','incremental_qty','incremental_cost','earliest_arrival_assumption','latest_order_date']} for x in calc['replenishment']['items']],'decision_maker':r['decision_maker'],'at':now(),'status':'계획 검토 · 공급·지급 미확인','provenance':'참가자 가정 / 계산 결과'}
        for item in calc['replenishment']['items']:
         key='regular:'+item['sku_id']
         if not any(q.get('id')==key for q in r['requests']):r['requests'].append({'id':key,'role':'SCM','question':item['sku_id']+' 정기 보충 수량·판매가능일·지급일 확인','blocking':False,'status':'대기','answer':'','evidence':'','po_id':None})
      r.update(at=now(),valid=operation=='handoff',basis=scm.basis(b,data),source_case_version=v,provenance='부서 주장',control_provenance='내부 통제')
      b['scm']['review']=r;b['scm'].pop('finance_packet',None)
      if operation=='handoff':
       from app.operations import pending_adjustment,complete_adjustment
       pending=pending_adjustment(b)
       if pending and pending['target']!='SCM':raise ValueError('현재 조정 요청의 담당 부서가 먼저 처리해야 합니다.')
       complete_adjustment(b,'SCM',now())
       # An earlier finance packet cannot represent the newly handed-off SKU quantities.
       # Preserve it for audit and build the next finance draft from the current SCM review.
       if b.get('finance_review'):b.setdefault('finance_review_history',[]).append(b.pop('finance_review'))
       b['marketing_stage']='재무 검토 요청'
       calc['valid']=True
       b['scm']['finance_packet']=scm.packet(b,r,calc)
       b['scm']['finance_packet']['case_id']=cid
       b['scm']['finance_packet']['documents']=[{'id':i,'name':n,'role':r,'provenance':p} for i,n,r,p in c.execute('SELECT id,name,role,provenance FROM w01_documents WHERE case_id=%s',(cid,))]
      else:b['marketing_stage']='SCM 추가 확인 대기' if r['direction']=='추가 확인 대기' else 'SCM 검토 요청'
      event='SCM 검토 완료 · 재무 인계' if operation=='handoff' else 'SCM 검토 저장';actor=r['decision_maker']
     b['approval']=None;b['status']='검토 중' if operation!='receipt' else ('재검토 필요' if b['scm'].get('review') else b['status'])
     commands=b.setdefault('scm_commands',{});commands[command]=hashed
     c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
     if demand_event:db.event(c,cid,role,'수요 근거 확인 · SCM 인계와 동시 기록',demand_event)
     db.event(c,cid,role,event,{'before':before,'after':b['scm'],'decision_maker':actor,'at':now(),'mutation_id':command,'note':'사람의 SCM 검토/회신. 발주·지급·캠페인 승인 아님.'})
     reconcile(c,actor,event);c.commit()
     return self.respond(200,{'id':cid,'stage':b['marketing_stage']})
    if path=='/api/marketing':
     if role not in ['마케팅','SCM']:raise ValueError('마케팅 또는 SCM만 기안을 작성·공유합니다.')
     operation=body.get('operation')
     if operation not in ['save','submit']:raise ValueError('저장 또는 SCM 검토 요청을 선택하세요.')
     cid=body.get('id');before=None
     if cid:
      row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s FOR UPDATE',(cid,)).fetchone()
      if not row or not row[0].get('marketing'):raise ValueError('마케팅 기안을 확인하세요.')
      if row[1]!=body.get('version'):raise Conflict()
      before=row[0]
      from app.portfolio import legacy_reservation
      legacy=legacy_reservation(before)
      if legacy and before.get('execution',{}).get('reservation') is None:before.setdefault('execution',{})['reservation']=legacy
      if before.get('execution',{}).get('orders') or before.get('execution',{}).get('closed') or before.get('execution',{}).get('withdrawn'):raise ValueError('발주 전달·종료 후 변경은 새 기안으로 요청하세요. 기존 발주 기록은 보존합니다.')
     else:
      key=str(body.get('submission_key',''))
      try:uuid.UUID(key)
      except ValueError:raise ValueError('중복 방지 키를 확인하세요.')
      fingerprint=hashlib.sha256(json.dumps({'plan':body.get('plan'),'operation':operation,'role':role,**({'ax_inputs':body['ax_inputs']} if body.get('ax_inputs') else {})},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
      old=c.execute("SELECT id,body FROM w01_cases WHERE body->>'submission_key'=%s",(key,)).fetchone()
      if old:
       if old[1].get('submission_fingerprint')!=fingerprint:raise ValueError('동일 요청 키의 내용이 다릅니다. 다시 열어 저장하세요.')
       return self.respond(200,{'id':old[0],'replayed':True})
     if operation=='submit' and 'media' in (body.get('plan') or {}):
      p=body['plan']
      from app.marketing import validate_submission
      validate_submission(p)
      if p.get('submission_mode')!='estimate_only' and any(not p.get(k) or p[k]<p.get('as_of','2026-07-01') for k in ['settlement_date','contract_deadline']):raise ValueError('정산일·확정기한은 기준일 이후로 입력하세요.')
     b=case_from(body.get('plan'),db.datasets(c));calculate(b,db.datasets(c),db.finance(c))
     if operation=='submit':
      from app.marketing import submission_cash_window
      submission_cash_window(b['marketing'],cash_bundle(db.datasets(c),db.finance(c)))
     b.update(status='접수',replies=[],approval=None,created_at=before['created_at'] if before else now(),marketing_stage='SCM 검토 요청' if operation=='submit' else '작성 중')
     if before:
      b['_case_id']=cid
      if before.get('execution'):
       b['execution']=json.loads(json.dumps(before['execution']));b['execution'].pop('rework',None)
      if before.get('scm'):
       b['scm']=before['scm'];scm.invalidate(b,'마케팅 기안 수정')
      for k in ['submission_key','submission_fingerprint','scm_commands','operations','operations_commands','finance_review_history']:
       if k in before:b[k]=before[k]
      if operation=='submit':
       from app.operations import pending_adjustment,complete_adjustment
       pending=pending_adjustment(b)
       if pending and pending['target']!='마케팅':raise ValueError('현재 조정 요청의 담당 부서가 먼저 처리해야 합니다.')
       complete_adjustment(b,'마케팅',now())
      c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
     else:
      cid=str(uuid.uuid4());b['_case_id']=cid;b.update(submission_key=key,submission_fingerprint=fingerprint)
      c.execute('INSERT INTO w01_cases(id,body) VALUES (%s,%s)',(cid,Jsonb(b)))
     if body.get('ax_inputs') is not None:
      from app.ax_planning import attach
      b['ax_plan']=attach(b,body['ax_inputs'],db.datasets(c),db.finance(c),cid)
      cost=b['ax_plan'].get('marketing_cost',{})
      if cost.get('enabled') and cost.get('scope_requires_confirmation') and cost.get('adopted_budget') is not None and cost['adopted_budget']==b['marketing']['budget']:
       if not b['marketing'].get('budget_basis'):raise ValueError('표본 기반 마케팅 예산의 적용 범위·근거를 입력하세요.')
       cost['scope_confirmation']={'decision_maker':b['marketing']['author'],'at':now(),'basis':b['marketing']['budget_basis'],'provenance':'참가자 가정 · 기안 신청 시 기록'}
      c.execute('UPDATE w01_cases SET body=%s WHERE id=%s',(Jsonb(b),cid))
     db.event(c,cid,role,'마케팅 계획 SCM 검토 요청' if operation=='submit' else '마케팅 기안 저장',{'before':before,'after':b,'author':b['marketing']['author'],'rule_id':PROJECT_POLICY['id'],'note':'사람의 계획 공유. 승인·발주·지급 아님.'})
     reconcile(c,role,'마케팅 기안 저장·공유')
     c.commit()
     return self.respond(200,{'id':cid,'stage':b['marketing_stage']})
    if path=='/api/cases':
     if role not in ['마케팅','SCM']:raise ValueError('마케팅 또는 SCM이 요청을 생성합니다.')
     b=validate_case(body['case']); data=db.datasets(c)
     calculate(b,data)
     cid=str(uuid.uuid4());b.update(status='접수',replies=[],approval=None,created_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
     c.execute('INSERT INTO w01_cases(id,body) VALUES (%s,%s)',(cid,Jsonb(b)))
     db.event(c,cid,role,'캠페인 검토 요청',{'case':b})
     reconcile(c,role,'검토 건 접수')
     return self.respond(200,{'id':cid})
    if path=='/api/finance-review':
     from app.finance_review import validate as validate_finance_review,view as finance_review_view
     if role!='재무':raise ValueError('재무 담당자만 재무 검토를 저장·상신합니다.')
     cid=body.get('id');row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s FOR UPDATE',(cid,)).fetchone()
     if not row:raise ValueError('검토 건이 없습니다.')
     b,v=row;b['_case_id']=cid
     if b.get('execution',{}).get('closed') or b.get('execution',{}).get('withdrawn'):raise ValueError('종료된 회차의 재무 검토를 수정할 수 없습니다. 새 기안으로 요청하세요.')
     if v!=body.get('version') or db.finance(c)['version']!=body.get('finance_version'):raise Conflict()
     data=db.datasets(c);config=db.finance(c)
     r=validate_finance_review(body.get('review'),b,data)
     if body.get('operation') not in ['preview'] and b.get('status') in ['승인','승인 대기','조건부 승인']:
      b['approval']=None;b['status']='재검토 필요'
     preview=finance_review_view(b,data,config,r)
     operation=body.get('operation')
     if operation=='preview':return self.respond(200,preview)
     if operation not in ['save','submit','request']:raise ValueError('저장·확인 요청·상신 중 선택하세요.')
     if b.get('status') in ['발주 전달','회신 기록 완료']:raise ValueError('전달된 발주는 새 변경 건으로 요청하세요.')
     if operation=='submit' and b.get('finance_review',{}).get('operation')=='submit' and finance_review_view(b,data,config)['valid']:raise ValueError('이미 상신한 버전입니다. 변경 검토를 저장한 후 재상신하세요.')
     if operation=='submit' and preview['errors']:raise ValueError('; '.join(preview['errors']))
     if operation=='submit':
      from app.operations import pending_adjustment,complete_adjustment
      pending=pending_adjustment(b)
      if pending and pending['target']!='재무':raise ValueError('현재 조정 요청의 담당 부서가 먼저 처리해야 합니다.')
      complete_adjustment(b,'재무',now())
     if operation=='request' and not any(q['status']=='대기' for q in r['requests']):raise ValueError('대기 중인 확인 질문을 입력하세요.')
     before=b.get('finance_review');r.update(basis=preview['basis'],operation=operation,at=now(),source_case_version=v,finance_version=config['version'],source_versions=preview['source_versions'],provenance='부서 주장',classification_provenance='내부 통제')
     if operation=='submit':r['packet']={'review':{k:v for k,v in r.items() if k!='packet'},'routes':preview['routes'],'performance':preview['performance'],'cash_impact':{sid:{'baseline_min':x['cash_min'],'impact_min':x['impact_min']} for sid,x in preview['scenarios'].items()},'related_contract':preview['related_contract'],'note':'재무 검토 상신. 승인·발주·지급 아님. ④ 약정별 사람 승인 후 발주·일정 정리로 연결.'}
     b['finance_review']=r
     from app.operations import detect_disagreement
     detect_disagreement(b,r['decision_maker'],now())
     c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
     db.event(c,cid,role,'재무 검토 '+operation,{'before':before,'after':r,'decision_maker':r['decision_maker'],'reason':r['reason'],'evidence':r['evidence']})
     reconcile(c,r['decision_maker'],'재무 검토 '+operation);c.commit()
     return self.respond(200,{'ok':True})
    if path=='/api/finance':
     if role!='재무':raise ValueError('재무 담당자만 시나리오와 회수·지급일을 확정합니다.')
     previous=db.finance(c)
     if body.get('version')!=previous['version']:raise Conflict()
     for key in ['reason','evidence','decision_maker']:
      if not isinstance(body.get(key),str) or not 1<=len(body[key].strip())<=4000:raise ValueError('결정자·사유·근거를 모두 입력하세요.')
     f={k:v for k,v in previous.items() if k!='version'}
     operation=body.get('operation')
     metadata={k:body[k].strip() for k in ['reason','evidence','decision_maker']};metadata.update(at=now(),role=role)
     if operation=='confirm':
      if body.get('selected') not in SCENARIOS:raise ValueError('시나리오를 선택하세요.')
      if not isinstance(body.get('weekend_shift'),bool):raise ValueError('영업일 조정 여부를 선택하세요.')
      from app.domain import day
      review=body.get('review_date');nextreview=body.get('next_review_date')
      if day(review)<AS_OF or day(nextreview)<=day(review):raise ValueError('다음 재전망일은 검토일 이후여야 합니다.')
      f.update(selected=body['selected'],weekend_shift=body['weekend_shift'],review_date=review,next_review_date=nextreview,confirmed=True,decision=metadata)
     elif operation=='overdue_reply':
      records=cash_bundle(db.datasets(c),previous)['overdue']
      if body.get('record_id') not in [x['id'] for x in records]:raise ValueError('연체 항목을 확인하세요.')
      from app.domain import day
      if body.get('date') and day(body['date'])<AS_OF:raise ValueError('회수·지급 확인일은 7/1 이후여야 합니다.')
      if body.get('provenance') not in ['모의 회신','부서 주장']:raise ValueError('회신 출처를 구분하세요.')
      f['overrides']={**f.get('overrides',{}),body['record_id']:{'date':body.get('date') or None,'provenance':body['provenance'],**metadata}}
      f['confirmed']=False
     else:raise ValueError('지원하지 않는 재무 결정입니다.')
     candidate=cash_bundle(db.datasets(c),f)
     if candidate['validation_errors']:raise ValueError('; '.join(candidate['validation_errors']))
     c.execute('UPDATE w01_finance SET body=%s,version=version+1 WHERE id=1',(Jsonb(f),))
     db.event(c,None,role,'공식 재전망 시나리오 확정' if operation=='confirm' else '연체 항목 확인 회신',{'before':previous,'after':f,**metadata,'provenance':'부서 주장' if operation=='confirm' else body['provenance']})
     reconcile(c,body['decision_maker'],body['reason'])
     return self.respond(200,{'ok':True})
    if path=='/api/assessment':
     if role!='재무':raise ValueError('재무 담당자만 유출일·신규 여부를 확인합니다.')
     cid=body.get('id');row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s FOR UPDATE',(cid,)).fetchone()
     if not row:raise ValueError('검토 건이 없습니다.')
     b,v=row;b['_case_id']=cid
     if b.get('marketing'):raise ValueError('마케팅 기안은 전용 저장·SCM 검토 요청으로 처리하세요. 승인·발주 건이 아닙니다.')
     if v!=body.get('version'):raise Conflict()
     from app.domain import day,number
     if b.get('marketing'):raise ValueError('마케팅 계획은 SCM 검토 후 승인 대상을 구분해야 합니다.')
     a=body.get('assessment',{})
     for key in ['reason','evidence','decision_maker','opinion','alternatives']:
      if not isinstance(a.get(key),str) or not 1<=len(a[key].strip())<=4000:raise ValueError('결정자·사유·근거·의견·대안을 모두 작성하세요.')
     day(a.get('payment_date'));a['amount']=number(a.get('amount'),'유출액')
     if a.get('change') not in ['기존 약정','추가발주','증량','지급일 앞당김','감량','지급일 연기','취소','신규 계약']:raise ValueError('약정 분류를 선택하세요.')
     if a['change'] in ['기존 약정','감량','지급일 연기','취소','증량','지급일 앞당김']:
      po=next((p for p in db.datasets(c)['purchase']['rows'] if p['po_id']==a.get('reference_po') and p['sku_id']==b['sku_id']),None)
      if not po:raise ValueError('변경·기존 약정은 대상 SKU의 원본 발주를 연결하세요.')
      if a['change']=='기존 약정' and (a['amount']!=int(po['amount_krw']) or a['payment_date']!=po['payment_due_date']):raise ValueError('기존 약정은 원본 지급액·지급일과 일치해야 합니다.')
     original_orders=json.loads((ROOT/'data/seed.json').read_text())['purchase']['rows']
     validate_commitment(a,original_orders,b['sku_id'])
     before=b.get('financial_assessment');a.update(at=now(),role=role,provenance='부서 주장',classification_provenance='내부 통제')
     if b['status'] in ['발주 전달','회신 기록 완료']:raise ValueError('이미 전달된 발주는 새 변경 검토 건으로 요청하세요.')
     b['financial_assessment']=a;b['approval']=None
     if b['status'] not in ['접수','회신 대기','검토 중','보완 필요']:b['status']='재검토 필요'
     elif b['status'] in ['접수','회신 대기']:b['status']='검토 중'
     b.setdefault('replies',[]).append({'role':'재무','result':'확인','message':a['opinion'],'at':now(),'provenance':'부서 주장'})
     c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
     db.event(c,cid,role,'약정 유출일·신규 여부 확정',{'before':before,'after':a,'decision_maker':a['decision_maker'],'reason':a['reason'],'evidence':a['evidence'],'at':a['at']})
     reconcile(c,a['decision_maker'],'재무 약정 분류 변경')
     return self.respond(200,{'ok':True})
    if path=='/api/draft':
     from app.drafts import generate
     cid=body.get('id');row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s',(cid,)).fetchone()
     if not row:raise ValueError('검토 건이 없습니다.')
     if row[1]!=body.get('version'):raise Conflict()
     b=row[0];result=generate(b,calculate(b,db.datasets(c),db.finance(c)))
     result.update(created_at=now(),source_case_version=row[1],finance_version=db.finance(c)['version'],dataset_versions={k:x['version'] for k,x in db.datasets(c).items()},human_review_required=True)
     b['draft']=result
     c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
     db.event(c,cid,role,'상신 패킷 초안 생성 · 상태변경 없음',result)
     c.commit()
     return self.respond(200,{'ok':True})
    if path=='/api/documents':
     cid=body.get('id');row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s FOR UPDATE',(cid,)).fetchone()
     if not row:raise ValueError('검토 건이 없습니다.')
     if row[1]!=body.get('version'):raise Conflict()
     name=Path(str(body.get('name',''))).name
     if len(name)>150 or Path(name).suffix.lower() not in ['.pdf','.csv','.txt','.md']:raise ValueError('PDF·CSV·TXT·MD 파일만 첨부할 수 있습니다.')
     try:content=base64.b64decode(body.get('content',''),validate=True)
     except Exception:raise ValueError('첨부 파일 형식이 올바르지 않습니다.')
     if not 1<=len(content)<=1_000_000:raise ValueError('첨부는 1MB 이하이어야 합니다.')
     if name.lower().endswith('.pdf') and not content.startswith(b'%PDF-'):raise ValueError('PDF 파일을 확인하세요.')
     if body.get('provenance') not in PROVENANCE:raise ValueError('자료 구분을 선택하세요.')
     did=str(uuid.uuid4())
     c.execute('INSERT INTO w01_documents(id,case_id,name,role,provenance,content) VALUES (%s,%s,%s,%s,%s,%s)',(did,cid,name,role,body['provenance'],content))
     b=row[0]
     if role=='SCM':scm.invalidate(b,'SCM 근거 파일 추가')
     if b['status'] in ['승인','승인 대기','회신 기록 완료']:b['status']='재검토 필요';b['approval']=None
     c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
     db.event(c,cid,role,'근거 파일 첨부',{'name':name,'provenance':body['provenance'],'document_id':did,'note':'파일 내용은 자동 추출·검증하지 않습니다.'})
     reconcile(c,role,'근거 첨부')
     c.commit()
     return self.respond(200,{'ok':True})
    if path=='/api/action':
     cid=body['id'];row=c.execute('SELECT body,version FROM w01_cases WHERE id=%s FOR UPDATE',(cid,)).fetchone()
     if not row:raise ValueError('검토 건이 없습니다.')
     b,v=row;b['_case_id']=cid
     if b.get('marketing'):raise ValueError('마케팅 기안은 전용 저장·SCM 검토 요청으로 처리하세요. 승인·발주 건이 아닙니다.')
     if v!=body.get('version'):raise Conflict()
     action=body['action']; data=db.datasets(c)
     if action=='reply':
      r=dict(body['reply']);r['role']=role;r['provenance']='모의 회신';validate_reply(r,b,data)
      if r.get('po_id') and role!='SCM':raise ValueError('공급 회신은 SCM이 기록합니다.')
      r['after_order']=b['status']=='발주 전달';r['at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());r['dataset_versions']={k:x['version'] for k,x in data.items()}
      b['replies'].append(r)
      if b['status'] in ['승인','승인 대기','회신 기록 완료']:
       b['status']='재검토 필요';b['approval']=None
      elif b['status']!='발주 전달':b['status']='검토 중'
      detail=r
     elif action=='revise':
      if role not in ['SCM','마케팅']:raise ValueError('SCM 또는 마케팅이 계획을 수정합니다.')
      updated=validate_case(body['case']);calculate(updated,data)
      detail={'before':b.copy(),'after':updated}
      b.update(updated);b.update(status='재검토 필요',approval=None,replies=[],financial_assessment=None)
     else:
      b['decision_note']=str(body.get('note',''))[:4000];b['approval_scope']=body.get('scope','')
      calc=calculate(b,data,db.finance(c))
      if action in ['approve','conditional']:
       expected=calc['authority']
       if b['approval_scope']!=expected:raise ValueError('계산된 승인권자와 승인 범위가 일치하지 않습니다.')
      b['status']=transition(b,action,role,calc)
      detail={'action':action,'note':b['decision_note'],'scope':b['approval_scope'],'dataset_versions':{k:x['version'] for k,x in data.items()},'first_short':calc['first_short'],'cash_min':calc['cash_min']}
      if action=='approve':b['approval']=detail
     c.execute('UPDATE w01_cases SET body=%s,version=version+1 WHERE id=%s',(Jsonb(b),cid))
     db.event(c,cid,role,{'reply':'협조 회신','revise':'계획 수정'}.get(action,b['status']),detail)
     reconcile(c,role,'부서 회신·결정 반영')
     return self.respond(200,{'ok':True})
    return self.respond(404,{'error':'경로가 없습니다.'})
  except Conflict:return self.respond(409,{'error':'다른 사용자가 변경했습니다. 새로고침 후 다시 확인하세요.'})
  except (ValueError,KeyError,TypeError) as e:return self.respond(400,{'error':str(e)})
  except Exception:return self.respond(503,{'error':'저장에 실패했습니다. DB 상태를 확인하고 다시 시도하세요.'})

def main():
 host='0.0.0.0' if PUBLIC_ACCESS or PASSWORD else '127.0.0.1'
 port=int(os.environ.get('PORT',8080))
 print(f'W01 prototype listening on {host}:{port}',flush=True)
 ThreadingHTTPServer((host,port),Handler).serve_forever()

if __name__=='__main__':main()
