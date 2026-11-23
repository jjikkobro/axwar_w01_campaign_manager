import copy,json,unittest
from pathlib import Path
from app.finance import cash_bundle,routing,task_specs,DEFAULT_FINANCE,validate_commitment
from app.domain import calculate,transition
from app.domain import validate_case
from app.drafts import generate

class FinanceTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads(Path('data/seed.json').read_text())
  self.config=copy.deepcopy(DEFAULT_FINANCE)
  self.bundle=cash_bundle(self.data,self.config)
  self.case={'title':'발주 검토','sku_id':'SKU-1001','as_of':'2026-07-01','start':'2026-07-13','end':'2026-07-19','quantity':6000,'evidence':'참가자 가정','demand_status':'가정','approval_type':'재고발주','status':'검토 중','replies':[],'requested_payment_date':'2026-08-25','requested_amount':1000000}
 def confirm(self,sid='exclude_pay'):
  self.config.update(confirmed=True,selected=sid)
  return cash_bundle(self.data,self.config)
 def assess(self,**fields):
  self.case['financial_assessment']={'change':'추가발주','amount':1000000,'payment_date':'2026-08-25','reason':'검증',**fields}
 def test_fixed_original_amounts(self):
  self.assertEqual(self.bundle['opening'],5148063540)
  self.assertEqual(self.bundle['purchase_total'],3749760000)
  self.assertEqual(self.bundle['double_counted_ap'],0)
  self.assertEqual(self.bundle['linked_ap_excluded'],14)
  self.assertEqual(self.bundle['ar_overdue_total'],180171155)
  self.assertEqual(self.bundle['ap_overdue_total'],454175115)
 def test_four_scenario_golden_values(self):
  for sid,minimum,last in [('collect_pay',1647835595,'2026-08-21'),('collect_exclude',2102010710,'2026-08-21'),('exclude_pay',1467664440,'2026-08-28'),('exclude_exclude',1921839555,'2026-08-21')]:
   s=self.bundle['scenarios'][sid]
   self.assertEqual((s['cash_min'],s['first_breach'],s['last_breach']),(minimum,'2026-07-21',last),sid)
  self.assertEqual((self.bundle['union_breach_dates'][0],self.bundle['union_breach_dates'][-1]),('2026-07-21','2026-08-28'))
 def test_unconfirmed_uses_union_and_blocks(self):
  self.assess();r=routing(self.case,self.bundle)
  self.assertEqual(r['status'],'CEO 상신 대상(재무 확정 대기)')
  self.assertTrue(r['blocked'])
 def test_reclassification_changes_and_retains_routes(self):
  self.assess();self.assertEqual(routing(self.case,self.confirm())['authority'],'CEO/이사회')
  self.assertEqual(routing(self.case,self.confirm('collect_pay'))['authority'],'SCM 전결')
  self.assess(payment_date='2026-07-21')
  self.assertEqual(routing(self.case,self.confirm('collect_pay'))['authority'],'CEO/이사회')
 def test_missing_date_never_defaults_to_normal(self):
  self.case['requested_payment_date']=None
  r=routing(self.case,self.confirm())
  self.assertEqual(r['status'],'판정 불가');self.assertTrue(r['blocked'])
  self.assertIn('payment',[t['key'] for t in task_specs(self.case,self.bundle)])
 def test_overdue_tasks_are_individual(self):
  tasks=task_specs(None,self.bundle)
  self.assertEqual(len(tasks),10);self.assertEqual(len({t['key'] for t in tasks}),10)
 def test_confirmed_reply_recalculates_without_altering_original(self):
  original=copy.deepcopy(self.data)
  for r in self.bundle['overdue']:
   if r['kind']=='ar':self.config['overrides'][r['id']]={'date':'2026-07-01','provenance':'모의 회신'}
  b=cash_bundle(self.data,self.config)
  self.assertEqual(b['scenarios']['exclude_pay']['cash_min'],1647835595)
  self.assertEqual(b['scenarios']['exclude_pay']['last_breach'],'2026-08-21')
  self.assertEqual(len(task_specs(None,b)),4);self.assertEqual(self.data,original)
 def test_weekend_dates_are_separate(self):
  self.config['weekend_shift']=True
  b=cash_bundle(self.data,self.config)
  r=next(x for x in b['scenarios']['exclude_pay']['schedule'] if x['id']=='ar:MAR-0004')
  self.assertEqual((r['original_date'],r['adjusted_date']),('2026-08-23','2026-08-24'))
 def test_existing_order_is_cause_not_new_commitment(self):
  self.assess(change='기존 약정',payment_date='2026-07-21',amount=524160000)
  r=routing(self.case,self.confirm());self.assertEqual(r['authority'],'SCM 전결');self.assertFalse(r['new_commitment'])
 def test_reductions_and_deferrals_keep_normal_route(self):
  for change in ['감량','지급일 연기','취소']:
   self.assess(change=change,payment_date='2026-07-21')
   self.assertEqual(routing(self.case,self.confirm())['authority'],'SCM 전결')
 def test_campaign_bundle_and_annual_thresholds(self):
  self.assess(payment_date='2026-09-21',amount=9016502)
  self.case.update(approval_type='캠페인집행',proposal_total=180803272)
  self.assertEqual(routing(self.case,self.confirm())['authority'],'Masil 대표 승인 + 그룹 보고')
  self.case['proposal_total']=100000000
  self.assertEqual(routing(self.case,self.confirm())['authority'],'마케팅팀 전결')
  self.case.update(approval_type='연간전속계약',annual_amount=1000000001)
  self.assertEqual(routing(self.case,self.confirm())['authority'],'CEO/이사회')
 def test_early_deadline_creates_ad_hoc_task(self):
  self.case['contract_deadline']='2026-07-03'
  task=next(t for t in task_specs(self.case,self.bundle) if t['key']=='forecast')
  self.assertTrue(task['urgent']);self.assertEqual(task['due'],'2026-07-03')
 def test_forecast_comparison_is_labelled_claim(self):
  rows=self.bundle['scenarios']['exclude_pay']['weekly']
  self.assertEqual(rows[0]['official_provenance'],'부서 주장')
  self.assertEqual(rows[0]['difference'],rows[0]['recalculated']-rows[0]['official'])
 def test_no_automatic_approval_from_draft(self):
  before=copy.deepcopy(self.case)
  result=generate(self.case,calculate(self.case,self.data))
  self.assertFalse(result['packet']['auto_approved']);self.assertEqual(self.case,before)
 def test_unknown_finance_blocks_approval(self):
  self.case.update(status='승인 대기',decision_note='검토',approval_scope='SCM 전결')
  with self.assertRaises(ValueError):transition(self.case,'approve','승인권자',calculate(self.case,self.data))
 def test_requester_cannot_inject_finance_or_approval(self):
  malicious={**self.case,'financial_assessment':{'change':'기존 약정'},'approval':{'scope':'CEO/이사회'},'status':'승인','routing':{'blocked':False}}
  valid=validate_case(malicious)
  for key in ['financial_assessment','approval','status','routing']:self.assertNotIn(key,valid)
 def test_cannot_disguise_earlier_payment_as_deferral(self):
  a={'change':'지급일 연기','reference_po':'SPO-0001','amount':524160000,'payment_date':'2026-07-10'}
  with self.assertRaises(ValueError):validate_commitment(a,self.data['purchase']['rows'],'SKU-1001')
 def test_cannot_disguise_increased_amount_as_reduction(self):
  a={'change':'감량','reference_po':'SPO-0001','amount':600000000,'payment_date':'2026-07-21'}
  with self.assertRaises(ValueError):validate_commitment(a,self.data['purchase']['rows'],'SKU-1001')
 def test_cancellation_requires_zero_remaining_payment(self):
  a={'change':'취소','reference_po':'SPO-0001','amount':1000000,'payment_date':'2026-07-21'}
  with self.assertRaises(ValueError):validate_commitment(a,self.data['purchase']['rows'],'SKU-1001')
 def test_new_po_cannot_be_classified_as_original_contract(self):
  fake={'po_id':'NEW-0001','sku_id':'SKU-1001','amount_krw':'100','payment_due_date':'2026-07-21'}
  a={'change':'기존 약정','reference_po':'NEW-0001','amount':100,'payment_date':'2026-07-21'}
  with self.assertRaises(ValueError):validate_commitment(a,[fake],'SKU-1001')

if __name__=='__main__':unittest.main()
