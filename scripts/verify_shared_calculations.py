"""Apply a formula only in an explicitly selected isolated local test server."""
import asyncio,copy,json,os,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
B=os.environ.get('W01_SHARED_CALC_TEST_BASE_URL','').rstrip('/');u=urlparse(B)
if u.scheme!='http' or u.hostname not in ['127.0.0.1','localhost'] or u.port in [None,8088]:raise RuntimeError('격리 테스트 서버만 허용. 8088 금지.')
CID='4774d5b9-980c-456c-919b-d520870a6410'
def call(path,body=None):
 req=urllib.request.Request(B+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def good(p,b=None):
 code,d=call(p,b);assert code==200,(p,code,d);return d
async def main():
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);errors=[];pages={}
  for sid in ['MKT_1_Proposal','SCM_1_Check','FIN_1_Review','APR_1_CEO']:
   print('화면 확인:',sid,flush=True)
   page=await browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));pages[sid]=page
   await page.goto(B+'/campaign#screen='+sid+('' if sid=='MKT_1_Proposal' else '&case='+CID))
   try:await page.locator('html[data-ready=true]').wait_for(timeout=10000)
   except:
    print((await page.locator('body').inner_text())[:1500],errors,flush=True);raise
  m=pages['MKT_1_Proposal']
  await m.evaluate("logic.state.f={...logic.state.f,title:'작성 중 제목 유지',start:'2026-11-16',end:'2026-11-20',req:'5000000'};logic.state.pick={'SKU-3003':true};logic.state.dem={'SKU-3003':100};dirty=true;render()")
  await m.get_by_role('button',name='예상 발주량·비용 계산',exact=True).click()
  await m.locator('.common-planning-evidence').wait_for()
  await m.locator('.common-planning-evidence>summary').click()
  before=good('/api/calculation-version');state=good('/api/state');case_before=good('/api/cases/'+CID)
  assert before['revision']==state['calculation_context']['revision']==case_before['calculation_context']['revision']
  raw={'role':'SCM','version':state['finance_version'],'formula_id':'lead_time_days','expression':'lead_weeks * 5','decision_maker':'격리 검증 SCM','reason':'공통 입고 산식의 역할별 전파 검증','evidence':'격리 DB · 교육용 일수 가정'}
  preview=good('/api/formulas/preview',raw);good('/api/formulas/apply',{**raw,'preview_key':preview['preview_key'],'human_confirmed':True})
  after=good('/api/calculation-version');assert before['formula_revision']!=after['formula_revision']
  code,error=call('/api/marketing',{'role':'마케팅','operation':'save','expected_calculation_revision':before['revision'],'plan':{}});assert code==400 and '계산 기준' in error['error'],(code,error)
  await m.evaluate('window.W01Calculations.check()')
  assert await m.evaluate("logic.state.f.title")=='작성 중 제목 유지'
  assert await m.evaluate('window.W01Calculations.revision()')==after['revision']
  assert not await m.evaluate('window.W01AX.status().fresh')
  await m.get_by_role('button',name='예상 발주량·비용 계산',exact=True).click();await m.locator('.common-planning-evidence').wait_for()
  forecast=await m.evaluate('window.W01AX.status().result');actual=good('/api/cases/'+CID)
  sku='SKU-3003';r=next(i for i in forecast['planning']['items'] if i['sku_id']==sku);s=next(i for i in actual['scm_calculation']['planning']['items'] if i['sku_id']==sku)
  assert r['earliest_arrival_assumption']==s['earliest_arrival_assumption']=='2026-07-31';assert forecast['planning']['formula_revision']==actual['scm_calculation']['planning']['formula_revision']
  for sid,page in pages.items():
   if sid=='MKT_1_Proposal':continue
   await page.evaluate('window.W01Calculations.check()');await page.locator('html[data-ready=true]').wait_for()
   assert await page.evaluate('window.W01Calculations.revision()')==after['revision'],sid
  await m.locator('.common-planning-evidence>summary').click();await m.screenshot(path='docs/assets/screenshots/shared-calculation-marketing.png',full_page=True)
  await m.set_viewport_size({'width':390,'height':844});assert await m.evaluate('document.documentElement.scrollWidth<=innerWidth');await m.screenshot(path='docs/assets/screenshots/shared-calculation-mobile.png',full_page=True)
  assert not errors,errors
  report={'formula':{'id':raw['formula_id'],'before':'lead_weeks * 7','after':raw['expression']},'revision_changed':True,'roles_refreshed':list(pages),'marketing_draft_preserved':True,'old_forecast_invalidated':True,'old_revision_save_rejected':error,'same_sku':sku,'marketing_arrival':r['earliest_arrival_assumption'],'scm_arrival':s['earliest_arrival_assumption'],'same_formula_revision':True,'actual_approval_or_order_created':False,'formula_preview_case_count':len(preview['cases']),'mobile_overflow':False,'errors':errors}
  Path('docs/verification/workflow/SHARED_CALCULATION_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));await browser.close()
asyncio.run(main())
