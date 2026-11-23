import copy,json,unittest
from pathlib import Path
from app.marketing import case_from
from app.domain import calculate
from app import scm

class ScmTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads(Path('data/seed.json').read_text())
  for d in self.data.values():d['version']=1
  p={'title':'SCM 검토','author':'마케팅','department':'마케팅','purpose':'원본 대조','as_of':'2026-07-01','written_date':'2026-07-01','start':'2026-07-13','end':'2026-07-19','performance_unknown_reason':'확인 필요','items':[{'sku_id':'SKU-2002','demand':1000,'unit':'EA/주','start':'2026-07-13','end':'2026-07-19','basis':'설명용 가정','confidence':'미확인','overlap':'기존 판매 제외한 순증'}]}
  self.case=case_from(p,self.data);self.case.update(marketing_stage='SCM 검토 요청',status='접수',replies=[],approval=None)
  self.review={'decision_maker':'SCM 담당','reason':'자료 대조','evidence':'원본 + 모의 회신','alternatives':'수량·일정 협의','direction':'재고로 가능','items':[{'sku_id':'SKU-2002','supply_result':'가능','procurement':'추가 조달 없음','reference_po':'SPO-0006'}],'requests':[]}
 def receipt(self,**overrides):
  raw={'po_id':'SPO-0006','status':'확인','qty':100,'available_date':'2026-07-10','decision_maker':'SCM 담당','reason':'잔여 수량 확인','evidence':'모의 공급 회신','provenance':'모의 회신',**overrides}
  r=scm.validate_receipt(raw,self.case,self.data);self.case.setdefault('scm',{}).setdefault('receipts',{})['SPO-0006']=r
  return r
 def test_review_reason_optional_but_actor_and_evidence_required(self):
  raw={**self.review,'reason':''};r=scm.validate_review(raw,self.case,self.data)
  self.assertEqual(r['reason'],'')
  for field in ['decision_maker','evidence']:
   with self.subTest(field=field):
    with self.assertRaises(ValueError):scm.validate_review({**raw,field:''},self.case,self.data)
 def test_receipt_reason_still_required(self):
  with self.assertRaises(ValueError):self.receipt(reason='')
 def test_period_supply_and_cover_are_distinct(self):
  x=scm.analysis(self.case,self.data)['items'][0]
  self.assertEqual(x['weekly'],4319);self.assertEqual(x['campaign_end_stock'],6659)
  self.assertEqual(x['simple_cover'],3.64);self.assertIsNone(x['first_short_through_campaign'])
  self.assertEqual(x['first_short_horizon'],'2026-07-30')
 def test_order_formula_subtracts_transit_and_moq_is_not_a_multiple(self):
  self.review['items'][0].update(target_qty=40000,target_basis='가정 목표')
  r=scm.validate_review(self.review,self.case,self.data);x=scm.analysis(self.case,self.data,review=r)['items'][0]['procurement']
  self.assertEqual(x['raw_suggested_qty'],19529);self.assertEqual(x['moq_qty'],19529)
  r['items'][0]['target_qty']=19000
  self.assertEqual(scm.analysis(self.case,self.data,review=r)['items'][0]['procurement']['moq_qty'],0)
 def test_missing_target_price_and_payment_remain_unknown(self):
  x=scm.analysis(self.case,self.data)['items'][0]['procurement']
  for k in ['target_qty','moq_qty','estimated_amount','requested_payment_date','lead_time_arrival_assumption']:self.assertIsNone(x[k])
 def test_confirmed_receipt_is_used_once_and_in_transit_is_not_added(self):
  self.receipt();x=scm.analysis(self.case,self.data)['items'][0]
  self.assertEqual(sum(d['inflow'] for d in x['stock']),100)
  self.assertEqual(x['campaign_end_stock'],6759)
 def test_unknown_or_impossible_reply_never_adds_supply(self):
  for status in ['미확인','불가']:
   self.receipt(status=status)
   self.assertEqual(sum(d['inflow'] for d in scm.analysis(self.case,self.data)['items'][0]['stock']),0)
 def test_stale_purchase_receipt_not_applied(self):
  self.receipt();next(p for p in self.data['purchase']['rows'] if p['po_id']=='SPO-0006')['order_qty']='17000'
  self.assertEqual(sum(d['inflow'] for d in scm.analysis(self.case,self.data)['items'][0]['stock']),0)
 def test_receipt_rejects_invalid_date_qty_or_unrelated_po(self):
  for values in [{'qty':16001},{'available_date':''},{'receipt_date':'2026-07-12','available_date':'2026-07-10'},{'po_id':'SPO-0001'}]:
   with self.subTest(values=values),self.assertRaises(ValueError):self.receipt(**values)
 def test_new_procurement_availability_does_not_become_actual_supply(self):
  self.review['items'][0].update(procurement='신규 발주 검토',target_qty=50000,target_basis='시나리오',planned_order_date='2026-07-01',proposed_available_date='2026-07-10')
  r=scm.validate_review(self.review,self.case,self.data);x=scm.analysis(self.case,self.data,review=r)['items'][0]
  self.assertEqual(sum(d['inflow'] for d in x['stock']),0)
  self.assertEqual(x['procurement']['lead_time_arrival_assumption'],'2026-08-26')
  self.assertIsNone(x['procurement']['requested_payment_date'])
 def test_handoff_is_not_approval_and_missing_payment_creates_finance_task(self):
  self.review['direction']='추가 발주 필요';self.review['items'][0].update(procurement='신규 발주 검토',target_qty=22000,target_basis='목표 4주 가정',requested_qty=16000,requested_unit_price=12600)
  r=scm.validate_review(self.review,self.case,self.data);a=scm.analysis(self.case,self.data,review=r);scm.can_handoff(r,a)
  r.update(valid=True,basis=scm.basis(self.case,self.data));self.case['scm']={'review':r};self.case['marketing_stage']='재무 검토 요청'
  self.assertTrue(any(t['role']=='재무' and '유출일' in t['title'] for t in scm.task_specs(self.case)))
  self.assertIsNone(scm.packet(self.case,r,a)['approval'])
  self.assertTrue(calculate(self.case,self.data)['routing']['blocked'])
 def test_new_order_handoff_requires_quantity_and_unit_price(self):
  self.review['direction']='추가 발주 필요';self.review['items'][0].update(procurement='신규 발주 검토',requested_qty=16000,requested_unit_price=None)
  r=scm.validate_review(self.review,self.case,self.data)
  with self.assertRaisesRegex(ValueError,'수량과 예상 단가'):scm.can_handoff(r,scm.analysis(self.case,self.data,review=r))
 def test_critical_request_and_unconfirmed_supply_block_handoff(self):
  self.review['requests']=[{'id':'q1','question':'납기 확인','blocking':True,'status':'대기'}]
  r=scm.validate_review(self.review,self.case,self.data)
  with self.assertRaises(ValueError):scm.can_handoff(r,scm.analysis(self.case,self.data,review=r))
  self.review['requests']=[];self.review['items'][0]['supply_result']='미확인'
  r=scm.validate_review(self.review,self.case,self.data)
  with self.assertRaises(ValueError):scm.can_handoff(r,scm.analysis(self.case,self.data,review=r))
 def test_shortage_cannot_be_marked_possible_just_by_proposed_new_order(self):
  self.case['marketing']['items'][0]['total_quantity']=50000
  r=scm.validate_review(self.review,self.case,self.data)
  with self.assertRaises(ValueError):scm.can_handoff(r,scm.analysis(self.case,self.data,review=r))
 def test_metadata_and_numeric_validation(self):
  for val in ['NaN',-1,1.5]:
   self.review['items'][0]['target_qty']=val
   with self.assertRaises(ValueError):scm.validate_review(self.review,self.case,self.data)
  self.review['items'][0].pop('target_qty');self.review['decision_maker']=''
  with self.assertRaises(ValueError):scm.validate_review(self.review,self.case,self.data)
 def test_basis_change_invalidates_handoff_and_preserves_receipts(self):
  self.receipt();r=scm.validate_review(self.review,self.case,self.data);r.update(valid=True,basis=scm.basis(self.case,self.data))
  self.case['scm']['review']=r;self.case['scm']['finance_packet']={};self.case['marketing_stage']='재무 검토 요청'
  self.data['inventory']['version']=2
  self.assertTrue(scm.stale(self.case,self.data));scm.invalidate(self.case,'재고 변경')
  self.assertFalse(r['valid']);self.assertEqual(self.case['marketing_stage'],'SCM 재검토 필요')
  self.assertIn('SPO-0006',self.case['scm']['receipts']);self.assertNotIn('finance_packet',self.case['scm'])
 def test_unanswered_po_request_cannot_be_closed_or_dropped(self):
  q={'id':'q1','po_id':'SPO-0006','question':'판매가능일 확인','blocking':True,'status':'완료','answer':'미확인','evidence':'모의 회신'}
  self.review['requests']=[q]
  with self.assertRaises(ValueError):scm.validate_review(self.review,self.case,self.data)
  q['status']='대기';r=scm.validate_review(self.review,self.case,self.data);r['basis']=scm.basis(self.case,self.data);self.case['scm']={'review':r}
  self.review['requests']=[]
  with self.assertRaises(ValueError):scm.validate_review(self.review,self.case,self.data)

if __name__=='__main__':unittest.main()
