import json
from pathlib import Path
from app.db import connect
from psycopg.types.json import Jsonb
with connect() as c:
 for k,v in json.loads(Path('data/seed.json').read_text()).items():
  c.execute('INSERT INTO w01_datasets(kind,body) VALUES (%s,%s) ON CONFLICT DO NOTHING',(k,Jsonb(v)))
 from app.workflow import reconcile
 reconcile(c,'시스템','초기 자료·규칙 준비')
print('Original baseline imported (existing data preserved)')
