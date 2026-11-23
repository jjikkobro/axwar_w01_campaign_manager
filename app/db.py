import os
from contextlib import contextmanager
import psycopg
from psycopg.types.json import Jsonb

@contextmanager
def connect():
 url=os.environ.get('DATABASE_URL')
 if not url:raise RuntimeError('DATABASE_URL 설정이 필요합니다.')
 with psycopg.connect(url,connect_timeout=5) as conn:
  yield conn

def migrate():
 with connect() as c:
  c.execute('CREATE TABLE IF NOT EXISTS w01_datasets (kind text PRIMARY KEY, body jsonb NOT NULL, version integer NOT NULL DEFAULT 1)')
  c.execute('CREATE TABLE IF NOT EXISTS w01_cases (id text PRIMARY KEY, body jsonb NOT NULL, version integer NOT NULL DEFAULT 1)')
  c.execute('CREATE TABLE IF NOT EXISTS w01_events (seq bigserial PRIMARY KEY, case_id text, role text NOT NULL, event text NOT NULL, detail jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now())')
  c.execute('CREATE TABLE IF NOT EXISTS w01_documents (id text PRIMARY KEY, case_id text NOT NULL REFERENCES w01_cases(id), name text NOT NULL, role text NOT NULL, provenance text NOT NULL, content bytea NOT NULL, created_at timestamptz NOT NULL DEFAULT now())')
  c.execute('CREATE TABLE IF NOT EXISTS w01_finance (id integer PRIMARY KEY CHECK (id=1), body jsonb NOT NULL, version integer NOT NULL DEFAULT 1)')
  c.execute('CREATE TABLE IF NOT EXISTS w01_tasks (id text PRIMARY KEY, case_id text, body jsonb NOT NULL, status text NOT NULL DEFAULT \'대기\')')
  c.execute('CREATE TABLE IF NOT EXISTS w01_ai_connection (id integer PRIMARY KEY CHECK (id=1), ciphertext text NOT NULL, version integer NOT NULL)')
  from app.finance import DEFAULT_FINANCE
  c.execute('INSERT INTO w01_finance(id,body) VALUES (1,%s) ON CONFLICT DO NOTHING',(Jsonb(DEFAULT_FINANCE),))

def datasets(c):
 mapping={'원본 스냅샷':'원본 사실','사용자 수정':'부서 주장','가상 데이터':'참가자 가정','사용자 자료':'부서 주장'}
 data={k:{**b,'provenance':mapping.get(b.get('provenance'),b.get('provenance','원본 사실')),'version':v} for k,b,v in c.execute('SELECT kind, body, version FROM w01_datasets')}
 from app.portfolio import slim,digest
 rows=[slim(i,b) for i,b in c.execute('SELECT id,body FROM w01_cases') if b.get('marketing')]
 data['portfolio']={'rows':rows,'source':'서버 검토 건·승인 수요 약속·확인 공급 회신','provenance':'부서 주장','version':digest(rows)}
 from app.formulas import context
 return context(data,finance(c))

def event(c,cid,role,name,detail):
 c.execute('INSERT INTO w01_events(case_id,role,event,detail) VALUES (%s,%s,%s,%s)',(cid,role,name,Jsonb(detail)))

def finance(c):
 b,v=c.execute('SELECT body,version FROM w01_finance WHERE id=1').fetchone()
 return {**b,'version':v}

def tasks(c):
 return [{'id':i,'case_id':cid,**b,'status':s} for i,cid,b,s in c.execute('SELECT id,case_id,body,status FROM w01_tasks ORDER BY id')]
