import copy,unittest
from app.marketing_cost import estimate,reference
from app.formulas import context,token,run
from app.ax_planning import preview
import tests.test_estimate_application as fixture
class MarketingCostTests(unittest.TestCase):
 def setUp(self):
  f=fixture.EstimateApplicationTests();f.setUp();self.data=f.data;self.config=f.config;self.raw=f.inputs
  self.cost={'media':['오프라인'],'product_line':'색조','country':'국내','platform':'','sns_format':'','influencer_id':'','other_cost':0}
 def calc(self,cost=None,days=5,data=None):return estimate(cost or self.cost,data or self.data,'2026-07-01','2026-11-01',f'2026-11-{days:02d}')
 def test_original_fees_are_already_in_advertising_cost(self):
  rows=reference()['spend'];self.assertEqual(len(rows),225)
  self.assertEqual(sum(int(r['ad_cost_krw']) for r in rows),763913793)
  self.assertEqual(sum(int(r['influencer_fee_krw']) for r in rows if r['influencer_fee_krw']!='NONE'),397235169)
 def test_daily_reference_uses_completed_comparable_campaigns(self):
  result=self.calc();self.assertGreater(result['recommended_budget'],0)
  for row in result['items'][0]['observations']:
   self.assertLessEqual(row['end'],'2026-07-01');self.assertTrue(row['spend_ids']);self.assertEqual(row['included_fee'],0)
  self.assertAlmostEqual(self.calc(days=10)['recommended_budget'],result['recommended_budget']*2,delta=1)
 def test_influencer_fixed_fee_is_not_added_twice_or_multiplied_by_days(self):
  raw={**self.cost,'media':['인플루언서'],'platform':'YouTube','sns_format':'롱폼','influencer_id':'INF-001'}
  short=self.calc(raw);long=self.calc(raw,days=10)
  self.assertGreater(short['fixed_budget'],0);self.assertEqual(short['variable_budget'],0)
  self.assertEqual(short['recommended_budget'],short['fixed_budget']);self.assertEqual(short['recommended_budget'],long['recommended_budget'])
 def test_missing_references_are_unknown_not_zero(self):
  for change in [{'product_line':'헤어'},{'media':['쿠폰·프로모션']}]:
   result=self.calc({**self.cost,**change});self.assertIsNone(result['recommended_budget']);self.assertTrue(result['missing'])
 def test_dynamic_formula_changes_the_live_estimate(self):
  updated=context(self.data,{'formulas':{'marketing_variable_budget':{'expression':'round_krw(reference_daily * campaign_days * 1.2)'}}})
  self.assertGreater(self.calc(data=updated)['recommended_budget'],self.calc()['recommended_budget']);self.assertNotEqual(token(updated),token(self.data))
 def test_other_cost_added_once_and_invalid_inputs_rejected(self):
  self.assertEqual(self.calc({**self.cost,'other_cost':12345})['recommended_budget'],self.calc()['recommended_budget']+12345)
  for change in [{'other_cost':-1},{'media':[[]]}]:
   with self.assertRaises(ValueError):self.calc({**self.cost,**change})
 def test_budget_split_preserves_cash_rules_and_allows_manual_zero(self):
  raw=copy.deepcopy(self.raw);raw.update(budget=0);raw['items'][0].update(qty=0)
  before=preview(raw,self.data,self.config);raw['marketing_cost_inputs']={**self.cost,'product_line':'기초'};after=preview(raw,self.data,self.config)
  self.assertGreater(after['marketing_cost']['recommended_budget'],0);self.assertEqual(after['inputs']['budget'],0)
  self.assertEqual(before['cash'],after['cash']);self.assertEqual(after['schedule']['procurement_budget'],0)
 def test_procurement_is_separate_from_marketing_budget(self):
  raw={**copy.deepcopy(self.raw),'marketing_cost_inputs':{**self.cost,'product_line':'기초'}};result=preview(raw,self.data,self.config)
  self.assertEqual(result['schedule']['marketing_budget'],result['marketing_cost']['recommended_budget'])
  self.assertEqual(result['schedule']['campaign_total_requirement'],raw['budget']+result['schedule']['procurement_budget'])
  self.assertNotEqual(result['schedule']['marketing_budget'],result['schedule']['campaign_total_requirement'])
  self.assertEqual(result['schedule']['predicted_total_requirement'],result['marketing_cost']['recommended_budget']+result['schedule']['procurement_budget'])

class MarketingReceiptTests(unittest.TestCase):
 def setUp(self):
  f=fixture.EstimateApplicationTests();f.setUp();self.f=f
  self.raw={'media':['오프라인'],'product_line':'기초','country':'국내','other_cost':300,'manual_costs':{'오프라인':{'fixed':1000,'variable':2000}}}
 def test_manual_lines_sum_and_are_serialized_without_losing_reference(self):
  a=estimate(self.raw,self.f.data,'2026-07-01','2026-07-13','2026-07-19')
  self.assertEqual(a['adopted_budget'],3300);self.assertEqual(a['inputs']['manual_costs'],self.raw['manual_costs'])
  self.assertFalse(a['scope_requires_confirmation']);self.assertNotEqual(a['recommended_budget'],a['adopted_budget'])
  self.assertTrue(a['items'][0]['fixed_manual']);self.assertTrue(a['items'][0]['variable_manual'])
 def test_missing_reference_remains_unknown_until_both_lines_entered(self):
  raw={**self.raw,'media':['쿠폰·프로모션'],'manual_costs':{'쿠폰·프로모션':{'fixed':0}}}
  a=estimate(raw,self.f.data,'2026-07-01','2026-07-13','2026-07-19');self.assertIsNone(a['adopted_budget'])
  raw['manual_costs']['쿠폰·프로모션']['variable']=50000
  b=estimate(raw,self.f.data,'2026-07-01','2026-07-13','2026-07-19');self.assertIsNone(b['recommended_budget']);self.assertEqual(b['adopted_budget'],50300)
 def test_partial_manual_keeps_reference_confirmation(self):
  self.raw['manual_costs']['오프라인'].pop('variable')
  a=estimate(self.raw,self.f.data,'2026-07-01','2026-07-13','2026-07-19');self.assertTrue(a['scope_requires_confirmation']);self.assertIsNotNone(a['adopted_budget'])
 def test_mismatched_item_total_is_rejected_before_save(self):
  from app.marketing import case_from
  from app.ax_planning import attach
  p=copy.deepcopy(self.f.b['marketing']);p.update(media=['오프라인'],country='국내',sales_channel='자사몰',target='기초',budget=1234)
  raw=copy.deepcopy(self.f.inputs);raw.update(budget=1234,marketing_cost_inputs={**self.raw,'budget_mode':'items'})
  with self.assertRaises(ValueError):attach(case_from(p,self.f.data),raw,self.f.data,self.f.config,'receipt')
  p['budget']=3300;raw['budget']=3300
  result=attach(case_from(p,self.f.data),raw,self.f.data,self.f.config,'receipt');self.assertEqual(result['marketing_cost']['adopted_budget'],3300)
 def test_invalid_manual_inputs_fail(self):
  for manual in [{'오프라인':{'fixed':-1}},{'퍼포먼스':{'fixed':1}},{'오프라인':{'unknown':1}}]:
   with self.subTest(manual=manual),self.assertRaises(ValueError):estimate({**self.raw,'manual_costs':manual},self.f.data,'2026-07-01','2026-07-13','2026-07-19')
