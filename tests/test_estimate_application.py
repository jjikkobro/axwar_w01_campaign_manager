import copy,unittest
import tests.test_execution as fixture
from app.ax_planning import preview,attach,confirm
from app.marketing import case_from
from app.execution import apply,projection,operational_schedule
from app.finance_review import initial_review,validate,basis
class EstimateApplicationTests(unittest.TestCase):
 def setUp(self):
  f=fixture.ExecutionTests();f.setUp();self.data=f.data;self.data['portfolio']={'rows':[]};self.config=f.config;self.meta={'decision_maker':'확인 담당','reason':'담당 부서 확인','evidence':'별도 검증 근거','case_id':'estimate-case'}
  p=copy.deepcopy(f.b['marketing']);p.update(submission_mode='estimate_only',settlement_date=None,contract_deadline=None);p['items'][0].update(unit='EA/주',demand=100)
  self.b=case_from(p,self.data);self.b.update(_case_id='estimate-case',marketing_stage='SCM 검토 요청');self.inputs={'mode':'estimate_only','as_of':p['as_of'],'start':p['start'],'end':p['end'],'budget':p['budget'],'items':[{'sku_id':'SKU-2002','demand_mode':'manual','demand':100,'qty_mode':'manual','qty':16000,'price_mode':'manual','unit_price':12600}]};self.b['ax_plan']=attach(self.b,self.inputs,self.data,self.config,'estimate-case')
 def op(self,name,role,**kw):self.b,_=apply(self.b,self.data,self.config,{**self.meta,'operation':name,**kw},role)
 def finance(self):
  self.b,_=confirm(self.b,self.data,self.config,self.meta,'SCM');r=initial_review(self.b)
  for t in r['targets']:
   for p in t['payments']:p['date']='2026-09-21'
   t['cash_scope']='전사 현금 반영 확인' if t['kind']=='재고발주' else '표본·현금 합산 제외'
  r.update(**{k:self.meta[k] for k in ['decision_maker','reason','evidence']},opinion='계획 유출일·현금 검토 완료',alternatives='변경 시 재판정',performance_basis='성과는 미확인')
  r=validate(r,self.b,self.data);r.update(operation='submit',basis=basis(self.b,self.data,self.config));self.b['finance_review']=r
 def approve_and_order(self):
  self.finance()
  for authority in ['마케팅팀 전결','SCM 전결']:self.op('campaign_decide','승인권자',authority=authority,decision='승인')
  self.op('order','SCM',lines=[{'target_id':'po-SKU-2002','qty':16000,'payment_date':'2026-09-21','order_date':'2026-07-01','wanted_date':'2026-08-26','reply_deadline':'2026-07-06','channel':'mail'}])
 def test_application_accepts_no_marketing_schedule(self):
  self.assertIsNone(self.b['marketing']['settlement_date']);self.assertIsNone(self.b['marketing']['contract_deadline']);raw=copy.deepcopy(self.b['marketing']);raw.update(settlement_date='2026-09-21',contract_deadline='2026-07-10');self.assertIsNone(case_from(raw,self.data)['marketing']['settlement_date']);p=preview(self.inputs,self.data,self.config,'estimate-case');self.assertTrue(p['estimate_ready']);self.assertFalse(p['simple_review_eligible']);self.assertIsNone(p['cash']['minimum_after'])
 def test_scm_can_review_but_unknown_payment_cannot_get_approved(self):
  self.b,_=confirm(self.b,self.data,self.config,self.meta,'SCM');self.assertEqual(projection(self.b,self.data,self.config)['stage'],3)
  with self.assertRaises(ValueError):confirm(self.b,self.data,self.config,self.meta,'재무')
  with self.assertRaises(ValueError):self.op('campaign_decide','승인권자',authority='SCM 전결',decision='승인')
 def test_finance_owns_planned_dates_without_updating_marketing_inputs(self):
  self.finance();self.assertEqual(projection(self.b,self.data,self.config)['stage'],4);self.assertIsNone(self.b['marketing']['settlement_date']);self.assertFalse(operational_schedule(self.b,self.data)['rows'])
 def test_order_and_receipt_populate_read_only_schedule(self):
  self.approve_and_order();r=operational_schedule(self.b,self.data)['rows'][0];self.assertEqual(r['payment_date'],'2026-09-21');self.assertEqual(r['available'],[])
  self.op('receipt','SCM',lines=[{'po_id':r['po_id'],'payment_date':'2026-09-21','shipments':[{'available_date':'2026-08-26','qty':16000}]}],message='모의 공급 회신',judgment='확인')
  r=operational_schedule(self.b,self.data)['rows'][0];self.assertEqual(r['available'][0]['available_date'],'2026-08-26');self.assertEqual(r['payment_basis'],'공급 회신 확인');self.assertIsNone(self.b['marketing']['settlement_date'])
 def test_changed_receipt_does_not_claim_a_confirmed_schedule(self):
  self.approve_and_order();po=self.b['execution']['orders'][0]
  self.op('receipt','SCM',lines=[{'po_id':po['po_id'],'payment_date':'2026-08-25','shipments':[{'available_date':'2026-08-26','qty':16000}]}],message='모의 변경 회신',judgment='재검토')
  r=operational_schedule(self.b,self.data)['rows'][0];self.assertEqual(r['available'],[]);self.assertEqual(r['status'],'변경 회신 재확인 중');self.assertEqual(projection(self.b,self.data,self.config)['stage'],3)
