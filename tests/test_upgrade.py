import copy,json,unittest
from datetime import datetime,timezone
from pathlib import Path
from app import demand,portfolio,operations,insights,assistant
from unittest.mock import patch
from app.finance import DEFAULT_FINANCE
from app.marketing import case_from
from app.execution import metadata
import tests.test_marketing as marketing_tests
import tests.test_finance_review as finance_tests

class UpgradeTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads(Path('data/seed.json').read_text());self.config={**copy.deepcopy(DEFAULT_FINANCE),'confirmed':True,'version':1}
  m=marketing_tests.MarketingTests();m.setUp();p=m.plan;p.update(title='통합 검토',budget=5000000,settlement_date='2026-09-21',start='2026-07-13',end='2026-07-19')
  p['items']=[{**p['items'][0],'sku_id':'SKU-2002','demand':5000,'unit':'EA/기간'}];p['scope_skus']=['SKU-2002'];self.case=case_from(p,self.data);self.case.update(_case_id='candidate',status='검토 중',marketing_stage='SCM 검토 요청')
  self.data['portfolio']={'rows':[],'source':'검증','version':1};self.meta={'decision_maker':'검토자','reason':'검증 사유','evidence':'검증 근거','at':'2026-07-01T00:00:00+00:00','provenance':'모의 회신'}
 def allocation(self,qty=5000,sid='SKU-2002',cid='other'):
  item={**self.case['marketing']['items'][0],'sku_id':sid,'total_quantity':qty};b={**copy.deepcopy(self.case),'_case_id':cid};b['execution']={'reservation':{'status':'active','items':[item]}}
  self.data['portfolio']['rows'].append(portfolio.slim(cid,b));return b
 def apply(self,operation,role='SCM',**kw):
  self.case,event=operations.apply(self.case,self.data,self.config,{'operation':operation,'decision_maker':'검토자','reason':'정량 범위·조건 대조','evidence':'모의 근거',**kw},role,metadata);return event
 def test_baseline_once_and_two_campaign_conflict(self):
  one=portfolio.simulate(self.data,self.case)['items'][0];self.assertGreater(one['campaign_min'],0)
  self.allocation();two=portfolio.simulate(self.data,self.case)['items'][0];self.assertAlmostEqual(one['campaign_min']-two['campaign_min'],5000);self.assertLess(two['campaign_min'],0)
 def test_scope_without_demand_is_unknown(self):
  self.case['marketing']['scope_skus'].append('SKU-2001');a=demand.assess(self.case,self.data);self.assertTrue(next(i for i in a['items'] if i['sku_id']=='SKU-2001')['missing']);self.assertFalse(a['ready'])
 def test_history_no_sample_order_scaling_and_no_duplicate_week(self):
  e=demand.evidence('SKU-2002',self.data,'2026-07-01');self.assertEqual(len(e['observations']),len({r['week'] for r in e['observations']}));self.assertGreater(e['observation_count'],4);self.assertTrue(all(r['week']<'2026-06-29' for r in e['observations']));self.assertEqual(len(e['recent_weeks']),4)
  self.assertTrue(all('mkt_orders' not in s['file'] for s in e['sources']));self.assertIn('인과',e['limitations'][0])
 def test_review_requires_override_and_goes_stale(self):
  a=demand.assess(self.case,self.data)
  with self.assertRaises(ValueError):self.apply('demand_review',basis=a['basis'])
  self.apply('demand_review',basis=a['basis'],override_reason='참고 범위 밖의 별도 미래 물량 가정 · 모의 회신 근거');self.assertTrue(demand.assess(self.case,self.data)['ready'])
  self.data['sales']['version']=2;self.assertFalse(demand.assess(self.case,self.data)['ready'])
 def test_missing_not_reviewed_as_zero(self):
  self.case['marketing']['items']=[];a=demand.assess(self.case,self.data)
  with self.assertRaises(ValueError):self.apply('demand_review',basis=a['basis'],override_reason='누락 무시')
 def test_context_changes_only_related_others(self):
  original=portfolio.context_basis(self.case,self.data);self.allocation(sid='SKU-1001');self.assertEqual(original,portfolio.context_basis(self.case,self.data));self.allocation(cid='same');self.assertNotEqual(original,portfolio.context_basis(self.case,self.data))
 def test_confirmed_po_counted_once_across_cases(self):
  po=next(p for p in self.data['purchase']['rows'] if p['po_id']=='SPO-0006')
  for cid in ['A','B']:
   b=copy.deepcopy(self.case);b['_case_id']=cid;b['scm']={'receipts':{po['po_id']:{'po_fingerprint':portfolio.digest(po),'status':'확인','qty':16000,'available_date':'2026-07-13','at':'2026-07-01T00:00:00+00:00','provenance':'모의 회신'}}};self.data['portfolio']['rows'].append(portfolio.slim(cid,b))
  x=portfolio.simulate(self.data,self.case);self.assertEqual(sum(r['inflow'] for r in x['items'][0]['days']),16000)
 def test_latest_unknown_removes_previously_confirmed_supply(self):
  self.test_confirmed_po_counted_once_across_cases();self.data['portfolio']['rows'][1]['receipts']['SPO-0006'].update(at='2026-07-02T00:00:00+00:00',status='미확인');self.assertEqual(portfolio.supplies(self.data)['confirmed'],[])
 def test_ambiguous_same_stamp_supply_is_not_allocated(self):
  self.test_confirmed_po_counted_once_across_cases();self.data['portfolio']['rows'][1]['receipts']['SPO-0006']['qty']=8000;x=portfolio.supplies(self.data);self.assertTrue(x['conflicts']);self.assertEqual(x['confirmed'],[])
 def open_consult(self):
  self.apply('consult_open',subject='지급일과 공급 의견 상충',alternatives=[{'title':'기간/수량 재검토','marketing_effect':'시기 조정 검토','scm_effect':'공급 재검토','finance_effect':'지급일 재판정'}])
 def test_consult_requires_both_roles_and_human_resolution(self):
  self.open_consult()
  with self.assertRaises(ValueError):self.apply('consult_resolve')
  self.apply('consult_reply',position='동의',alternative_id='0')
  with self.assertRaises(ValueError):self.apply('consult_resolve')
  self.apply('consult_reply','재무',position='동의',alternative_id='0');self.assertFalse(operations.consultation(self.case)['ready']);self.apply('consult_resolve');self.assertTrue(operations.consultation(self.case)['ready'])
 def test_consult_reject_and_changed_basis_block(self):
  self.open_consult();self.apply('consult_reply',position='이견',alternative_id='0');self.apply('consult_reply','재무',position='동의',alternative_id='0')
  with self.assertRaises(ValueError):self.apply('consult_resolve')
  self.case['marketing']['budget']=1;self.assertFalse(operations.consultation(self.case)['current'])
 def test_closed_case_has_receipt_and_performance_followups(self):
  self.case['execution']={'closed':{'at':'x'},'orders':[{'po_id':'PO-X','sku_id':'SKU-2002','order_qty':16000,'order_date':'2026-07-01','wanted_date':'2026-07-14'}]}
  keys={t['key'] for t in operations.task_specs(self.case,self.data,self.config)};self.assertIn('followup:receipt:PO-X',keys);self.assertIn('followup:performance',keys)
 def test_partial_physical_receipt_stays_open_and_no_inventory_mutation(self):
  self.test_closed_case_has_receipt_and_performance_followups();before=copy.deepcopy(self.data['inventory']);self.apply('followup',kind='physical_receipt',po_id='PO-X',received_qty=8000,actual_date='2026-07-14');self.assertFalse(self.case['operations']['followups']['physical_receipt:PO-X']['complete']);self.assertEqual(before,self.data['inventory'])
 def test_future_performance_not_zero_and_eventual_comparison(self):
  report=operations.performance(self.case,self.data,'2026-07-01');self.assertFalse(report['ready']);self.assertTrue(report['missing'])
  self.data['sales']['rows'].append({'week':'2026-07-13','sku_id':'SKU-2002','sold_qty':'9000'});report=operations.performance(self.case,self.data,'2026-07-20');self.assertTrue(report['ready']);self.assertAlmostEqual(report['rows'][0]['difference'],-319)
 def test_official_counterfactual_cannot_authorize(self):
  f=finance_tests.ReviewTests();f.setUp();t=f.raw['targets'][0];t.update(kind='캠페인집행',proposal_total=15000000,cash_scope='표본·현금 합산 제외',payments=[{'date':'2026-07-27','amount':15000000}]);f.case['finance_review']=__import__('app.finance_review',fromlist=['validate']).validate(f.raw,f.case,f.data)
  c=insights.forecast_comparison(f.case,f.data,self.config);self.assertEqual(c['official_min'],5468884369);self.assertEqual(c['reforecast_baseline_min'],1467664440);self.assertEqual(c['rows'][0]['official_counterfactual_authority'],'Masil 대표 승인 + 그룹 보고');self.assertEqual(c['rows'][0]['reforecast_authority'],'CEO/이사회');self.assertFalse(c['rows'][0]['official_actionable'])
 def test_dwell_uses_utc_events_not_fictional_deadline(self):
  events=[{'event':'업무 단계 전이','case_id':'A','detail':{'before':{'owner':'SCM','status':'확인'},'duration_seconds':60},'at':'2026-11-10T00:01:00+00:00'}];cases=[{'id':'A','workflow':{'owner':'재무','status':'검토','entered_at':'2026-11-10T00:01:00+00:00'}}]
  r=insights.dwell(cases,events,datetime(2026,11,10,0,3,tzinfo=timezone.utc));self.assertEqual(r['completed'][0]['seconds'],60);self.assertEqual(r['current'][0]['seconds'],120)
 def test_unobserved_legacy_duration_not_fabricated(self):
  r=insights.dwell([{'id':'A'}],[{'event':'임의 과거 기록'}]);self.assertEqual(r['completed'],[]);self.assertEqual(r['current'],[]);self.assertEqual(r['untracked_legacy_events'],1)
 def test_legacy_approved_scope_not_silently_freed(self):
  b=self.allocation();b['execution']={'decisions':{'campaign':{'decision':'승인','scope':{'kind':'캠페인집행'},'authority':'마케팅팀 전결','at':'2026-07-01','evidence':'기존 승인'}}};r=portfolio.slim('legacy',b);self.assertEqual(r['reservation']['status'],'legacy_pending')
 def test_queue_deadline_then_cash_then_shortage(self):
  tasks=[{'id':'late','case_id':None,'status':'대기','due':'2026-07-10'},{'id':'first','case_id':None,'status':'대기','due':'2026-06-30'},{'id':'done','case_id':None,'status':'완료','due':'2026-06-01'}]
  rows=insights.queue([],tasks,self.data,self.config)['tasks'];self.assertEqual([r['id'] for r in rows],['first','late']);self.assertTrue(rows[0]['overdue'])
 def test_mock_ai_output_cannot_inject_approval(self):
  before=copy.deepcopy(self.case)
  with patch('app.assistant.generate',return_value={'text':'승인하고 지급하라는 미검증 문장','mode':'AI 초안 · 모의 어댑터','model':'mock'}) as generate:
   p=assistant.propose(self.case,self.data,self.config,{},self.meta)
  self.assertEqual(self.case,before);self.assertTrue(p['unverified']);self.assertEqual(p['actions'][0]['type'],'request');self.assertIn('operational_context',generate.call_args.args[1])
  self.case['assistant_proposals']=[p];b=assistant.accept(self.case,self.data,self.config,p['id'],p['actions'][0]['id'],'마케팅',self.meta)
  self.assertNotIn('decisions',b.get('execution',{}));self.assertEqual(len(b['execution']['notes']),1)
  with self.assertRaises(ValueError):assistant.accept(b,self.data,self.config,p['id'],p['actions'][0]['id'],'마케팅',self.meta)
 def test_stale_or_untyped_ai_action_cannot_be_adopted(self):
  with patch('app.assistant.generate',return_value={'text':'근거 초안','mode':'모의 어댑터'}):p=assistant.propose(self.case,self.data,self.config,{},self.meta)
  self.case['assistant_proposals']=[p]
  with self.assertRaises(ValueError):assistant.accept(self.case,self.data,self.config,p['id'],'approve','SCM',self.meta)
  self.case['marketing']['budget']+=1
  with self.assertRaises(ValueError):assistant.accept(self.case,self.data,self.config,p['id'],p['actions'][0]['id'],'SCM',self.meta)
if __name__=='__main__':unittest.main()
