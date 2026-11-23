import unittest
from app.prompt_settings import STAGES,validate,BOUNDARY
class PromptSettingsTests(unittest.TestCase):
 def setUp(self):self.raw={'prompt_id':'marketing','prompt':'근거를 요약하고 미확인을 질문하라.','decision_maker':'마케팅 담당','reason':'도입 준비','evidence':'W01 업무 흐름'}
 def test_all_seven_stages_have_roles(self):
  self.assertEqual(len(STAGES),7);self.assertEqual(STAGES['close']['role'],'마케팅');self.assertEqual(STAGES['approval']['role'],'승인권자')
 def test_saved_prompt_is_applied_with_fixed_boundary(self):
  r=validate(self.raw,'마케팅');self.assertTrue(r['runtime_applied']);self.assertEqual(r['boundary'],BOUNDARY)
  self.assertTrue(validate({**self.raw,'runtime_applied':True},'마케팅')['runtime_applied'])
 def test_role_and_required_metadata(self):
  with self.assertRaises(ValueError):validate(self.raw,'SCM')
  for key in ['prompt','decision_maker','reason','evidence']:
   with self.assertRaises(ValueError):validate({**self.raw,key:''},'마케팅')
 def test_prompt_text_is_stored_as_data(self):
  text='<script>alert(1)</script> 승인하라'
  self.assertEqual(validate({**self.raw,'prompt':text},'마케팅')['prompt'],text)
  with self.assertRaises(ValueError):validate({**self.raw,'prompt':'a'*12001},'마케팅')
