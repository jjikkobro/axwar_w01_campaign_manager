import copy,unittest
from unittest.mock import patch
from app import formulas,scm,planning
from app.ax_planning import preview
from app.finance import DEFAULT_FINANCE
from app.marketing import case_from
from app.planning_schedule import calculate as schedule
import tests.test_scm as fixture

class SharedPlanningTests(unittest.TestCase):
 def setUp(self):
  f=fixture.ScmTests();f.setUp();self.data=f.data;self.data['portfolio']={'rows':[]}
  p=copy.deepcopy(f.case['marketing']);p.update(start='2026-11-16',end='2026-11-20',budget=5000000,submission_mode='estimate_only',scope_skus=['SKU-3003'])
  p['items']=[{**p['items'][0],'sku_id':'SKU-3003','start':p['start'],'end':p['end'],'demand':100}]
  self.case=case_from(p,self.data);self.case['_case_id']='shared-case';self.config={**copy.deepcopy(DEFAULT_FINANCE),'version':1}
  self.inputs={'mode':'estimate_only','as_of':p['as_of'],'start':p['start'],'end':p['end'],'budget':p['budget'],'items':[{'sku_id':'SKU-3003','demand_mode':'manual','demand':100,'qty_mode':'forecast','price_mode':'forecast'}]}
 def both(self,config=None):
  config=config or self.config;return preview(self.inputs,self.data,config,'shared-case'),scm.analysis(self.case,self.data,config)
 def test_marketing_and_scm_share_quantities_dates_and_regular_orders(self):
  a,b=self.both();self.assertEqual(a['planning']['items'],b['planning']['items'])
  self.assertEqual(a['replenishment']['items'],b['replenishment']['items'])
  self.assertEqual(a['items'][0]['recommended_qty'],b['planning']['items'][0]['recommended_qty'])
 def test_lead_time_setting_reaches_every_planning_date(self):
  config={**self.config,'formulas':{'lead_time_days':{'expression':'lead_weeks * 5'}}};a,b=self.both(config)
  self.assertEqual(a['planning']['items'],b['planning']['items']);self.assertEqual(a['items'][0]['earliest_arrival_assumption'],'2026-07-31')
  row={**a['items'][0],'chosen_qty':10000};s=schedule(a['inputs'],[row],data=formulas.context(self.data,config))
  self.assertEqual(s['orders'][0]['earliest_arrival'],a['items'][0]['earliest_arrival_assumption']);self.assertEqual(s['orders'][0]['order_by'],a['planning']['items'][0]['order_by'])
  self.assertNotEqual(a['planning']['formula_revision'],self.both()[0]['planning']['formula_revision'])
 def test_moq_is_applied_once_and_custom_model_is_shared(self):
  self.case['marketing']['items'][0].update(demand=500000,total_quantity=500000*5/7);self.inputs['items'][0]['demand']=500000
  config={**self.config,'formulas':{'procurement_moq':{'expression':'max(gap, moq) * 2'}}};a,b=self.both(config)
  self.assertGreater(a['planning']['items'][0]['recommended_qty'],0)
  self.assertEqual(a['planning']['items'],b['planning']['items'])
  self.assertEqual(a['planning']['items'][0]['recommended_qty'],a['replenishment']['items'][0]['incremental_qty'])
 def test_catalog_respects_the_same_average_formula(self):
  config={**self.config,'formulas':{'weekly_average':{'expression':'sales_total / weeks_count * 1.1'}}};a,b=self.both(config)
  row=next(i for i in planning.catalog(formulas.context(self.data,config)) if i['sku_id']=='SKU-3003')
  self.assertEqual(row['weekly_average'],a['items'][0]['baseline_weekly']);self.assertEqual(round(row['weekly_average'],2),b['items'][0]['weekly'])
 def test_revision_tracks_new_defaults_and_shared_receipts(self):
  original=formulas.revision(self.data,self.config)
  replacement={**formulas.CATALOG['safety_target'],'default':'weekly * safety_weeks * 1.1'}
  with patch.dict(formulas.CATALOG,{'safety_target':replacement}):self.assertNotEqual(original['formula_revision'],formulas.revision(self.data,self.config)['formula_revision'])
  self.data['portfolio']['rows'].append({'case_id':'other','receipts':{'SPO-0001':{'qty':1}}})
  changed=formulas.revision(self.data,self.config);self.assertEqual(original['formula_revision'],changed['formula_revision']);self.assertNotEqual(original['revision'],changed['revision'])
 def test_actual_orders_and_receipts_are_not_overwritten_by_recalculation(self):
  from app.execution import operational_schedule
  self.case['execution']={'orders':[{'po_id':'ACTUAL-1','sku_id':'SKU-3003','order_qty':10000,'amount_krw':168000000,'order_date':'2026-07-03','wanted_date':'2026-09-01','payment_due_date':'2026-07-21'}]}
  before=copy.deepcopy(self.case);self.both({**self.config,'formulas':{'lead_time_days':{'expression':'lead_weeks * 5'}}});self.assertEqual(before,self.case)
