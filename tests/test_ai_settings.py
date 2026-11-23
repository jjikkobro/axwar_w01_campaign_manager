import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from app import ai_settings,drafts
from app.prompt_settings import default_prompt,FORMAT,BOUNDARY

class AISettingsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.file=Path(self.temp.name)/'secrets/settings.json';self.env=patch.dict(os.environ,{'AI_SETTINGS_PATH':str(self.file),'AI_API_KEY':'','OPENAI_API_KEY':''});self.env.start()
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def saved(self):return ai_settings.save({'version':0,'model':'gpt-5-mini','api_key':'sk-test-only-placeholder','enabled':True},'SCM')
 def test_secret_persists_server_side_without_public_leak(self):
  public=self.saved();self.assertNotIn('sk-',json.dumps(public));self.assertTrue(ai_settings.public()['configured']);self.assertEqual(self.file.stat().st_mode&0o777,0o600)
  self.assertEqual(ai_settings.load()['api_key'],'sk-test-only-placeholder')
 def test_role_version_clear_and_blank_key_preservation(self):
  with self.assertRaises(ValueError):ai_settings.save({'version':0},'마케팅')
  self.saved()
  with self.assertRaises(ValueError):ai_settings.save({'version':0,'enabled':False},'SCM')
  ai_settings.save({'version':1,'model':'gpt-5-mini','api_key':'','enabled':True},'SCM');self.assertEqual(ai_settings.load()['api_key'],'sk-test-only-placeholder')
  result=ai_settings.save({'version':2,'clear_key':True},'SCM');self.assertFalse(result['configured']);self.assertFalse(result['key_present'])
 def test_no_key_never_calls_network(self):
  with patch('app.drafts.urlopen') as call:
   with self.assertRaises(ValueError):drafts.complete({'case':'test'},'검토')
   call.assert_not_called()
 def test_real_request_contract_keeps_key_out_of_prompt_and_human_boundary(self):
  self.saved();response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'output':[{'content':[{'type':'output_text','text':'[위험]\n- 지급일 확인 필요.'}]}]}).encode();source={'sku':'SKU-3001','qty':12000};original=copy.deepcopy(source)
  with patch('app.drafts.urlopen',return_value=response) as request:
   result=drafts.complete(source,'- 검토는 개조식으로')
   sent=request.call_args.args[0];payload=json.loads(sent.data);self.assertEqual(sent.full_url,'https://api.openai.com/v1/responses');self.assertNotIn('sk-',json.dumps(payload));self.assertFalse(payload['store']);self.assertNotIn('tools',payload);self.assertIn(BOUNDARY,payload['instructions']);self.assertIn(FORMAT,payload['instructions'])
  self.assertEqual(source,original);self.assertTrue(result['unverified'])
 def test_all_default_prompts_are_bulleted_and_grounded(self):
  from app.prompt_settings import STAGES
  for stage in STAGES:self.assertIn('개조식',default_prompt(stage));self.assertIn('[확인 질문]',default_prompt(stage))
