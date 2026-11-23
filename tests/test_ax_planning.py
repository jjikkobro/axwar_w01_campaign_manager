import copy,unittest
from app.ax_planning import preview,attach,current,confirm
from app.execution import projection
from app.marketing import case_from
import tests.test_execution as e
class AXPlanningTests(unittest.TestCase):
 def setUp(self):
  x=e.ExecutionTests();x.setUp();self.data=x.data;self.config=x.config;self.p=copy.deepcopy(x.b['marketing']);self.data['portfolio']={'rows':[]};self.cid='ax-test'
  self.inputs={'as_of':'2026-07-01','start':'2026-07-13','end':'2026-07-19','budget':5000000,'settlement_date':'2026-09-21','items':[{'sku_id':'SKU-2002','demand_mode':'manual','demand':100,'qty_mode':'manual','qty':0,'price_mode':'manual','unit_price':12600}]}
  self.meta={'decision_maker':'부서 확인 담당','reason':'사전검토의 수요·공급·현금·결재선과 긴급 이슈 확인','evidence':'원본 근거·현재 입력 확인'}
 def ready(self):
  self.p['items'][0].update(demand=100,unit='EA/주');self.p.update(budget=5000000,settlement_date='2026-09-21')
  b=case_from(self.p,self.data);b['_case_id']=self.cid;b['marketing_stage']='SCM 검토 요청';b['ax_plan']=attach(b,self.inputs,self.data,self.config,self.cid);return b
 def test_forecast_is_bounded_history_and_read_only(self):
  before=copy.deepcopy(self.data);p=preview(self.inputs,self.data,self.config,self.cid)
  self.assertEqual(before,self.data);self.assertGreater(p['items'][0]['observations'],4);self.assertEqual(p['items'][0]['history']['from'],'2025-01-06');self.assertLess(p['items'][0]['history']['to'],'2026-06-29');self.assertTrue(p['simple_review_eligible'])
 def test_missing_payment_blocks_new_order_not_invented(self):
  raw=copy.deepcopy(self.inputs);raw['items'][0].update(qty_mode='forecast',price_mode='forecast')
  p=preview(raw,self.data,self.config,self.cid);self.assertIsNone(p['items'][0]['payment_date']);self.assertIsNone(p['cash']['minimum_after']);self.assertFalse(p['simple_review_eligible']);self.assertTrue(any('지급일' in x for x in p['issues']))
 def test_late_replenishment_does_not_claim_supply(self):
  raw=copy.deepcopy(self.inputs);raw['items'][0].update(sku_id='SKU-1001',demand=12000,qty_mode='forecast',price_mode='forecast',payment_date='2026-07-27')
  p=preview(raw,self.data,self.config,self.cid);self.assertFalse(p['simple_review_eligible']);self.assertTrue(any('공급 부족' in x for x in p['issues']));self.assertTrue(any(r['authority']=='CEO/이사회' for r in p['routes']))
 def test_preplan_matches_plan_and_stales_on_data_change(self):
  b=self.ready();current(b,self.data,self.config)
  other=copy.deepcopy(self.data);other['sales']['version']=99
  with self.assertRaises(ValueError):current(b,other,self.config)
  b['marketing']['budget']+=1
  with self.assertRaises(ValueError):current(b,self.data,self.config)
 def test_human_confirmations_reach_approval_without_approving(self):
  b=self.ready();self.assertEqual(projection(b,self.data,self.config)['stage'],2)
  b,_=confirm(b,self.data,self.config,self.meta,'SCM');self.assertEqual(projection(b,self.data,self.config)['stage'],3)
  b,_=confirm(b,self.data,self.config,{**self.meta,'decision_maker':'재무 확인 담당'},'재무');x=projection(b,self.data,self.config);self.assertEqual(x['stage'],4);self.assertTrue(x['finance_valid']);self.assertFalse(b.get('execution',{}).get('decisions'));self.assertFalse(b.get('execution',{}).get('orders'))
 def test_custom_ax_gap_is_managed_in_formula_settings(self):
  original=preview(self.inputs,self.data,self.config,self.cid)
  data=copy.deepcopy(self.data);data['formula_settings']={'entries':{'ax_replenishment_gap':{'expression':'max(safety_target - minimum_projected, 0) * 2'}},'version':2}
  modified=preview(self.inputs,data,self.config,self.cid)
  self.assertGreater(modified['items'][0]['recommended_qty'],original['items'][0]['recommended_qty'])
  self.assertNotEqual(modified['basis'],original['basis'])
 def test_invalid_input_and_mismatched_plan_do_not_attach(self):
  for item in [{'sku_id':[]},{'sku_id':'SKU-2002','demand_mode':'manual','demand':-1}]:
   with self.assertRaises(ValueError):preview({**self.inputs,'items':[item]},self.data,self.config,self.cid)
  b=self.ready();b['marketing']['group_total']=200000000
  with self.assertRaises(ValueError):attach(b,self.inputs,self.data,self.config,self.cid)
 def test_wrong_role_and_unconfirmed_cash_cannot_fast_track(self):
  b=self.ready()
  with self.assertRaises(ValueError):confirm(b,self.data,self.config,self.meta,'마케팅')
  with self.assertRaises(ValueError):confirm(b,self.data,self.config,self.meta,'재무')
  cfg={**self.config,'confirmed':False};self.assertFalse(preview(self.inputs,self.data,cfg,self.cid)['simple_review_eligible'])
if __name__=='__main__':unittest.main()
