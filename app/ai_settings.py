"""Server-only OpenAI credentials. Public settings and audit events never contain a key."""
import json,os,re,tempfile,threading
from pathlib import Path
LOCK=threading.RLock()
DEFAULT_MODEL='gpt-5-mini'
BASE_URL='https://api.openai.com/v1'
def environment_managed():return os.environ.get('AI_SETTINGS_BACKEND')=='environment'
def from_environment():
 key=os.environ.get('AI_API_KEY') or os.environ.get('OPENAI_API_KEY','')
 return {'enabled':bool(key),'api_key':key,'model':os.environ.get('AI_MODEL') or DEFAULT_MODEL,'version':0,'base_url':BASE_URL}
def path():return Path(os.environ.get('AI_SETTINGS_PATH') or Path(__file__).resolve().parent.parent/'.axhub/local-runtime/secrets/openai.json')
def load():
 with LOCK:
  if environment_managed():return from_environment()
  if os.environ.get('AI_SETTINGS_BACKEND')=='postgres':
   from app.ai_storage import read
   stored=read()
   if stored:return {**stored,'base_url':BASE_URL}
   p=None
  else:p=path()
  if p is not None and p.exists():
   try:
    value=json.loads(p.read_text());return {'enabled':bool(value.get('enabled')),'api_key':value.get('api_key',''),'model':value.get('model') or DEFAULT_MODEL,'version':int(value.get('version',0)),'base_url':BASE_URL}
   except (OSError,ValueError,TypeError):raise ValueError('GPT 연결 설정을 읽지 못했습니다. 관리자 설정을 확인하세요.')
  return from_environment()
def public(config=None):
 c=load() if config is None else config
 return {'provider':'OpenAI','model':c['model'],'enabled':c['enabled'],'key_present':bool(c['api_key']),'configured':bool(c['enabled'] and c['api_key'] and c['model']),'version':c['version'],'environment_managed':environment_managed()}
def save(raw,role):
 if environment_managed():raise ValueError('GPT 연결은 AXhub 보안 환경변수에서 관리합니다. 앱 화면에서는 변경할 수 없습니다.')
 if role!='SCM':raise ValueError('시스템 관리 담당 SCM 역할에서 GPT 연결을 설정하세요.')
 with LOCK:
  old=load()
  if raw.get('version')!=old['version']:raise ValueError('GPT 설정이 변경되었습니다. 새로고침 후 저장하세요.')
  model=raw.get('model',old['model'])
  if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}',model):raise ValueError('사용 가능한 GPT 모델명을 입력하세요.')
  key=raw.get('api_key','')
  if not isinstance(key,str) or len(key)>1024 or any(x.isspace() for x in key):raise ValueError('API 키 입력을 확인하세요.')
  if key and not key.startswith('sk-'):raise ValueError('OpenAI API 키를 입력하세요.')
  enabled=raw.get('enabled',old['enabled'])
  if not isinstance(enabled,bool):raise ValueError('연결 사용 여부를 확인하세요.')
  key='' if raw.get('clear_key') is True else key or old['api_key']
  if raw.get('clear_key') is True:enabled=False
  if enabled and not key:raise ValueError('GPT 연결에 사용할 API 키를 입력하세요.')
  value={'enabled':enabled,'api_key':key,'model':model,'version':old['version']+1}
  if os.environ.get('AI_SETTINGS_BACKEND')=='postgres':
   from app.ai_storage import write
   write(value,old['version'])
   return public(value)
  p=path();p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  fd,name=tempfile.mkstemp(prefix='.openai-',dir=p.parent)
  try:
   with os.fdopen(fd,'w') as stream:
    os.fchmod(stream.fileno(),0o600);json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
   os.replace(name,p)
  finally:
   if os.path.exists(name):os.unlink(name)
  return public(value)
