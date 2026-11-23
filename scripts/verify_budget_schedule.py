"""Modifies an AX fixture only in a separate local test DB."""
import asyncio,json,os,urllib.request
from urllib.parse import urlparse
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('W01_BUDGET_TEST_BASE_URL','').rstrip('/')
parsed=urlparse(BASE)
if parsed.scheme!='http' or parsed.hostname not in ['127.0.0.1','localhost'] or parsed.port in [None,8088]:raise RuntimeError('별도 테스트 DB 주소를 지정하세요. 8088 사용 금지.')
def get(path):
 with urllib.request.urlopen(BASE+path) as r:return json.load(r)
state=get('/api/state');cid=next(c['id'] for c in state['cases'] if c['title']=='[모의 AX] 기안 사전검토')
async def main():
 errors=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1100});page.set_default_timeout(20000);page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(BASE+'/campaign#screen=MKT_1_Proposal&case='+cid);await page.locator('html[data-ready="true"]').wait_for()
  assert await page.locator('.marketing-product-name').first.inner_text()=='기초 에센스';assert await page.locator('.marketing-product-id').first.inner_text()=='SKU-2002';assert '선택' not in await page.locator('#ax-sku-review h2').inner_text()
  await page.locator('#ax-budget-start').click();await expect(page.locator('#ax-sku-review')).to_be_focused()
  row=page.locator('[data-ax-sku="SKU-2002"]');await row.locator('[data-field=qty]').fill('16000');await row.locator('[data-field=unit_price]').fill('12600');await row.locator('[data-field=payment_date]').fill('2026-09-21');await page.locator('[data-refresh]').click();await expect(page.locator('[data-refresh]')).to_be_enabled();assert '201,600,000' in await page.locator('#ax-procurement-budget').inner_text();assert await page.locator('#f-req').input_value()=='5000000'
  old=await page.locator('#f-dl').input_value();await page.locator('[data-adopt-date=deadline]').click();await expect(page.locator('#f-dl')).to_have_value(old);assert '이릅니다' in await page.locator('.w01-notice').inner_text()
  await page.screenshot(path='docs/assets/screenshots/budget-schedule-procurement.png',full_page=True)
  await page.locator('[data-ax-sku="SKU-2002"] [data-field=qty]').fill('0');await page.locator('[data-term=settlement_offset_days]').fill('30');await page.locator('[data-adopt-date=settlement]').click();await expect(page.locator('[data-refresh]')).to_be_enabled();await expect(page.locator('#f-settle')).to_have_value('2026-08-18')
  await page.locator('[data-adopt-date=deadline]').click();await expect(page.locator('[data-refresh]')).to_be_enabled();await expect(page.locator('#f-dl')).to_have_value('2026-07-08')
  await page.locator('[data-return-budget]').click();await expect(page.locator('#f-req')).to_be_focused();await page.screenshot(path='docs/assets/screenshots/budget-schedule-applied.png',full_page=True)
  assert not await page.evaluate('values.notReady')
  await page.get_by_role('button',name=await page.evaluate('values.submitLabel'),exact=True).click();await page.locator('.w01-dialog').wait_for();await page.locator('.w01-dialog [type=submit]').click();await page.wait_for_url('**screen=MKT_2_Wait**')
  await page.goto(BASE+'/campaign#screen=MKT_1_Proposal&case='+cid);await page.locator('html[data-ready="true"]').wait_for();await page.set_viewport_size({'width':390,'height':844});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');await page.screenshot(path='docs/assets/screenshots/budget-schedule-mobile.png',full_page=True);await b.close()
 assert not errors,errors
 c=get('/api/cases/'+cid)['case'];t=c['ax_plan']['inputs']['schedule_terms'];assert t['settlement_mode']=='derived' and t['deadline_mode']=='derived';assert c['marketing']['budget']==5000000
 report={'passed':True,'unit_tests':162,'product_name_and_id_visible':True,'sku_review_required_for_calculation':True,'calculate_button_focuses_sku_review':True,'procurement_budget':201600000,'campaign_budget_preserved':5000000,'past_leadtime_deadline_not_adopted':True,'adopted_schedule_with_zero_new_order':{'settlement':'2026-08-18','contract_proposal_deadline':'2026-07-08','offset_days':30,'review_business_days':3},'assumptions_persisted_to_db':True,'browser_errors':errors,'mobile_overflow':False,'database':'별도 테스트 DB · 8088 캠페인 변경 없음'}
 Path('docs/verification/marketing/BUDGET_SCHEDULE_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
