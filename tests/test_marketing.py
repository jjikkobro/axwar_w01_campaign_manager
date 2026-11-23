import copy,json,unittest
from pathlib import Path
from app.marketing import case_from,tasks
from app.domain import calculate,transition,validate_reply
from app.drafts import generate
from app.policy import PROJECT_POLICY

class MarketingTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads(Path('data/seed.json').read_text())
  self.plan={'title':'계획 공유','author':'마케팅 담당','department':'마케팅','purpose':'원본 기반 확대 검토','written_date':'2026-07-01','as_of':'2026-07-01','start':'2026-07-13','end':'2026-07-26','reference_plan_id':'PLAN-001','budget':18962703,'expected_gmv':213330410,'performance_status':'미확인','performance_unknown_reason':'비용 범위 담당자 확인 필요','items':[{'sku_id':'SKU-1001','demand':700,'unit':'EA/주','start':'2026-07-13','end':'2026-07-19','basis':'주간 순증 가정','confidence':'보통','overlap':'기존 판매 제외한 순증'},{'sku_id':'SKU-2001','demand':100,'unit':'EA/기간','start':'2026-07-20','end':'2026-07-26','basis':'후반 기간 전체 추가 가정','confidence':'낮음','overlap':'중복 여부 미확인'}]}
 def test_reference_and_new_values_are_separate(self):
  self.plan['budget']=900
  c=case_from(self.plan,self.data)
  self.assertEqual(c['marketing']['reference']['plan']['requested_budget_krw'],'18962703')
  self.assertEqual(c['marketing']['budget'],900)
  self.assertEqual(c['marketing']['reference']['campaign']['campaign_id'],'CMP-0003')
  self.assertEqual(c['marketing']['reference']['campaign']['start_date'],'2025-12-30')
  self.assertIsNone(c['requested_amount']);self.assertIsNone(c['requested_payment_date'])
 def test_settlement_draft_never_becomes_confirmed_payment_date(self):
  from app.marketing import validate
  p=copy.deepcopy(self.plan);p.update(submission_mode='estimate_only',settlement_draft={'date':'2026-08-29','basis':'동일 제품군 표본 중앙값'} )
  saved=validate(p,self.data);self.assertEqual(saved['settlement_draft']['date'],'2026-08-29');self.assertIn('재무 확인 전',saved['settlement_draft']['provenance']);self.assertIsNone(saved['settlement_date'])
 def test_multi_product_demand_is_not_combined_and_periods_are_respected(self):
  calc=calculate(case_from(self.plan,self.data),self.data)
  a,b=calc['items'];self.assertEqual(a['weekly'],8320.75);self.assertEqual(b['weekly'],4079.25)
  self.assertEqual(a['demand']['total_quantity'],700);self.assertEqual(b['demand']['total_quantity'],100)
  self.assertEqual(a['weeks'],['2026-06-01','2026-06-08','2026-06-15','2026-06-22'])
  self.assertEqual(next(x for x in a['stock'] if x['date']=='2026-07-20')['campaign'],0)
  self.assertEqual(next(x for x in b['stock'] if x['date']=='2026-07-13')['campaign'],0)
  self.assertAlmostEqual(sum(x['campaign'] for x in a['stock']),700)
  self.assertAlmostEqual(sum(x['campaign'] for x in b['stock']),100,delta=.1)
  self.assertTrue(calc['routing']['blocked'])
 def test_other_completed_week_averages(self):
  for sku,expected in [('SKU-2002',4319),('SKU-2003',3911.25)]:
   self.plan['items'][0]['sku_id']=sku
   self.assertEqual(calculate(case_from(self.plan,self.data),self.data)['items'][0]['weekly'],expected)
 def test_invalid_demand_duplicate_and_period_rejected(self):
  for value in [-1,'NaN','Infinity',1.5]:
   with self.subTest(value=value):
    p=copy.deepcopy(self.plan);p['items'][0]['demand']=value
    with self.assertRaises(ValueError):case_from(p,self.data)
  p=copy.deepcopy(self.plan);p['items'][1]['sku_id']='SKU-1001'
  with self.assertRaises(ValueError):case_from(p,self.data)
  p=copy.deepcopy(self.plan);p['items'][0]['end']='2026-07-12'
  with self.assertRaises(ValueError):case_from(p,self.data)
 def test_missing_performance_creates_task_only_after_human_submission(self):
  c=case_from(self.plan,self.data)
  self.assertEqual(tasks(c),[])
  c['marketing_stage']='SCM 검토 요청'
  self.assertEqual({t['role'] for t in tasks(c)},{'SCM','마케팅'})
  self.assertTrue(any(t['key']=='marketing:performance' for t in tasks(c)))
 def test_plan_is_never_an_approval_or_payment(self):
  c=case_from(self.plan,self.data);c.update(status='접수',replies=[])
  with self.assertRaises(ValueError):transition(c,'request','SCM',calculate(c,self.data))
  c['financial_assessment']={'payment_date':'2026-07-27','amount':900,'change':'추가발주'}
  self.assertTrue(calculate(c,self.data)['routing']['blocked'])
 def test_packet_has_policy_sources_and_per_product_results_without_mutation(self):
  c=case_from(self.plan,self.data);before=copy.deepcopy(c)
  result=generate(c,calculate(c,self.data))
  self.assertEqual(c,before)
  self.assertEqual(result['packet']['project_policy']['id'],PROJECT_POLICY['id'])
  self.assertEqual(len(result['packet']['product_results']),2)
  self.assertIn('source',result['packet']['evidence_sources']['sales'])
  self.assertFalse(result['packet']['auto_approved'])
  self.assertEqual(result['packet']['suggested_state'],'SCM 재고·입고표 대조 요청')
 def test_supply_for_other_sku_is_not_double_counted(self):
  c=case_from(self.plan,self.data)
  po=next(r for r in self.data['purchase']['rows'] if r['sku_id']=='SKU-2001')
  reply={'role':'SCM','result':'확인','message':'모의 확인','po_id':po['po_id'],'qty':100,'available_date':'2026-07-10','confirmed':True}
  validate_reply(reply,c,self.data);c['replies']=[reply]
  a,b=calculate(c,self.data)['items']
  self.assertEqual(sum(x['inflow'] for x in a['stock']),0)
  self.assertEqual(sum(x['inflow'] for x in b['stock']),100)

if __name__=='__main__':unittest.main()
