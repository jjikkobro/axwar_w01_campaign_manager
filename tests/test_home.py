import unittest
from app.home import build
class HomeTests(unittest.TestCase):
 def setUp(self):
  self.c={'id':'A','title':'진행 캠페인','marketing':{'start':'2026-07-13','end':'2026-07-19','contract_deadline':'2026-07-10'}}
  self.x={'stage':3,'status':'재무 검토 대기','targets':[],'closed':None,'withdrawn':None};self.config={'review_date':'2026-07-01'}
 def view(self,role,tasks=None,events=None,cases=None):return build(cases if cases is not None else [self.c],tasks or [],events or [],{},self.config,role,project=lambda *a:self.x)
 def event(self,role,name):return {'case_id':'A','role':role,'event':name,'detail':{}}
 def test_current_owner_has_to_do_without_task_duplicate(self):
  r=self.view('재무');self.assertEqual(len(r['todo']),1);self.assertEqual(r['processed'],[])
 def test_processed_follows_next_owner_and_lists_are_disjoint(self):
  e=[self.event('SCM','SCM 검토 완료 · 재무 인계')];r=self.view('SCM',events=e);self.assertEqual(r['processed'][0]['owner'],'재무');self.assertFalse(r['todo'])
  t=[{'id':'A:scm:verify','case_id':'A','role':'SCM','status':'대기','title':'재확인','due':'2026-07-08'}];r=self.view('SCM',t,e);self.assertEqual(len(r['todo']),1);self.assertFalse(r['processed'])
 def test_automatic_events_do_not_claim_human_work(self):
  self.assertFalse(self.view('SCM',events=[self.event('SCM','업무 단계 전이'),self.event('SCM','SCM 근거 변경 · 재검토 필요')])['processed'])
 def test_noncampaign_and_global_tasks_do_not_enter_home(self):
  ts=[{'id':'global:overdue:ar:1','case_id':None,'role':'마케팅','status':'대기','title':'연체 회수'}, {'id':'A:finance:contract:INF-001','case_id':'A','role':'마케팅','status':'대기','title':'전속계약 통보'}];self.assertFalse(self.view('마케팅',ts)['todo'])
 def test_closed_case_keeps_real_campaign_followup_deadline(self):
  self.x.update(stage=7,status='회차 종료',closed={'at':'x'});t=[{'id':'A:followup:performance','case_id':'A','role':'마케팅','status':'대기','title':'실제 성과 검산','due':'2026-07-26'}];r=self.view('마케팅',t);self.assertEqual(r['todo'][0]['deadline'],'2026-07-26')
 def test_list_metadata_does_not_change_finance_validation_input(self):
  seen=[]
  def project(case,*args):seen.append(case);return self.x
  build([{**self.c,'version':99}],[],[],{},self.config,'재무',project=project)
  self.assertNotIn('id',seen[0]);self.assertNotIn('version',seen[0]);self.assertEqual(seen[0]['_case_id'],'A')
 def test_marketing_handed_off_campaigns_open_wait_even_with_remaining_tasks(self):
  for stage in range(2,7):
   for key in ['marketing:performance','demand:verify','question:1']:
    with self.subTest(stage=stage,key=key):
     self.x.update(stage=stage,status='다음 부서 검토 대기')
     task={'id':'A:'+key,'case_id':'A','role':'마케팅','status':'대기','title':'추가 확인'}
     r=self.view('마케팅',[task]);self.assertFalse(r['todo']);row=r['processed'][0]
     self.assertEqual(row['screen'],'MKT_2_Wait');self.assertTrue(row['waiting']);self.assertIsNone(row['action_tab']);self.assertEqual(len(row['tasks']),1)
 def test_marketing_draft_rework_and_close_stay_on_their_work_pages(self):
  for stage,status,screen in [(1,'기안 작성','MKT_1_Proposal'),(3,'보류·재검토','MKT_3_Hold'),(7,'일정 정리','MKT_4_Close')]:
   self.x.update(stage=stage,status=status);row=self.view('마케팅')['todo'][0]
   self.assertEqual(row['screen'],screen);self.assertFalse(row['waiting'])
 def test_marketing_submitted_campaign_is_processed_without_recent_events(self):
  for stage in range(2,7):
   self.x.update(stage=stage,status='다음 담당자 진행 중')
   r=self.view('마케팅');self.assertFalse(r['todo']);self.assertEqual(len(r['processed']),1)
 def test_marketing_schedule_stage_returns_to_todo_despite_old_tasks(self):
  self.x.update(stage=7,status='마케팅 정리 대기')
  r=self.view('마케팅',[{'id':'A:demand:verify','case_id':'A','role':'마케팅','status':'대기','title':'이전 보완 작업'}]);self.assertEqual(r['todo'][0]['screen'],'MKT_4_Close');self.assertIsNone(r['todo'][0]['action_tab']);self.assertFalse(r['processed'])
 def test_closed_campaign_without_followup_opens_close_record(self):
  self.x.update(stage=7,status='회차 종료',closed={'at':'x'})
  r=self.view('마케팅');self.assertFalse(r['todo']);self.assertEqual(r['processed'][0]['screen'],'MKT_4_Close')
 def test_other_roles_and_unknown_role(self):
  self.assertFalse(self.view('승인권자')['todo']);self.assertFalse(self.view('SCM',cases=[])['processed'])
  with self.assertRaises(ValueError):self.view('시스템 관리자')
if __name__=='__main__':unittest.main()
