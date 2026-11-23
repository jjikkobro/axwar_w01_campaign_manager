import copy,json,unittest
from pathlib import Path
from app.finance import cash_bundle
from app.marketing import submission_cash_window

class MarketingCashWindowTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.bundle=cash_bundle(json.loads(Path('data/seed.json').read_text()))
 def plan(self):return {'start':'2026-07-13','end':'2026-07-19','settlement_date':None,'settlement_draft':{'date':'2026-08-01'},'budget':0}
 def test_boundary_dates_and_zero_budget_allowed_without_mutation(self):
  p=self.plan();p.update(start='2026-07-01',end='2026-09-28');p['settlement_draft']['date']='2026-09-28';old=copy.deepcopy(p)
  self.assertEqual(submission_cash_window(p,self.bundle)['payment_date'],'2026-09-28');self.assertEqual(p,old)
 def test_each_outside_date_blocked_at_submission(self):
  for key in ['start','end','payment']:
   with self.subTest(key=key):
    p=self.plan()
    if key=='payment':p['settlement_draft']['date']='2026-12-24'
    else:p[key]='2026-11-15'
    with self.assertRaisesRegex(ValueError,'현금 전망 기간'):submission_cash_window(p,self.bundle)
 def test_missing_payment_does_not_become_zero_or_default(self):
  p=self.plan();p['settlement_draft']=None
  with self.assertRaisesRegex(ValueError,'지급예정일을 입력'):submission_cash_window(p,self.bundle)
 def test_confirmed_payment_takes_priority_over_prediction(self):
  p=self.plan();p['settlement_draft']['date']='2027-01-09';p['settlement_date']='2026-08-01'
  self.assertEqual(submission_cash_window(p,self.bundle)['payment_date'],'2026-08-01')
