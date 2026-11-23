import copy,unittest
from app import scm,replenishment,demand
from app.marketing import case_from
from app.finance import DEFAULT_FINANCE
import tests.test_scm as fixture

class ReplenishmentTests(unittest.TestCase):
 def setUp(self):
  f=fixture.ScmTests();f.setUp();self.data=f.data;self.case=f.case;self.review=f.review
  self.data['portfolio']={'rows':[]};self.case['_case_id']='replenishment-case'
 def november(self):
  p=copy.deepcopy(self.case['marketing']);p.update(start='2026-11-16',end='2026-11-20');p['items'][0].update(start=p['start'],end=p['end'],demand=100)
  self.case=case_from(p,self.data);self.case['_case_id']='replenishment-case'
 def test_lead_time_plus_week_threshold_places_order_this_week(self):
  self.data['purchase']['rows']=[]
  sku=next(s for s in self.data['sku']['rows'] if s['sku_id']=='SKU-2002');sku.update(lead_time_weeks='2',moq='50')
  for r in self.data['sales']['rows']:
   if r['sku_id']=='SKU-2002':r['sold_qty']='100'
  next(r for r in self.data['inventory']['rows'] if r['sku_id']=='SKU-2002').update(on_hand_qty='650',in_transit_qty='0')
  result=replenishment.plan(self.case,self.data)['items'][0];first=result['regular_orders'][0]
  self.assertEqual(first['order_date'],'2026-07-01');self.assertEqual(first['date'],'2026-07-15')
  self.assertLessEqual(first['lead_plus_week_stock'],first['safety_qty']);self.assertEqual(first['qty'],150)
 def test_long_campaign_has_procurement_option_not_refusal(self):
  self.november();result=scm.analysis(self.case,self.data)
  self.assertEqual(result['recommendation']['kind'],'procurement');self.assertTrue(result['replenishment']['feasible'])
  self.assertGreater(result['replenishment']['items'][0]['regular_qty'],0)
  self.assertLess(result['items'][0]['campaign_min'],0);self.assertEqual(sum(d['inflow'] for d in result['items'][0]['stock']),0)
 def test_marketing_estimate_does_not_turn_assumed_supply_into_scm_confirmation(self):
  from app.ax_planning import preview
  self.november();p=self.case['marketing']
  raw={'mode':'estimate_only','as_of':p['as_of'],'start':p['start'],'end':p['end'],'budget':0,'settlement_date':None,'items':[{'sku_id':'SKU-2002','demand_mode':'manual','demand':100,'qty_mode':'forecast','price_mode':'forecast'}]}
  result=preview(raw,self.data,DEFAULT_FINANCE)
  self.assertTrue(result['items'][0]['regular_condition_required']);self.assertLess(result['items'][0]['campaign_min_before'],0)
  self.assertTrue(result['scm_pending']);self.assertFalse(result['scm_review_eligible']);self.assertFalse(result['simple_review_eligible'])
 def test_zero_increment_does_not_charge_regular_orders_to_campaign(self):
  self.november();self.case['marketing']['items'][0].update(demand=0,total_quantity=0)
  i=replenishment.plan(self.case,self.data)['items'][0]
  self.assertEqual(i['incremental_qty'],0);self.assertGreater(i['regular_qty'],0)
 def test_planning_is_read_only_and_keeps_lead_time_gap(self):
  self.november();before=copy.deepcopy(self.data);b=copy.deepcopy(self.case)
  result=replenishment.plan(self.case,self.data);self.assertEqual(before,self.data);self.assertEqual(b,self.case)
  for r in result['items'][0]['regular_orders']:
   from datetime import date
   self.assertEqual((date.fromisoformat(r['date'])-date.fromisoformat(r['order_date'])).days,56)
 def test_po_pipeline_does_not_add_aggregate_transit_twice(self):
  self.november();first=replenishment.plan(self.case,self.data)
  next(r for r in self.data['inventory']['rows'] if r['sku_id']=='SKU-2002')['in_transit_qty']='999999'
  self.assertEqual(first,replenishment.plan(self.case,self.data)|{'basis':first['basis']})
 def test_confirmation_is_required_but_no_normal_override(self):
  self.case['marketing']['items'][0].update(demand=100,total_quantity=100)
  a=demand.assess(self.case,self.data);self.assertFalse(a['warnings'])
  before=copy.deepcopy(self.case)
  with self.assertRaises(ValueError):scm.handoff_demand(self.case,self.data,DEFAULT_FINANCE,self.review,None)
  b,event=scm.handoff_demand(self.case,self.data,DEFAULT_FINANCE,self.review,{'checked':True,'basis':a['basis']})
  self.assertTrue(demand.assess(b,self.data)['ready']);self.assertEqual(before,self.case);self.assertIsNotNone(event)
 def test_missing_stale_or_outside_demand_cannot_bypass_confirmation(self):
  a=demand.assess(self.case,self.data)
  with self.assertRaises(ValueError):scm.handoff_demand(self.case,self.data,DEFAULT_FINANCE,self.review,{'checked':True,'basis':'old'})
  self.case['marketing']['scope_skus'].append('SKU-2001');a=demand.assess(self.case,self.data)
  with self.assertRaises(ValueError):scm.handoff_demand(self.case,self.data,DEFAULT_FINANCE,self.review,{'checked':True,'basis':a['basis']})
  self.case['marketing']['scope_skus'].remove('SKU-2001');self.case['marketing']['items'][0].update(demand=99999,total_quantity=99999)
  a=demand.assess(self.case,self.data)
  with self.assertRaises(ValueError):scm.handoff_demand(self.case,self.data,DEFAULT_FINANCE,self.review,{'checked':True,'basis':a['basis']})
 def test_existing_confirmed_po_is_not_assumed_again(self):
  r=scm.validate_receipt({'po_id':'SPO-0006','status':'확인','qty':16000,'available_date':'2026-08-06','decision_maker':'SCM','reason':'확인','evidence':'모의 회신','provenance':'모의 회신'},self.case,self.data)
  self.case['scm']={'receipts':{'SPO-0006':r}};self.november()
  # november() rebuilds the case, so retain the explicit reply on the new plan.
  self.case['scm']={'receipts':{'SPO-0006':r}}
  result=replenishment.plan(self.case,self.data)['items'][0]
  self.assertNotIn('SPO-0006',[o['id'] for o in result['pipeline_assumptions']])
 def test_adopted_draft_rechecks_business_values_and_rejects_changed_demand(self):
  from app.ax_planning import adopted
  p=self.case['marketing'];p['budget']=1000000
  raw={'mode':p.get('submission_mode','normal'),'as_of':p['as_of'],'start':p['start'],'end':p['end'],'budget':p['budget'],'group_total':p['budget'],'settlement_date':None,'items':[{'sku_id':'SKU-2002','demand_mode':'manual','demand':1000,'qty_mode':'manual','qty':16000,'price_mode':'manual','unit_price':12600}]}
  self.case['ax_plan']={'plan_signature':'legacy-json-numeric-difference','inputs':raw}
  self.assertEqual(adopted(self.case,self.data,DEFAULT_FINANCE)['items'][0]['chosen_qty'],16000)
  p['items'][0]['total_quantity']+=1
  self.assertIsNone(adopted(self.case,self.data,DEFAULT_FINANCE))
 def test_missing_scope_demand_renders_a_repairable_result(self):
  self.case['marketing']['scope_skus'].append('SKU-2001')
  result=scm.analysis(self.case,self.data)
  self.assertEqual(result['recommendation']['kind'],'missing')
  self.assertFalse(result['replenishment']['feasible'])
 def test_regular_plan_confirmation_can_be_handed_off_without_fake_new_po(self):
  self.november();calculation=scm.analysis(self.case,self.data)
  self.review.update(direction='재고로 가능',reason='정기 보충 계획과 공급 확인 조건을 검토함');self.review['items'][0].update(supply_result='가능')
  r=scm.validate_review(self.review,self.case,self.data)
  scm.can_handoff(r,calculation)
  wrong={**r,'direction':'추가 발주 필요'}
  with self.assertRaises(ValueError):scm.can_handoff(wrong,calculation)
  calculation['replenishment']['feasible']=False
  with self.assertRaises(ValueError):scm.can_handoff(r,calculation)
if __name__=='__main__':unittest.main()
