import copy,json,unittest
from pathlib import Path
from app.domain import calculate,parse_dataset,transition,validate_reply

class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads(Path('data/seed.json').read_text())
  self.case={'title':'테스트 캠페인','sku_id':'SKU-1001','as_of':'2026-07-01','start':'2026-07-13','end':'2026-07-19','quantity':12000,'evidence':'교육용 가정','demand_status':'가정','status':'검토 중','replies':[]}
 def test_original_demand_and_cash(self):
  r=calculate(self.case,self.data)
  self.assertEqual(r['weekly'],8320.75)
  self.assertNotIn('2026-06-29',r['weeks'])
  self.assertEqual(r['first_breach'],'2026-07-21')
  self.assertEqual(r['cash'][14]['closing'],1737574844)
 def test_in_transit_not_added_without_reply(self):
  r=calculate(self.case,self.data)
  self.assertEqual(sum(x['inflow'] for x in r['stock']),0)
 def test_supply_revision_replaces_old_reply(self):
  self.case['replies']=[{'role':'SCM','po_id':'SPO-0001','qty':15821,'available_date':'2026-07-15','result':'확인','confirmed':True},{'role':'SCM','po_id':'SPO-0001','qty':15821,'available_date':'2026-07-22','result':'확인','confirmed':True}]
  r=calculate(self.case,self.data)
  self.assertEqual(sum(x['inflow'] for x in r['stock']),15821)
  self.assertEqual(next(x['date'] for x in r['stock'] if x['inflow']),'2026-07-22')
 def test_amount_is_incremental_and_changes_authority(self):
  self.case['requested_payment_date']='2026-07-21'
  self.case['requested_amount']=1000000
  r=calculate(self.case,self.data)
  self.assertEqual(r['authority'],'CEO/이사회')
  self.assertTrue(r['routing']['blocked'])
 def test_partial_or_missing_replies_block_submission(self):
  with self.assertRaises(ValueError):transition(self.case,'submit','SCM',calculate(self.case,self.data))
 def test_wrong_role_cannot_approve(self):
  self.case['status']='승인 대기'
  with self.assertRaises(ValueError):transition(self.case,'approve','마케팅',calculate(self.case,self.data))
 def test_completion_requires_after_order_reply(self):
  self.case['status']='발주 전달'
  with self.assertRaises(ValueError):transition(self.case,'complete','SCM',calculate(self.case,self.data))
 def test_supply_cannot_exceed_purchase(self):
  with self.assertRaises(ValueError):validate_reply({'role':'SCM','message':'확약','result':'확인','po_id':'SPO-0001','qty':24001,'available_date':'2026-07-15'},self.case,self.data)
 def test_invalid_upload_is_rejected(self):
  for val in ['-1','NaN','Infinity','1.1']:
   with self.assertRaises(ValueError):parse_dataset('cash','date|closing_balance\n2026-06-30|'+val)
 def test_duplicate_records_rejected(self):
  with self.assertRaises(ValueError):parse_dataset('cash','date|closing_balance\n2026-06-30|1\n2026-06-30|2')

if __name__=='__main__':unittest.main()
