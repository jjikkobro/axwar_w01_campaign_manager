import copy,json,unittest
from pathlib import Path
from app.execution import apply,projection,packet_key
from app.marketing import case_from
from app.scm import basis as scm_basis
from app.finance_review import basis,validate
from app.finance import DEFAULT_FINANCE
import tests.test_marketing as marketing_tests
class ExecutionTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads(Path('data/seed.json').read_text());self.config={**copy.deepcopy(DEFAULT_FINANCE),'version':1,'confirmed':True}
  m=marketing_tests.MarketingTests();m.setUp();p=m.plan;p.update(budget=5000000,settlement_date='2026-09-21',end='2026-07-19');p['items']=[{**p['items'][0],'sku_id':'SKU-2002','demand':100}]
  self.b=case_from(p,self.data);self.b.update(status='검토 중',marketing_stage='재무 검토 요청')
  self.b['scm']={'review':{'valid':True,'basis':scm_basis(self.b,self.data),'items':[]}}
  raw={k:'담당 근거' for k in ['decision_maker','reason','evidence','opinion','alternatives','performance_basis']};raw.update(requests=[],targets=[{'id':'campaign','kind':'캠페인집행','change':'신규 계약','basis':'단독 기안','cash_scope':'표본·현금 합산 제외','proposal_total':5000000,'payments':[{'date':'2026-09-21','amount':5000000}]}])
  r=validate(raw,self.b,self.data);r.update(operation='submit',basis=basis(self.b,self.data,self.config));self.b['finance_review']=r
  self.meta={'decision_maker':'승인 담당','reason':'검토','evidence':'모의 근거','case_id':'test-case'}
 def runop(self,op,role='승인권자',**kw):
  self.b,event=apply(self.b,self.data,self.config,{**self.meta,'operation':op,**kw},role);return event
 def decide(self,d='승인',**kw):return self.runop('decide',authority='마케팅팀 전결',decisions=[{'id':'campaign','decision':d,'condition':'확인 조건' if d=='조건부 승인' else ''}],**kw)
 def with_po(self,ceo=False):
  self.b['scm']['review']['items']=[{'sku_id':'SKU-2002','procurement':'신규 발주 검토'}]
  r=copy.deepcopy(self.b['finance_review']);date='2026-07-27' if ceo else '2026-09-21';r['targets'][0]['payments'][0]['date']=date
  r['targets'].append({'id':'po-SKU-2002','kind':'재고발주','change':'추가발주','sku_id':'SKU-2002','basis':'확인 발주안','cash_scope':'전사 현금 반영 확인','payments':[{'date':date,'amount':201600000}]})
  r=validate(r,self.b,self.data);r.update(operation='submit',basis=basis(self.b,self.data,self.config));self.b['finance_review']=r
 def test_single_campaign_decision_record(self):
  event=self.runop('campaign_decide',authority='마케팅팀 전결',decision='승인')
  self.assertEqual(event['operation'],'campaign_decide');self.assertEqual(self.b['execution']['campaign_reviews']['마케팅팀 전결']['decision'],'승인');self.assertTrue(projection(self.b,self.data,self.config)['targets'][0]['current'])
 def test_campaign_decision_cannot_cross_authorities(self):
  self.with_po();self.runop('campaign_decide',authority='마케팅팀 전결',decision='승인',decisions=[{'id':'po-SKU-2002','decision':'승인'}])
  self.assertNotIn('po-SKU-2002',self.b['execution']['decisions']);self.assertFalse(next(t for t in projection(self.b,self.data,self.config)['targets'] if t['kind']=='재고발주')['current'])
  self.runop('campaign_decide',authority='SCM 전결',decision='승인');self.assertEqual(projection(self.b,self.data,self.config)['stage'],5)
 def test_ceo_campaign_decision_covers_its_approved_scope_once(self):
  self.with_po(ceo=True);self.runop('campaign_decide',authority='CEO/이사회',decision='승인')
  self.assertEqual(set(self.b['execution']['decisions']),{'campaign','po-SKU-2002'});self.assertEqual(len(self.b['execution']['campaign_reviews']),1)
 def test_approval_with_inventory_shortage_records_risk_and_advances_to_order(self):
  self.data['portfolio']={'rows':[]};next(x for x in self.data['inventory']['rows'] if x['sku_id']=='SKU-2002')['on_hand_qty']='0'
  self.with_po(ceo=True);self.b['scm']['review']['basis']=scm_basis(self.b,self.data);self.b['finance_review']['basis']=basis(self.b,self.data,self.config)
  self.runop('campaign_decide',authority='CEO/이사회',decision='승인')
  decision=self.b['execution']['decisions']['campaign'];self.assertLess(decision['supply_risk']['items'][0]['campaign_min'],0)
  self.assertEqual(projection(self.b,self.data,self.config)['stage'],5);self.assertFalse(self.b['execution'].get('orders'));self.assertEqual(self.b['execution']['reservation']['status'],'active')
 def test_campaign_decision_keeps_role_condition_and_stale_guards(self):
  with self.assertRaises(ValueError):self.runop('campaign_decide','SCM',authority='마케팅팀 전결',decision='승인')
  with self.assertRaises(ValueError):self.runop('campaign_decide',authority='CEO/이사회',decision='승인')
  with self.assertRaises(ValueError):self.runop('campaign_decide',authority='마케팅팀 전결',decision='조건부 승인',condition='')
  self.config['version']+=1
  with self.assertRaises(ValueError):self.runop('campaign_decide',authority='마케팅팀 전결',decision='승인')
 def test_decision_does_not_invalidate_own_packet(self):
  key=packet_key(self.b,self.data,self.config);self.decide();self.assertEqual(key,packet_key(self.b,self.data,self.config));self.assertTrue(projection(self.b,self.data,self.config)['targets'][0]['current'])
 def test_changed_source_invalidates_decision(self):
  self.decide();self.config['version']=2;self.assertFalse(projection(self.b,self.data,self.config)['targets'][0]['current'])
 def test_wrong_role_and_authority_rejected(self):
  for role,authority in [('SCM','마케팅팀 전결'),('승인권자','CEO/이사회')]:
   with self.assertRaises(ValueError):self.runop('decide',role,authority=authority,decisions=[{'id':'campaign','decision':'승인'}])
 def test_self_approval_rejected(self):
  self.meta['decision_maker']=self.b['marketing']['author']
  with self.assertRaises(ValueError):self.decide()
 def test_conditional_requires_fulfilment_evidence(self):
  self.decide('조건부 승인')
  with self.assertRaises(ValueError):self.decide()
  self.decide(condition_evidence='조건 충족 회신 모의 확인');self.assertEqual(projection(self.b,self.data,self.config)['stage'],6);self.runop('confirm_supply','SCM',mode='stock_only');self.assertEqual(projection(self.b,self.data,self.config)['stage'],7)
 def test_unknown_target_duplicate_and_invalid_decision_rejected(self):
  for ds in [[{'id':'bad','decision':'승인'}],[{'id':'campaign','decision':'자동승인'}],[{'id':'campaign','decision':'승인'}]*2]:
   with self.assertRaises(ValueError):self.runop('decide',authority='마케팅팀 전결',decisions=ds)
 def test_expired_packet_blocks_approval(self):
  self.b['marketing']['budget']=5000001
  with self.assertRaises(ValueError):self.decide()
 def test_approval_no_po_requires_explicit_scm_supply_check(self):
  self.decide();self.assertEqual(projection(self.b,self.data,self.config)['stage'],6)
  with self.assertRaises(ValueError):self.runop('close','마케팅',notified=True,start='2026-07-13',end='2026-07-19',budget=5000000,sku_ids=['SKU-2002'])
  self.runop('confirm_supply','SCM',mode='stock_only');self.assertEqual(projection(self.b,self.data,self.config)['stage'],7);self.assertNotIn('receipt',self.b['execution']);self.assertEqual(self.b['execution']['supply_review']['mode'],'stock_only')
 def test_supply_check_requires_role_approval_and_real_evidence(self):
  with self.assertRaises(ValueError):self.runop('confirm_supply','SCM',mode='stock_only')
  self.decide()
  with self.assertRaises(ValueError):self.runop('confirm_supply','재무',mode='stock_only')
  with self.assertRaises(ValueError):self.runop('confirm_supply','SCM',mode='confirmed_po')
  self.runop('confirm_supply','SCM',mode='stock_only');self.config['version']+=1;self.assertNotEqual(projection(self.b,self.data,self.config)['stage'],7)
 def test_new_po_cannot_skip_supplier_receipt_with_stock_check(self):
  self.with_po();self.runop('campaign_decide',authority='마케팅팀 전결',decision='승인');self.runop('campaign_decide',authority='SCM 전결',decision='승인')
  with self.assertRaises(ValueError):self.runop('confirm_supply','SCM',mode='stock_only')
 def test_order_requires_receipt_before_schedule_cleanup(self):
  self.with_po();self.b['scm']['review']['items'][0].update(requested_qty=16000,requested_unit_price=12600)
  self.b['scm']['review']['basis']=scm_basis(self.b,self.data);self.b['finance_review']['basis']=basis(self.b,self.data,self.config)
  for authority in ['마케팅팀 전결','SCM 전결']:self.runop('campaign_decide',authority=authority,decision='승인')
  self.runop('order','SCM',lines=[{'target_id':'po-SKU-2002','qty':16000,'payment_date':'2026-09-21','order_date':'2026-07-01','wanted_date':'2026-08-26','reply_deadline':'2026-07-06','channel':'mail'}])
  self.assertEqual(projection(self.b,self.data,self.config)['stage'],6)
  with self.assertRaisesRegex(ValueError,'공급 회신'):self.runop('close','마케팅',notified=True)
  po=self.b['execution']['orders'][0]
  self.runop('receipt','SCM',lines=[{'po_id':po['po_id'],'payment_date':'2026-09-21','shipments':[{'available_date':'2026-08-26','qty':16000}]}],message='모의 공급 회신 확인',judgment='승인 조건 일치')
  self.assertEqual(projection(self.b,self.data,self.config)['stage'],7)
 def test_unsent_receipt_rejected(self):
  with self.assertRaises(ValueError):self.runop('receipt','SCM',lines=[])
 def test_close_requires_approval_and_notification(self):
  with self.assertRaises(ValueError):self.runop('close','마케팅',notified=True)
  self.decide();self.runop('confirm_supply','SCM',mode='stock_only')
  with self.assertRaisesRegex(ValueError,'통보'):self.runop('close','마케팅',notified=False)
 def test_period_change_cannot_be_closed_without_resubmission(self):
  self.decide();self.runop('confirm_supply','SCM',mode='stock_only')
  with self.assertRaises(ValueError):self.runop('close','마케팅',start='2026-07-14',end='2026-07-19',budget=5000000,sku_ids=['SKU-2002'],notified=True)
 def test_rework_requires_rejection_and_notification(self):
  with self.assertRaises(ValueError):self.runop('rework','마케팅',notified=True)
  self.decide('반려')
  with self.assertRaises(ValueError):self.runop('rework','마케팅',notified=False)
  self.runop('rework','마케팅',notified=True);self.assertEqual(projection(self.b,self.data,self.config)['stage'],1)
 def test_close_and_no_further_mutation(self):
  self.decide();self.runop('confirm_supply','SCM',mode='stock_only');self.runop('close','마케팅',start='2026-07-13',end='2026-07-19',budget=5000000,sku_ids=['SKU-2002'],notified=True)
  self.assertTrue(self.b['execution']['closed'])
  with self.assertRaises(ValueError):self.runop('note','마케팅')
 def test_note_does_not_grant_approval(self):
  before=packet_key(self.b,self.data,self.config);self.runop('note','SCM');self.assertEqual(before,packet_key(self.b,self.data,self.config));self.assertNotIn('decisions',self.b['execution'])
 def test_optional_sku_does_not_fabricate_a_demand(self):
  from app.domain import calculate
  p=copy.deepcopy(self.b['marketing']);p['items']=[]
  b=case_from(p,self.data);calc=calculate(b,self.data,self.config)
  self.assertEqual(b['marketing']['items'],[]);self.assertEqual(calc['items'],[])
  from app.scm import can_handoff
  with self.assertRaises(ValueError):can_handoff({'direction':'재고로 가능','items':[],'requests':[]},{'items':[]})
 def test_inquiry_is_owned_and_does_not_auto_answer(self):
  self.runop('note','SCM',to_role='재무')
  with self.assertRaises(ValueError):self.runop('answer','마케팅',index=0)
  self.runop('answer','재무',index=0);self.assertIn('answer',self.b['execution']['notes'][0])
 def test_container_performance_snapshot_matches_source(self):
  from app.performance import sample
  snapshot=json.loads(Path('data/performance_reference.json').read_text())
  self.assertEqual(snapshot,sample())
if __name__=='__main__':unittest.main()
