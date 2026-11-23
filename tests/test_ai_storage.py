import os,unittest
from unittest.mock import patch
from app.ai_storage import seal,open_value
class AIStorageTests(unittest.TestCase):
 def test_encrypt_roundtrip_no_plain_key(self):
  value={'api_key':'sk-test-only-placeholder','version':1,'enabled':True}
  with patch.dict(os.environ,{'SESSION_SECRET':'test-secret-never-used-for-deployment'}):
   encrypted=seal(value);self.assertNotIn(value['api_key'],encrypted);self.assertEqual(open_value(encrypted),value)
  with patch.dict(os.environ,{'SESSION_SECRET':'different-test-secret'}):
   with self.assertRaises(ValueError):open_value(encrypted)
 def test_missing_server_secret_rejected(self):
  with patch.dict(os.environ,{'SESSION_SECRET':''}):
   with self.assertRaises(ValueError):seal({'api_key':'test'})
