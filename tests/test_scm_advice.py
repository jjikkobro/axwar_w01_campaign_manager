import copy,unittest
import tests.test_scm as fixture
from app import scm
from app.marketing import case_from
from app.demand import signature
class ScmAdviceTests(unittest.TestCase):
 def setUp(self):
  f=fixture.ScmTests();f.setUp();self.data=f.data;self.data['portfolio']={'rows':[]};self.case=f.case;self.case['_case_id']='advice-case'
 def plan(self,start,end,qty=7000):
  p=copy.deepcopy(self.case['marketing']);p.update(start=start,end=end);p['items'][0].update(demand=qty,start=start,end=end,unit='EA/주');self.case=case_from(p,self.data);self.case['_case_id']='advice-case'
 def inbound(self,date,qty=16000):
  r=scm.validate_receipt({'po_id':'SPO-0006','status':'확인','qty':qty,'available_date':date,'decision_maker':'SCM','reason':'회신 검증','evidence':'모의 공급처 회신','provenance':'모의 회신'},self.case,self.data);self.case.setdefault('scm',{}).setdefault('receipts',{})['SPO-0006']=r
 def test_confirmed_inbound_shift_is_recalculated_and_sourced(self):
  self.plan('2026-07-27','2026-08-02');self.inbound('2026-08-06')
  advice=scm.analysis(self.case,self.data)['recommendation'];shift=next(a for a in advice['actions'] if a['type']=='shift_campaign')
  self.assertEqual(shift['start'],'2026-08-06');self.assertGreaterEqual(shift['minimum'],0);self.assertIn('SPO-0006',shift['source']);self.assertIn('겹치지 않습니다',shift['text'])
 def test_pre_campaign_shortage_is_separate_from_campaign_viability(self):
  self.plan('2026-08-06','2026-08-12');self.inbound('2026-08-06')
  result=scm.analysis(self.case,self.data);self.assertIsNotNone(result['items'][0]['first_short_before_campaign']);self.assertIsNone(result['items'][0]['first_short_in_campaign']);self.assertEqual(result['recommendation']['kind'],'ready');self.assertTrue(any('캠페인 시작 전' in text for text in result['recommendation']['why']))
 def test_marketing_estimate_is_carried_without_becoming_confirmed_supply(self):
  self.plan('2026-09-01','2026-09-07',100)
  self.case['ax_plan']={'plan_signature':signature(self.case['marketing']),'items':[{'sku_id':'SKU-2002','chosen_qty':40000,'chosen_unit_price':12600,'earliest_arrival_assumption':'2026-08-26'}]}
  result=scm.analysis(self.case,self.data);p=result['items'][0]['procurement'];self.assertEqual(p['effective_proposal_qty'],40000);self.assertEqual(p['requested_unit_price'],12600);self.assertIn(result['recommendation']['kind'],['conditional','procurement']);self.assertEqual(sum(d['inflow'] for d in result['items'][0]['stock']),0)
 def test_regular_replenishment_is_not_campaign_extra_order(self):
  self.plan('2026-11-15','2026-11-20',21);result=scm.analysis(self.case,self.data);a=result['recommendation']
  self.assertEqual(a['kind'],'procurement');self.assertFalse(a['campaign_extra_required']);self.assertIn('재고로 가능',a['label'])
  self.assertTrue(any('미확인 기존 발주' in why for why in a['why']));self.assertTrue(any('가정에서만' in why for why in a['why']))
  self.assertLess(result['items'][0]['campaign_min'],0);self.assertGreaterEqual(a['scenario'][0]['minimum'],0)
 def test_unconfirmed_order_does_not_create_a_verified_shift(self):
  self.plan('2026-07-27','2026-08-02');a=scm.analysis(self.case,self.data)['recommendation'];self.assertFalse(any(x['type']=='shift_campaign' for x in a['actions']))
 def test_insufficient_confirmed_receipt_is_not_a_schedule_solution(self):
  self.plan('2026-07-27','2026-08-02');self.inbound('2026-08-06',100)
  advice=scm.analysis(self.case,self.data)['recommendation'];self.assertFalse(any(a['type']=='shift_campaign' for a in advice['actions']))
 def test_impossible_reduction_does_not_claim_a_solution(self):
  self.plan('2026-07-27','2026-08-02');a=scm.analysis(self.case,self.data)['recommendation'];self.assertTrue(any(x['type']=='baseline_shortage' for x in a['actions']))
 def test_viable_demand_reduction_is_quantitative(self):
  self.plan('2026-07-13','2026-07-19',20000);a=scm.analysis(self.case,self.data)['recommendation'];r=next(x for x in a['actions'] if x['type']=='reduce_demand');self.assertLess(r['max_demand'],20000);self.assertGreaterEqual(r['max_demand'],0)
if __name__=='__main__':unittest.main()
