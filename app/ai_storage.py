"""Encrypted PostgreSQL persistence for deployed GPT configuration."""
import base64,hashlib,json,os

def cipher():
 from cryptography.fernet import Fernet
 secret=os.environ.get('SESSION_SECRET','')
 if not secret:raise ValueError('GPT 설정 보관에 필요한 서버 SESSION_SECRET이 없습니다.')
 return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))
def seal(value):return cipher().encrypt(json.dumps(value).encode()).decode()
def open_value(value):
 from cryptography.fernet import InvalidToken
 try:return json.loads(cipher().decrypt(value.encode()))
 except (InvalidToken,ValueError):raise ValueError('GPT 설정 복호화에 실패했습니다. 서버 보안 설정을 확인하세요.') from None
def read():
 from app.db import connect
 with connect() as conn:
  row=conn.execute('SELECT ciphertext FROM w01_ai_connection WHERE id=1').fetchone()
 return open_value(row[0]) if row else None
def write(value,expected):
 from app.db import connect
 encrypted=seal(value)
 with connect() as conn:
  if expected==0:
   row=conn.execute('INSERT INTO w01_ai_connection(id,ciphertext,version) VALUES (1,%s,%s) ON CONFLICT DO NOTHING RETURNING version',(encrypted,value['version'])).fetchone()
  else:row=conn.execute('UPDATE w01_ai_connection SET ciphertext=%s,version=%s WHERE id=1 AND version=%s RETURNING version',(encrypted,value['version'],expected)).fetchone()
  if not row:raise ValueError('GPT 설정이 변경되었습니다. 새로고침 후 저장하세요.')
