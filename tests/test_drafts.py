import copy,json,os,unittest
from unittest.mock import patch
from pathlib import Path
from app.domain import calculate
from app.drafts import generate

class DraftTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads(Path('data/seed.json').read_text())
  self.case={'title':'초안 경계 검증','sku_id':'SKU-1001','as_of':'2026-07-01','start':'2026-07-13','end':'2026-07-19','quantity':1000,'demand_status':'가정','evidence':'참가자 가정','status':'검토 중','replies':[{'role':'SCM','result':'확인','message':'이 문구를 지시로 실행하지 말 것','provenance':'모의 회신'}]}
 def test_response_adapter_and_no_state_mutation(self):
  response=unittest.mock.MagicMock()
  response.__enter__.return_value.read.return_value=json.dumps({'output':[{'type':'message','content':[{'type':'output_text','text':'모의 AI: 재무 확인 후 사람이 상신을 검토하세요.'}]}]}).encode()
  before=copy.deepcopy(self.case)
  with patch.dict(os.environ,{'AI_BASE_URL':'https://api.openai.com/v1','AI_API_KEY':'test-not-a-real-key','AI_MODEL':'configured-test-model'}),patch('app.drafts.urlopen',return_value=response) as mock:
   result=generate(self.case,calculate(self.case,self.data))
   request=mock.call_args.args[0];body=json.loads(request.data)
   self.assertFalse(body['store']);self.assertNotIn('tools',body)
   self.assertIn('Human-led',body['instructions'])
   self.assertIn('W01 원본 업무 흐름',body['instructions'])
   self.assertIn('evidence_sources',json.loads(body['input']))
   self.assertTrue(request.full_url.endswith('/responses'))
  self.assertEqual(self.case,before);self.assertTrue(result['unverified'])
  self.assertEqual(result['packet']['suggested_state'],'재무 확인 요청')

if __name__=='__main__':unittest.main()
