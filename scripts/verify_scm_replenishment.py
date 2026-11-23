"""Read preview, then exercise only an isolated local DB. Never writes port 8088."""
import asyncio,copy,json,os,uuid,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('W01_REPLENISHMENT_TEST_BASE_URL','').rstrip('/')
u=urlparse(BASE)
if u.scheme!='http' or u.hostname not in ['127.0.0.1','localhost'] or u.port in [None,8088]:raise RuntimeError('별도 로컬 테스트 DB 서버를 지정하세요. 8088 쓰기 금지.')
CID='4774d5b9-980c-456c-919b-d520870a6410'
def api(path,body=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def get():
 code,d=api('/api/cases/'+CID);assert code==200,d;return d
before=get();a=before['scm_calculation'];assert a['recommendation']['kind']=='procurement';assert not before['demand_validation']['warnings'];assert not before['demand_validation']['ready'];assert a['adopted_estimate_revalidated']
# Deliberately fail *after* the demand confirmation has been validated. The whole transaction must roll back.
review={'decision_maker':'격리 검증 SCM','reason':'','evidence':'모의 검증 · 원본 재고·판매·발주','direction':'재고로 가능','alternatives':'정기 보충 공급능력과 일정 확인','requests':[],'items':[{'sku_id':i['sku_id'],'procurement':'추가 조달 없음','supply_result':'조정 필요'} for i in a['items']]}
command={'role':'SCM','id':CID,'version':before['case']['version'],'operation':'handoff','mutation_id':str(uuid.uuid4()),'review':review,'demand_confirmation':{'checked':True,'basis':before['demand_validation']['basis']},'replenishment_checked':True}
code,error=api('/api/scm',command);assert code==400,(code,error)
after_failure=get();assert after_failure['case']['version']==before['case']['version'];assert not after_failure['demand_validation']['ready'];assert len(after_failure['history'])==len(before['history'])
async def main():
 errors=[];requests=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await browser.new_page(viewport={'width':1440,'height':1000})
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:requests.append(r.url))
  await page.goto(BASE+'/campaign#screen=SCM_1_Check&case='+CID);await page.locator('html[data-ready=true]').wait_for()
  assert not await page.locator('a[href*="/hub#tab=demand"]').count()
  await page.locator('#scm-demand-evidence summary').first.click();await page.get_by_text('누락·참고 범위 이탈 없음.',exact=False).first.wait_for()
  await page.locator('#scm-replenishment summary').first.click()
  await page.locator('input[name="scm-decision"]').nth(1).check()
  await expect(page.get_by_role('button',name='대조 결과 전달',exact=True)).to_be_enabled()
  await page.screenshot(path='docs/assets/screenshots/scm-replenishment-1440.png',full_page=True)
  await page.get_by_role('button',name='대조 결과 전달',exact=True).click()
  dialog=page.get_by_role('dialog');await dialog.wait_for()
  assert not await dialog.locator('a[href*="/hub"]').count()
  assert await dialog.locator('[name=decision_maker]').input_value()=='SCM 담당자 (시연)'
  await dialog.locator('[name=demand_checked]').check();await dialog.locator('[name=replenishment_checked]').check()
  assert await dialog.locator('[name=reason]').input_value()==''
  await page.screenshot(path='docs/assets/screenshots/scm-demand-inline.png',full_page=True)
  await dialog.get_by_role('button',name='검토 결과 저장·재무 인계',exact=True).click()
  await page.locator('html[data-screen="SCM_2_WaitApproval"][data-ready=true]').wait_for()
  done=get();assert done['case']['marketing_stage']=='재무 검토 요청';assert done['demand_validation']['ready'];assert done['case']['scm']['review']['reason']=='';assert not done['case'].get('approval');assert not done['case'].get('execution',{}).get('orders')
  assert done['case']['scm']['review']['supply_plan']['status']=='계획 검토 · 공급·지급 미확인'
  await page.set_viewport_size({'width':390,'height':844});await page.goto(BASE+'/campaign#screen=SCM_1_Check&case='+CID);await page.locator('html[data-ready=true]').wait_for()
  await page.locator('#scm-replenishment summary').first.click();assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  await page.screenshot(path='docs/assets/screenshots/scm-replenishment-390.png',full_page=True)
  assert not errors,errors
  report={'case_id':CID,'before':{'version':before['case']['version'],'state':before['case']['marketing_stage'],'demand_ready':False},'planning':{'policy':a['replenishment']['policy'],'recommendation':a['recommendation']['label'],'items':[{k:i[k] for k in ['sku_id','regular_qty','incremental_qty','regular_orders','pipeline_assumptions','pre_campaign_gap','feasible']} for i in a['replenishment']['items']]},'failed_handoff':{'error':error,'version_unchanged':True,'demand_not_committed':True,'history_unchanged':True},'after':{'version':done['case']['version'],'state':done['case']['marketing_stage'],'demand_ready':True,'reason_optional':True,'approval':None,'orders':[],'history':[{'event':e['event'],'role':e['role']} for e in done['history']]},'browser':{'errors':errors,'no_hub_navigation':not any('/hub' in r for r in requests),'mobile_overflow':False}}
  Path('docs/verification/scm/SCM_REPLENISHMENT_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':True,'state':done['case']['marketing_stage'],'atomic_rollback':True,'errors':errors},ensure_ascii=False));await browser.close()
asyncio.run(main())
