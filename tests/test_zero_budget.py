import copy,unittest
from app.marketing import case_from,validate_submission
from app.ax_planning import preview,attach
import tests.test_estimate_application as fixtures
class ZeroBudgetTests(unittest.TestCase):
 def setUp(self):
  f=fixtures.EstimateApplicationTests();f.setUp();self.f=f
 def test_zero_is_present_and_preserved_in_plan_and_estimate(self):
  p=copy.deepcopy(self.f.b['marketing']);p.update(budget=0,media=['오프라인'],country='국내',sales_channel='자사몰',target='기초');validate_submission(p)
  b=case_from(p,self.f.data);self.assertEqual(b['marketing']['budget'],0)
  raw=copy.deepcopy(self.f.inputs);raw.update(budget=0,group_total=0);raw['items'][0].update(qty=0)
  estimate=attach(b,raw,self.f.data,self.f.config,'zero-budget')
  self.assertEqual(estimate['inputs']['budget'],0);self.assertEqual(estimate['schedule']['procurement_budget'],0)
  self.assertNotIn('캠페인 요청액 확인 필요',estimate['issues'])
 def test_missing_negative_and_invalid_are_not_zero(self):
  for budget in [None,'',' ','-1','NaN',1.5,True]:
   with self.subTest(budget=budget),self.assertRaises(ValueError):validate_submission({'media':['기타'],'budget':budget})
 def test_zero_does_not_bypass_other_required_information(self):
  with self.assertRaises(ValueError):validate_submission({'media':[],'budget':0})
