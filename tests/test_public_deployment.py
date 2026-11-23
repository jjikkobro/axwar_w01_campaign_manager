import os,unittest
from unittest.mock import patch,Mock
from app import ai_settings,server

class PublicDeploymentTests(unittest.TestCase):
 def test_public_access_ignores_password_and_cookie(self):
  handler=object.__new__(server.Handler);handler.client_address=('203.0.113.7',1234);handler.headers={}
  with patch.object(server,'PUBLIC_ACCESS',True),patch.object(server,'PASSWORD','old-password'):
   self.assertTrue(handler.authorized())
  with patch.object(server,'PUBLIC_ACCESS',False),patch.object(server,'PASSWORD','old-password'):
   self.assertFalse(handler.authorized())
  with patch.object(server,'PUBLIC_ACCESS',False),patch.object(server,'PASSWORD',''):
   self.assertFalse(handler.authorized());handler.client_address=('127.0.0.1',1234);self.assertTrue(handler.authorized())
 def test_public_server_binds_all_interfaces_without_password(self):
  with patch.object(server,'PUBLIC_ACCESS',True),patch.object(server,'PASSWORD',''),patch.object(server,'ThreadingHTTPServer') as http:
   server.main();self.assertEqual(http.call_args.args[0][0],'0.0.0.0')
 def test_environment_key_wins_without_reading_file_or_db(self):
  with patch.dict(os.environ,{'AI_SETTINGS_BACKEND':'environment','AI_API_KEY':'sk-unit-test','AI_MODEL':'gpt-5-mini'}),patch.object(ai_settings,'path') as path,patch('app.ai_storage.read') as db:
   self.assertEqual(ai_settings.load()['api_key'],'sk-unit-test');self.assertTrue(ai_settings.public()['environment_managed'])
   self.assertNotIn('sk-unit-test',str(ai_settings.public()));path.assert_not_called();db.assert_not_called()
 def test_public_app_cannot_replace_or_clear_environment_key(self):
  with patch.dict(os.environ,{'AI_SETTINGS_BACKEND':'environment','AI_API_KEY':'sk-unit-test'}),patch('app.ai_storage.write') as write:
   for body in [{'api_key':'sk-replacement'},{'clear_key':True},{'enabled':False}]:
    with self.assertRaisesRegex(ValueError,'환경변수'):ai_settings.save(body,'SCM')
   self.assertEqual(ai_settings.load()['api_key'],'sk-unit-test');write.assert_not_called()
