import copy,json,unittest
from pathlib import Path
from app import formulas as f
from app.domain import calculate
from app.finance import DEFAULT_FINANCE,cash_bundle
from app.scm import analysis,basis
from app.execution import projection
import tests.test_execution as execution_tests
class FormulaTests(unittest.TestCase):
 def setUp(self):
  e=execution_tests.ExecutionTests();e.setUp();self.case=e.b;self.data=e.data;self.config=e.config
  self.raw={'formula_id':'weekly_average','expression':'sales_total / weeks_count * 1.1','decision_maker':'마케팅 담당','reason':'보수적 수요 가정','evidence':'시험 근거'}
 def test_all_defaults_match_examples(self):
  for key,s in f.CATALOG.items():self.assertIsInstance(f.evaluate(key,s['default'],s['example']),(int,float))
 def test_arbitrary_code_and_invalid_numbers_rejected(self):
  for expr in ['__import__("os")','sales_total.__class__','sales_total[0]','2 ** 100','[sales_total]','max(x=2)','sales_total / 0','1e309','-1','sales_total * 1000000000000000']:
   with self.subTest(expr=expr),self.assertRaises(ValueError):f.evaluate('weekly_average',expr,{'sales_total':4000,'weeks_count':4})
  for values in [None,[],{'sales_total':True,'weeks_count':4},{'sales_total':float('nan'),'weeks_count':4}]:
   with self.assertRaises(ValueError):f.evaluate('weekly_average','sales_total / weeks_count',values)
 def test_role_and_metadata_guards(self):
  for role in ['SCM','재무','승인권자']:
   with self.assertRaises(ValueError):f.candidate(self.config,self.raw,role)
  for key in ['decision_maker','reason','evidence']:
   with self.assertRaises(ValueError):f.candidate(self.config,{**self.raw,key:''},'마케팅')
  with self.assertRaises(ValueError):f.candidate(self.config,{**self.raw,'formula_id':'approval_authority'},'승인권자')
 def test_runtime_changes_real_stock_and_invalidates_review(self):
  config=f.candidate(self.config,self.raw,'마케팅');data=f.context(self.data,config)
  before=analysis(self.case,self.data,self.config);after=analysis(self.case,data,config)
  self.assertAlmostEqual(after['items'][0]['weekly'],before['items'][0]['weekly']*1.1,delta=.02)
  self.assertLess(after['items'][0]['campaign_min'],before['items'][0]['campaign_min'])
  self.assertNotEqual(basis(self.case,self.data),basis(self.case,data))
  self.assertFalse(projection(self.case,data,config)['finance_valid'])
 def test_integrated_portfolio_uses_identical_formula(self):
  config=f.candidate(self.config,self.raw,'마케팅');data=f.context(self.data,config);data['portfolio']={'rows':[]};b=copy.deepcopy(self.case);b['_case_id']='fixture'
  single=calculate(b,data,config)['items'][0]
  self.assertAlmostEqual(single['weekly'],single['portfolio']['items'][0]['weekly_average'],delta=.01)
 def test_moq_money_and_cash_guards(self):
  with self.assertRaises(ValueError):f.evaluate('procurement_moq','gap',{'gap':1,'moq':10000})
  self.assertEqual(f.evaluate('purchase_amount','round_krw(qty * unit_price)',{'qty':1,'unit_price':2.5}),3)
  before=cash_bundle(self.data,self.config)
  config=f.candidate(self.config,{'formula_id':'cash_gap','expression':'max(threshold - closing, 0) * 1.1',**{k:self.raw[k] for k in ['decision_maker','reason','evidence']}},'재무');after=cash_bundle(self.data,config)
  for key,scenario in before['scenarios'].items():
   self.assertEqual(scenario['cash_min'],after['scenarios'][key]['cash_min']);self.assertEqual(scenario['breach_dates'],after['scenarios'][key]['breach_dates'])
 def test_reset_and_preview_are_pure(self):
  before=copy.deepcopy(self.config);result=f.impact(self.config,self.raw,'마케팅',self.data,[('fixture',self.case)])
  self.assertEqual(before,self.config);self.assertEqual(len(result['cases']),1)
  reset=f.candidate({**result['candidate'],'version':2},{**self.raw,'expression':f.CATALOG['weekly_average']['default']},'마케팅')
  self.assertEqual(reset['formulas'],{})
 def test_campaign_daily_cover_and_safety_models_reach_runtime(self):
  before=calculate(self.case,self.data,self.config)
  config={**self.config,'formulas':{'campaign_daily':{'expression':'total_quantity / duration_days * 2'},'inventory_cover':{'expression':'on_hand / weekly * 0.9'},'safety_target':{'expression':'weekly * safety_weeks * 1.2'}}}
  after=calculate(self.case,self.data,config)
  self.assertGreater(after['stock'][12]['campaign'],before['stock'][12]['campaign'])
  self.assertLess(after['simple_cover'],before['simple_cover'])
  self.assertAlmostEqual(after['cover'],before['cover']*.9,delta=.02)
  self.assertAlmostEqual(after['safety_target'],before['safety_target']*1.2)
 def test_procurement_and_financial_diagnostic_runtime(self):
  self.case['scm']['review']['items']=[{'sku_id':'SKU-2002','target_qty':30000,'requested_unit_price':12600}]
  before=analysis(self.case,self.data,self.config)['items'][0]['procurement']
  config={**self.config,'formulas':{'procurement_gap':{'expression':'max(target - on_hand - in_transit, 0) * 2'},'purchase_amount':{'expression':'round_krw(qty * unit_price * 1.1)'},'forecast_difference':{'expression':'(recalculated - official) * 2'}}}
  after=analysis(self.case,self.data,config)['items'][0]['procurement']
  self.assertAlmostEqual(after['raw_suggested_qty'],before['raw_suggested_qty']*2)
  self.assertGreater(after['estimated_amount'],before['estimated_amount'])
  oldcash=cash_bundle(self.data,self.config);newcash=cash_bundle(self.data,config)
  old=oldcash['scenarios']['exclude_pay'];new=newcash['scenarios']['exclude_pay']
  self.assertEqual(old['weekly'][0]['difference']*2,new['weekly'][0]['difference'])
  self.assertEqual(old['cash_min'],new['cash_min'])
 def test_sample_and_live_domain_errors(self):
  with self.assertRaises(ValueError):f.impact(self.config,{**self.raw,'expression':'sales_total / (weeks_count - 4)'},'마케팅',self.data,[('fixture',self.case)])
if __name__=='__main__':unittest.main()
