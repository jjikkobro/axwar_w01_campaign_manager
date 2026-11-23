import unittest
from app.planning_schedule import calculate,terms
class PlanningScheduleTests(unittest.TestCase):
 def setUp(self):
  self.inputs={'as_of':'2026-07-01','start':'2026-07-13','end':'2026-07-19'}
  self.rows=[{'sku_id':'SKU-2002','chosen_qty':0,'lead_time_weeks':8,'estimated_cost':0}]
 def test_no_inferred_settlement_and_no_extra_order(self):
  r=calculate(self.inputs,self.rows);self.assertIsNone(r['suggested_settlement']);self.assertEqual(r['orders'],[]);self.assertEqual(r['suggested_deadline'],'2026-07-08');self.assertTrue(r['deadline_applicable'])
 def test_explicit_terms_yield_proposed_settlement(self):
  r=calculate(self.inputs,self.rows,{'settlement_base':'end','settlement_offset_days':30,'review_business_days':3});self.assertEqual(r['suggested_settlement'],'2026-08-18')
  self.assertEqual(calculate(self.inputs,self.rows,{'settlement_base':'start','settlement_offset_days':0})['suggested_settlement'],'2026-07-13')
 def test_lead_time_deadline_in_past_cannot_be_adopted(self):
  self.rows[0].update(chosen_qty=16000,estimated_cost=201600000)
  r=calculate(self.inputs,self.rows);self.assertEqual(r['orders'][0]['order_by'],'2026-05-18');self.assertFalse(r['deadline_applicable']);self.assertEqual(r['procurement_budget'],201600000)
 def test_missing_cost_is_not_zero(self):
  self.rows[0].update(chosen_qty=16000,estimated_cost=None)
  self.assertIsNone(calculate(self.inputs,self.rows)['procurement_budget'])
 def test_invalid_terms_rejected(self):
  for t in [{'settlement_offset_days':-1},{'review_business_days':True},{'settlement_base':'unknown'},{'review_business_days':1.5}]:
   with self.assertRaises(ValueError):terms(t)
