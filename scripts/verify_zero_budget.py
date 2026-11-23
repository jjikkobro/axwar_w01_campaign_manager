"""Create a zero-budget campaign in an isolated local test DB only."""
import asyncio,json,os,urllib.request,urllib.error,uuid
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright,expect
B=os.environ.get('W01_ZERO_BUDGET_TEST_BASE_URL','').rstrip('/');u=urlparse(B)
if u.scheme!='http' or u.hostname not in ['localhost','127.0.0.1'] or u.port in [None,8088]:raise RuntimeError('격리 테스트 서버만 허용합니다. 8088 금지.')
def api(p,body=None):
 req=urllib.request.Request(B+p,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(B+'/campaign#screen=MKT_1_Proposal');await page.locator('html[data-ready=true]').wait_for()
  await page.evaluate("logic.state.f={...logic.state.f,title:'[모의] 추가 발주 없는 0원 캠페인',name:'0원 캠페인 검증',media:['오프라인'],country:'국내',sales:'자사몰',pl:'색조',start:'2026-11-16',end:'2026-11-20',req:''};logic.state.pick={'SKU-3001':true};logic.state.dem={'SKU-3001':21};dirty=true;render()")
  assert not await page.evaluate("values.checks.find(c=>c.label==='캠페인 집행 예산').ok")
  await page.get_by_role('button',name='예상 발주량·비용 계산',exact=True).click();await page.locator('#ax-calculation-result').wait_for()
  assert await page.evaluate('W01AX.status().result.schedule.procurement_budget')==0
  await page.get_by_role('button',name='발주량과 비용 적용하기',exact=True).click();await expect(page.get_by_role('button',name='캠페인 신청',exact=True)).to_be_enabled()
  assert await page.locator('#f-req').input_value()=='0';assert not await page.locator('#f-req').evaluate("n=>n.classList.contains('mkt-needs-input')")
  await page.locator('#f-req').fill('');assert not await page.evaluate("values.checks.find(c=>c.label==='캠페인 집행 예산').ok")
  await page.locator('#f-req').fill('0');await expect(page.get_by_role('button',name='캠페인 신청',exact=True)).to_be_enabled()
  await page.screenshot(path='docs/assets/screenshots/zero-budget-marketing.png',full_page=True)
  await page.get_by_role('button',name='캠페인 신청',exact=True).click();dialog=page.get_by_role('dialog');await dialog.get_by_role('button',name='기안 저장·SCM 검토 요청',exact=True).click();await page.locator('html[data-screen="MKT_2_Wait"][data-ready=true]').wait_for()
  cid=await page.evaluate('caseId');_,d=api('/api/cases/'+cid);assert d['case']['marketing']['budget']==0;assert d['case']['marketing_stage']=='SCM 검토 요청';assert d['case']['ax_plan']['schedule']['procurement_budget']==0;assert not d['case'].get('approval')
  # The same server path must reject missing/negative values even without the browser.
  rejected=[]
  for amount in [None,'',-1]:
   plan={**d['case']['marketing'],'budget':amount};code,error=api('/api/marketing',{'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':plan});assert code==400,(code,error);rejected.append({'input':amount,'error':error['error']})
  await page.goto(B+'/campaign#screen=MKT_1_Proposal&case='+cid);await page.locator('html[data-ready=true]').wait_for();assert await page.locator('#f-req').input_value()=='0'
  assert not errors,errors
  report={'case_id':cid,'predicted_procurement_qty':0,'predicted_procurement_budget':0,'applied_budget_field':'0','empty_field_not_ready':True,'zero_field_ready':True,'saved_budget':d['case']['marketing']['budget'],'state':d['case']['marketing_stage'],'reload_preserves_zero':True,'invalid_requests_rejected':rejected,'approval':None,'errors':errors}
  Path('docs/verification/marketing/ZERO_BUDGET_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));await browser.close()
asyncio.run(main())
