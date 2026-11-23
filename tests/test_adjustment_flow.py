import copy,unittest
from app import operations,execution
import tests.test_execution as fixture

class AdjustmentFlowTests(unittest.TestCase):
 def setUp(self):
  f=fixture.ExecutionTests();f.setUp();self.case=f.b;self.data=f.data;self.config=f.config
  self.raw={'operation':'adjust_request','target':'SCM','decision_maker':'검토 담당','reason':'수량 재검토','evidence':'SCM 원본 근거'}
 def test_each_recipient_is_routed_and_prior_finance_preserved(self):
  for target,stage,role in [('마케팅',1,'재무'),('SCM',2,'재무'),('재무',3,'승인권자')]:
   with self.subTest(target=target):
    b,event=operations.apply(copy.deepcopy(self.case),self.data,self.config,{**self.raw,'target':target},role,execution.metadata)
    p=execution.projection(b,self.data,self.config);self.assertEqual(p['stage'],stage);self.assertEqual(p['adjustment']['reason'],'수량 재검토');self.assertEqual(p['adjustment']['target'],target)
    self.assertEqual(len(b['finance_review_history']),1);self.assertNotIn('finance_review',b)
    if target in ('마케팅','SCM'):self.assertFalse(b['scm']['review']['valid'])
    else:self.assertTrue(b['scm']['review']['valid'])
    operations.complete_adjustment(b,target,'기록 시간');self.assertIsNone(operations.pending_adjustment(b));self.assertEqual(b['operations']['adjustments'][0]['status'],'처리 완료')
 def test_duplicate_and_self_request_rejected(self):
  b,_=operations.apply(self.case,self.data,self.config,self.raw,'재무',execution.metadata)
  with self.assertRaises(ValueError):operations.apply(b,self.data,self.config,self.raw,'재무',execution.metadata)
  with self.assertRaises(ValueError):operations.apply(self.case,self.data,self.config,self.raw,'SCM',execution.metadata)
 def test_after_order_is_not_silently_changed(self):
  b=copy.deepcopy(self.case);b['execution']={'orders':[{'po_id':'이미 전달'}]}
  with self.assertRaisesRegex(ValueError,'별도 변경 기안'):operations.apply(b,self.data,self.config,self.raw,'재무',execution.metadata)
  self.assertEqual(b['execution']['orders'][0]['po_id'],'이미 전달')
if __name__=='__main__':unittest.main()
