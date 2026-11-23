"""Creates and approves simulated records in an isolated local DB only."""
import asyncio,copy,json,os,uuid,urllib.request,urllib.error
from urllib.parse import urlparse
from pathlib import Path
from playwright.async_api import async_playwright,expect
from app.finance_review import initial_review
BASE=os.environ.get('W01_ESTIMATE_TEST_BASE_URL','').rstrip('/')
parsed=urlparse(BASE)
if parsed.scheme!='http' or parsed.hostname not in ['127.0.0.1','localhost'] or parsed.port in [None,8088]:raise RuntimeError('별도 테스트 DB의 로컬 서버만 사용하세요. 8088 금지.')
def api(path,body=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def good(path,body=None):
 code,d=api(path,body);assert code==200,(path,code,d);return d
s=good('/api/state');base=next(c for c in s['cases'] if '기초 라인' in c['title']);p=copy.deepcopy(good('/api/cases/'+base['id'])['case']['marketing']);p.update(title='[모의] 예상안 신청·일정 연동',campaign_name='예상안 신청·일정 연동',submission_mode='estimate_only',settlement_date=None,contract_deadline=None,group_total=None,scope_skus=['SKU-2002']);p['items']=[{'sku_id':'SKU-2002','demand':100,'unit':'EA/주','start':p['start'],'end':p['end'],'basis':'기존 판매와 과거 증분 검토','confidence':'보통','overlap':'기존 판매 제외한 순증'}]
inputs={'mode':'estimate_only','as_of':p['as_of'],'start':p['start'],'end':p['end'],'budget':p['budget'],'items':[{'sku_id':'SKU-2002','demand_mode':'manual','demand':100,'qty_mode':'manual','qty':16000,'price_mode':'manual','unit_price':12600}]}
cid=good('/api/marketing',{'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':p,'ax_inputs':inputs})['id']
meta={'decision_maker':'부서 검증 담당','reason':'원본과 가정 대조','evidence':'격리 DB 모의 검증'}
def execution(op,role,**kw):
 d=good('/api/cases/'+cid);return good('/api/execution',{'id':cid,'version':d['case']['version'],'role':role,'operation':op,'mutation_id':str(uuid.uuid4()),**meta,**kw})
async def main():
 errors=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(20000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
  await page.goto(BASE+'/campaign#screen=MKT_1_Proposal&case='+cid);await page.locator('html[data-ready="true"]').wait_for();assert await page.locator('#mkt-writing-guide').count()==0;assert await page.locator('#f-settle,#f-dl,[data-field=payment_date],.ax-schedule,.ax-cash').count()==0
  await page.locator('[data-refresh]').click();await expect(page.locator('[data-refresh]')).to_be_enabled();assert not await page.evaluate('values.notReady');await page.screenshot(path='docs/assets/screenshots/estimate-only-marketing.png',full_page=True)
  await page.get_by_role('button',name='캠페인 신청',exact=True).click();await page.locator('.w01-dialog').wait_for();await page.locator('.w01-dialog [type=submit]').click();await page.wait_for_url('**screen=MKT_2_Wait**');d=good('/api/cases/'+cid);assert d['case']['marketing']['settlement_date'] is None and d['case']['marketing']['contract_deadline'] is None;assert not d['operational_schedule']['rows']
  good('/api/ax-confirm',{'role':'SCM','id':cid,'version':d['case']['version'],'mutation_id':str(uuid.uuid4()),**meta})
  d=good('/api/cases/'+cid);assert d['execution']['stage']==3
  assert api('/api/ax-confirm',{'role':'재무','id':cid,'version':d['case']['version'],'mutation_id':str(uuid.uuid4()),**meta})[0]==400
  r=initial_review(d['case']);r.update(**meta,opinion='계획 지급일·현금·결재선 확인',alternatives='변경 시 재판정',performance_basis='성과는 미확인')
  for t in r['targets']:
   t['cash_scope']='전사 현금 반영 확인' if t['kind']=='재고발주' else '표본·현금 합산 제외'
   for pay in t['payments']:pay['date']='2026-09-21'
  good('/api/finance-review',{'role':'재무','id':cid,'version':d['case']['version'],'finance_version':good('/api/state')['finance_version'],'operation':'submit','review':r})
  assert good('/api/cases/'+cid)['execution']['stage']==4
  for authority in ['마케팅팀 전결','SCM 전결']:execution('campaign_decide','승인권자',authority=authority,decision='승인')
  d=good('/api/cases/'+cid);assert d['execution']['stage']==5;assert not d['operational_schedule']['rows']
  execution('order','SCM',lines=[{'target_id':'po-SKU-2002','qty':16000,'payment_date':'2026-09-21','order_date':'2026-07-01','wanted_date':'2026-08-26','reply_deadline':'2026-07-06','channel':'mail'}])
  d=good('/api/cases/'+cid);row=d['operational_schedule']['rows'][0];assert row['payment_date']=='2026-09-21' and not row['available']
  card=page.locator('[aria-label="SCM 발주·입고 일정"]');await expect(card).to_contain_text('2026-09-21',timeout=25000);assert '공급처 회신 대기' in await card.inner_text()
  execution('receipt','SCM',lines=[{'po_id':row['po_id'],'payment_date':'2026-09-21','shipments':[{'available_date':'2026-08-26','qty':16000}]}],message='모의 회신 확인',judgment='승인 조건 일치')
  await expect(page.locator('[aria-label="SCM 발주·입고 일정"]')).to_contain_text('2026-08-26',timeout=25000);await page.screenshot(path='docs/assets/screenshots/estimate-scm-confirmed-schedule.png',full_page=True)
  await page.goto(BASE+'/campaign#screen=MKT_4_Close&case='+cid);await page.locator('html[data-ready="true"]').wait_for();assert await page.locator('[aria-label="SCM 발주·입고 일정"]').count()==1
  await page.set_viewport_size({'width':390,'height':844});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');await b.close()
 assert not errors,errors
 final=good('/api/cases/'+cid);assert final['case']['marketing']['settlement_date'] is None;assert final['execution']['stage']==7
 report={'passed':True,'unit_tests':167,'mode':'예상안 신청','marketing_date_inputs_removed':True,'writing_guide_removed':True,'application_without_dates_saved':True,'finance_planned_dates_still_required_before_approval':True,'stage_flow':[2,3,4,5,6,7],'approvals_are_human':True,'before_po_no_operational_dates':True,'after_po':{'payment_date':'2026-09-21','available_date':None},'after_confirmed_receipt':{'payment_date':'2026-09-21','available_date':'2026-08-26'},'original_marketing_fields_not_overwritten':True,'marketing_schedule_populated_from_scm_records':True,'automatic_refresh_on_scm_change':True,'browser_errors':errors,'mobile_overflow':False,'database':'격리된 테스트 DB · 실제 8088 데이터 변경 없음','case_id':cid}
 Path('docs/verification/marketing/ESTIMATE_APPLICATION_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
