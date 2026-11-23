"""Verify matching controls and manual marketing revision in an isolated local DB."""
import asyncio,json,os,urllib.request
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('W01_STYLE_TEST_BASE_URL','').rstrip('/');url=urlparse(BASE)
if url.scheme!='http' or url.hostname not in ['127.0.0.1','localhost'] or url.port in [None,8088]:raise RuntimeError('격리된 로컬 테스트 서버만 지정하세요. 8088 금지.')
def api(path,body=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req) as response:return json.load(response)
async def main():
 before=api('/api/state');cid=before['cases'][0]['id'];original=api('/api/cases/'+cid)['case'];count=len(before['cases']);errors=[]
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(BASE+'/campaign#screen=SCM_1_Check&case='+cid);await page.locator('html[data-ready=true]').wait_for();await page.locator('label').filter(has_text='추가 발주 필요').first.click();editor=page.locator('#scm-order-editor');await editor.wait_for()
  await page.locator('#scm-select-SKU-3001').check();await page.locator('#scm-qty-SKU-3001').fill('12000');await page.locator('#scm-price-SKU-3001').fill('16800');await expect(page.locator('#scm-price-SKU-3001')).to_have_value('16,800');await expect(editor).to_contain_text('201,600,000원')
  styles=await page.locator('#scm-price-SKU-3001').evaluate('(e)=>{const s=getComputedStyle(e);return {height:e.getBoundingClientRect().height,borderRadius:s.borderRadius,borderColor:s.borderColor}}');assert styles['height']>=44 and styles['borderRadius']=='8px',styles
  await editor.scroll_into_view_if_needed();await page.screenshot(path='docs/assets/screenshots/scm-order-style-desktop.png',full_page=True)
  await page.set_viewport_size({'width':390,'height':844});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await page.screenshot(path='docs/assets/screenshots/scm-order-style-mobile.png',full_page=True)
  await page.set_viewport_size({'width':1440,'height':1000});await page.get_by_role('button',name='기안 변경 요청',exact=True).click();dialog=page.get_by_role('dialog',name='기안 변경 요청');await dialog.wait_for();assert await dialog.locator('[name=target]').input_value()=='마케팅';assert await dialog.locator('select[name=target]').count()==0
  await dialog.locator('[name=reason]').fill('캠페인 기간과 요청 예산 재검토');await page.screenshot(path='docs/assets/screenshots/adjustment-style-desktop.png',full_page=True)
  await page.set_viewport_size({'width':390,'height':844});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await page.screenshot(path='docs/assets/screenshots/adjustment-style-mobile.png',full_page=True)
  await dialog.get_by_role('button',name='요청 전달',exact=True).click();await expect(page.locator('html')).to_have_attribute('data-screen','MKT_1_Proposal',timeout=15000);await expect(page.locator('[aria-label="조정 요청 내용"]')).to_contain_text('캠페인 기간과 요청 예산 재검토');await page.locator('#p-title').fill('[모의] 마케팅이 직접 수정한 캠페인');await expect(page.locator('#p-title')).to_have_value('[모의] 마케팅이 직접 수정한 캠페인')
  d=api('/api/cases/'+cid);assert d['execution']['stage']==1 and d['execution']['adjustment']['target']=='마케팅';assert len(api('/api/state')['cases'])==count
  plan={**d['case']['marketing'],'title':'[모의] 마케팅이 직접 수정한 캠페인'};api('/api/marketing',{'role':'마케팅','operation':'submit','id':cid,'version':d['case']['version'],'plan':plan});after=api('/api/cases/'+cid);assert after['execution']['stage']==2 and after['execution']['adjustment'] is None;assert after['case']['title']==plan['title'];assert len(api('/api/state')['cases'])==count
  assert not errors,errors
  report={'field_style':styles,'money_format':'16,800','procurement_cost':201600000,'mobile_overflow':False,'marketing_request_target_fixed':True,'same_case_returned':True,'marketing_edit_and_resubmit':True,'after_stage':after['execution']['stage'],'new_case_created':False,'browser_errors':errors};Path('docs/verification/workflow/WORKFLOW_STYLE_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));await browser.close()
asyncio.run(main())
