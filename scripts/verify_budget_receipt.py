"""Exercise itemised budget entry in a separate local test database only."""
import asyncio,json,os,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlparse,quote
from playwright.async_api import async_playwright,expect
B=os.environ.get('W01_BUDGET_RECEIPT_TEST_BASE_URL','').rstrip('/');u=urlparse(B)
if u.scheme!='http' or u.hostname not in ['127.0.0.1','localhost'] or u.port in [None,8088]:raise RuntimeError('격리 테스트 서버만 허용합니다. 8088 금지.')
def api(p,b=None):
 q=urllib.request.Request(B+p,data=json.dumps(b).encode() if b else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(q) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def good(p,b=None):
 status,d=api(p,b);assert status==200,(p,status,d);return d
async def setnum(page,selector,val):
 x=page.locator(selector);await x.fill(str(val));await x.press('Tab')
async def main():
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(B+'/campaign#screen=MKT_1_Proposal');await page.locator('html[data-ready=true]').wait_for()
  assert await page.locator('#budget-direct').input_value()==''
  await page.evaluate("logic.state.f={...logic.state.f,title:'[모의] 항목별 예산 명세',name:'항목별 예산',media:['오프라인'],country:'국내',sales:'자사몰',pl:'색조',start:'2026-11-16',end:'2026-11-20',req:''};logic.state.pick={'SKU-3001':true};logic.state.dem={'SKU-3001':21};dirty=true;render()")
  await expect(page.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000);await page.locator('#receipt-qty-0').wait_for()
  await page.get_by_role('button',name='발주량과 비용 적용하기',exact=True).click();await expect(page.get_by_role('button',name='캠페인 신청',exact=True)).to_be_enabled()
  await setnum(page,'#receipt-qty-0',12000);await expect(page.locator('.receipt-grand b')).to_have_text('201,618,683원')
  await setnum(page,'#budget-variable-0',50000);await expect(page.locator('#f-req')).to_have_value('50,000')
  await setnum(page,'#budget-fixed-0',10000);await expect(page.locator('#f-req')).to_have_value('60,000')
  await setnum(page,'#budget-other',2000);await expect(page.locator('#f-req')).to_have_value('62,000');await expect(page.locator('.receipt-grand b')).to_have_text('201,662,000원')
  assert await page.locator('[data-ax-sku="SKU-3001"] [data-field=qty]').input_value()=='12000'
  assert '62,000원' in await page.locator('#ax-calculation-result').inner_text()
  assert '201,662,000원' in await page.locator('#ax-calculation-result').inner_text()
  await page.screenshot(path='docs/assets/screenshots/budget-receipt-desktop.png',full_page=True)
  await page.get_by_role('button',name='캠페인 신청',exact=True).click();d=page.get_by_role('dialog');await d.get_by_role('button',name='기안 저장·SCM 검토 요청',exact=True).click();await page.locator('html[data-screen="MKT_2_Wait"][data-ready=true]').wait_for()
  cid=await page.evaluate('caseId');saved=good('/api/cases/'+cid)['case'];assert saved['marketing']['budget']==62000;mc=saved['ax_plan']['inputs']['marketing_cost_inputs'];assert mc['manual_costs']['오프라인']=={'fixed':10000,'variable':50000};assert mc['other_cost']==2000;assert saved['ax_plan']['schedule']['procurement_budget']==201600000;assert not saved.get('approval')
  await page.goto(B+'/campaign#screen=MKT_1_Proposal&case='+cid);await page.locator('html[data-ready=true]').wait_for();await expect(page.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000);await expect(page.locator('#budget-variable-0')).to_have_value('50,000');await expect(page.locator('#budget-fixed-0')).to_have_value('10,000');await expect(page.locator('#budget-other')).to_have_value('2,000');await expect(page.locator('.receipt-grand b')).to_have_text('201,662,000원')
  await page.set_viewport_size({'width':390,'height':844});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await page.screenshot(path='docs/assets/screenshots/budget-receipt-mobile.png',full_page=True)
  state=good('/api/state');raw={'role':'마케팅','version':state['finance_version'],'formula_id':'marketing_execution_budget','expression':'round_krw((fixed_budget + variable_budget + other_cost) * 1.1)','decision_maker':'검증 담당','reason':'명세 합계 산식 테스트','evidence':'격리 데이터'}
  change=good('/api/formulas/preview',raw);good('/api/formulas/apply',{**raw,'preview_key':change['preview_key'],'human_confirmed':True});await page.evaluate('window.W01Calculations.check()');await page.locator('html[data-ready=true]').wait_for();await expect(page.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000);await expect(page.locator('.receipt-grand b')).to_have_text('201,668,200원');await page.get_by_text('설정 산식 조정',exact=True).wait_for();assert good('/api/cases/'+cid)['case']['marketing']['budget']==62000
  assert not errors,errors
  report={'marketing_items':{'오프라인 고정비':10000,'오프라인 기간비':50000,'별도 마케팅비':2000},'marketing_subtotal':62000,'sku':'SKU-3001','quantity':12000,'unit_price':16800,'procurement_subtotal':201600000,'total':201662000,'saved_budget':saved['marketing']['budget'],'saved_items':mc['manual_costs'],'reload_preserved':True,'formula_adjustment':6200,'new_total_after_formula':201668200,'saved_budget_unchanged':True,'mobile_overflow':False,'approval':None,'errors':errors};Path('docs/verification/marketing/BUDGET_RECEIPT_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));await b.close()
asyncio.run(main())
