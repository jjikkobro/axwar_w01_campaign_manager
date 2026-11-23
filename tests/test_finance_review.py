import copy,json,unittest
from pathlib import Path
from app.finance_review import validate,view,basis
from app.finance import DEFAULT_FINANCE

class ReviewTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads(Path('data/seed.json').read_text());self.config={**copy.deepcopy(DEFAULT_FINANCE),'confirmed':True,'version':1};self.case={'title':'검토','sku_id':'SKU-2002','status':'검토 중'}
  self.raw={k:'담당자 근거' for k in ['decision_maker','reason','evidence','opinion','alternatives','performance_basis']}
  self.raw.update(targets=[{'id':'new','kind':'재고발주','change':'추가발주','basis':'확인 견적','cash_scope':'전사 현금 반영 확인','payments':[{'date':'2026-08-21','amount':201600000}]}],requests=[])
 def runview(self):return view(self.case,self.data,self.config,validate(self.raw,self.case,self.data))
 def test_unsaved_plan_provides_preview_targets_without_mutation(self):
  from app.finance_review import initial_review
  self.case['marketing']={'budget':5000000,'settlement_date':'2026-07-27','contract_deadline':'2026-07-10'}
  before=copy.deepcopy(self.case);draft=initial_review(self.case);result=view(self.case,self.data,self.config,draft)
  self.assertEqual(len(result['routes']),1);self.assertEqual(result['routes'][0]['payment']['date'],'2026-07-27');self.assertFalse(result['valid']);self.assertEqual(self.case,before)
 def test_marketing_prediction_prefills_finance_without_confirming_plan(self):
  from app.finance_review import initial_review
  self.case['marketing']={'budget':5000000,'settlement_date':None,'settlement_draft':{'date':'2026-07-27','basis':'과거 지급일 중앙값'}}
  before=copy.deepcopy(self.case);draft=initial_review(self.case);result=view(self.case,self.data,self.config,draft)
  self.assertEqual(draft['targets'][0]['payments'][0]['date'],'2026-07-27');self.assertIn('예측 지급일',draft['targets'][0]['basis']);self.assertNotEqual(result['recommendation']['action'],'지급정보 보완');self.assertFalse(result['valid']);self.assertEqual(self.case,before)
  self.case['marketing']['settlement_date']='2026-09-21'
  self.assertEqual(initial_review(self.case)['targets'][0]['payments'][0]['date'],'2026-09-21')
 def test_preview_po_keeps_missing_payment_date_unknown(self):
  from app.finance_review import initial_review
  self.case['marketing']={'budget':5000000,'settlement_date':'2026-07-27'};self.case['scm']={'review':{'items':[{'sku_id':'SKU-2002','procurement':'신규 발주 검토','requested_qty':16000,'requested_unit_price':12600}]}}
  draft=initial_review(self.case);result=view(self.case,self.data,self.config,draft);po=next(r for r in result['routes'] if r['kind']=='재고발주')
  self.assertIsNone(po['payment']['date']);self.assertEqual(po['route']['status'],'판정 불가');self.assertEqual(po['payment']['amount'],201600000)
 def test_advice_ceo_for_new_commitment_in_cash_breach(self):
  a=self.runview()['recommendation'];self.assertEqual(a['action'],'CEO 승인 요청');self.assertTrue(a['items'][0]['ceo_required']);self.assertFalse(a['auto_approved'])
 def test_advice_scm_for_outside_breach_po(self):
  self.raw['targets'][0]['payments'][0]['date']='2026-09-21';a=self.runview()['recommendation'];self.assertEqual(a['action'],'SCM 발주 승인 요청');self.assertTrue(a['ready_to_request'])
 def test_advice_missing_payment_does_not_guess(self):
  self.raw['targets'][0]['payments'][0]['date']=None;a=self.runview()['recommendation'];self.assertEqual(a['action'],'지급정보 보완');self.assertEqual(a['label'],'발주대금 지급일 확인');self.assertIsNone(a['items'][0]['effective_payment_date']);self.assertFalse(a['ready_to_request'])
 def test_campaign_payment_and_forecast_horizon_are_distinct(self):
  self.case['marketing']={'start':'2026-11-15'};self.case['scm']={'review':{'direction':'추가 발주 필요'}}
  self.raw['targets'][0].update(kind='캠페인집행',proposal_total=51465820,cash_scope='표본·현금 합산 제외',payments=[{'date':None,'amount':51465820}])
  a=self.runview()['recommendation'];self.assertEqual(a['label'],'캠페인 집행비 지급일 확인');self.assertFalse(a['ready_to_request']);self.assertEqual(a['basis']['forecast_end'],'2026-09-28')
  self.assertTrue(any('해당 기간 전망' in x for x in a['why']));self.assertTrue(any('SCM 종합 의견' in x for x in a['why']));self.assertTrue(any('추가 발주 대상 없음' in x for x in a['why']))
  self.raw['targets'][0]['payments'][0]['date']='2026-11-16';a=self.runview()['recommendation'];self.assertEqual(a['label'],'해당 기간 현금 전망 필요');self.assertFalse(a['ready_to_request'])
 def test_outside_forecast_submission_explains_payment_and_required_action(self):
  self.raw['targets'][0].update(kind='캠페인집행',proposal_total=5000000,cash_scope='표본·현금 합산 제외',payments=[{'date':'2026-12-24','amount':5000000}])
  result=self.runview();message=' / '.join(result['errors'])
  self.assertIn('캠페인 집행비',message);self.assertIn('2026-12-24',message);self.assertIn('2026-07-01 ~ 2026-09-28',message);self.assertIn('다시 상신',message);self.assertNotIn('campaign 判',message);self.assertNotIn('campaign 판정 불가',message);self.assertFalse(result['valid'])
 def test_advice_unknown_cash_scope_blocks_ready(self):
  self.raw['targets'][0]['cash_scope']='미확인';a=self.runview()['recommendation'];self.assertEqual(a['action'],'CEO 승인 요청');self.assertFalse(a['ready_to_request']);self.assertTrue(a['blockers'])
 def test_advice_finance_unconfirmed_uses_union(self):
  self.config.update(confirmed=False,selected='collect_pay');self.raw['targets'][0]['payments'][0]['date']='2026-08-26';a=self.runview()['recommendation'];self.assertEqual(a['basis']['selected'],'union');self.assertEqual(a['action'],'CEO 승인 요청');self.assertFalse(a['ready_to_request'])
 def test_advice_supply_impossible_requires_adjustment(self):
  self.case['scm']={'review':{'direction':'공급 불가'}};a=self.runview()['recommendation'];self.assertEqual(a['action'],'공급 조정 우선');self.assertEqual(a['opinion'],'no')
 def test_advice_existing_po_not_new_ceo_request(self):
  self.raw['targets'][0].update(change='기존 약정',reference_po='SPO-0006',sku_id='SKU-2002',payments=[{'date':'2026-07-21','amount':201600000}]);a=self.runview()['recommendation'];self.assertEqual(a['action'],'기존 약정 유지');self.assertFalse(a['items'][0]['ceo_required'])
 def test_advice_campaign_does_not_invent_po(self):
  self.raw['targets'][0].update(kind='캠페인집행',proposal_total=5000000,cash_scope='표본·현금 합산 제외',payments=[{'date':'2026-09-21','amount':5000000}]);a=self.runview()['recommendation'];self.assertEqual(a['action'],'캠페인 승인 요청');self.assertTrue(any('추가 발주 대상 없음' in x for x in a['why']))
 def test_baseline_impact_separate(self):
  s=self.runview()['scenarios']['exclude_pay'];self.assertEqual(s['cash_min'],1467664440);self.assertEqual(s['impact_min'],1266064440)
 def test_missing_dates_and_amounts_block(self):
  self.raw['targets'][0]['payments']=[{'date':None,'amount':None}]
  self.assertTrue(self.runview()['errors']);self.assertEqual(self.runview()['routes'][0]['route']['status'],'판정 불가')
 def test_sample_not_added(self):
  self.raw['targets'][0]['cash_scope']='표본·현금 합산 제외'
  s=self.runview()['scenarios']['exclude_pay'];self.assertEqual(s['cash_min'],s['impact_min'])
 def test_installments_do_not_bypass_campaign_limit(self):
  t=self.raw['targets'][0];t.update(kind='캠페인집행',proposal_total=20000000,payments=[{'date':'2026-09-21','amount':6000000},{'date':'2026-09-22','amount':6000000}])
  self.assertTrue(all(x['route']['authority']=='Masil 대표 승인 + 그룹 보고' for x in self.runview()['routes']))
 def test_existing_po_not_subtracted_twice(self):
  p=self.data['purchase']['rows'][0];t=self.raw['targets'][0];t.update(change='기존 약정',sku_id=p['sku_id'],reference_po=p['po_id'],payments=[{'date':p['payment_due_date'],'amount':p['amount_krw']}]);s=self.runview()['scenarios']['exclude_pay'];self.assertEqual(s['impact_min'],s['cash_min'])
 def test_source_changes_make_saved_review_stale(self):
  r=validate(self.raw,self.case,self.data);r['basis']=basis(self.case,self.data,self.config);self.case['finance_review']=r
  self.assertTrue(view(self.case,self.data,self.config)['valid']);self.config['confirmed']=False;self.assertFalse(view(self.case,self.data,self.config)['valid'])
 def test_week_min_and_friday_differ(self):
  w=self.runview()['scenarios']['exclude_pay']['weekly_min'][1];self.assertNotEqual(w['minimum'],w['recalculated'])
 def test_preview_does_not_mutate_inputs(self):
  before=copy.deepcopy((self.case,self.data,self.config,self.raw));self.runview();self.assertEqual((self.case,self.data,self.config,self.raw),before)
 def test_unknown_scope_and_pending_request_block(self):
  self.raw['targets'][0]['cash_scope']='미확인';self.raw['requests']=[{'role':'SCM','question':'지급일?','answer':''}];self.assertGreaterEqual(len(self.runview()['errors']),2)
 def test_scm_handoff_required(self):
  self.case['marketing']={'influencer_id':'INF-001'};v=self.runview();self.assertIn('② SCM 인계·유효 검토 필요',v['errors']);self.assertEqual(v['related_contract']['annual_fixed_fee'],2800000000)
 def test_sample_performance_reproduces_original_comparison(self):
  from app.performance import sample
  s=sample()['campaigns']['CMP-0003']
  self.assertEqual(s['marketing_spend'],123929733)
  self.assertEqual(s['gmv'],158022526)
  self.assertAlmostEqual(s['contribution'],-30674334.9)
  self.assertEqual((s['rank'],s['rank_population']),(24,25))
 def test_duplicate_existing_po_change_rejected(self):
  p=self.data['purchase']['rows'][0];t=self.raw['targets'][0];t.update(change='기존 약정',sku_id=p['sku_id'],reference_po=p['po_id'],payments=[{'date':p['payment_due_date'],'amount':p['amount_krw']}]);t2=copy.deepcopy(t);t2['id']='duplicate';self.raw['targets'].append(t2)
  with self.assertRaises(ValueError):validate(self.raw,self.case,self.data)
 def test_partial_last_week_is_labelled(self):
  self.assertEqual(self.runview()['scenarios']['exclude_pay']['weekly_min'][-1]['days'],1)
