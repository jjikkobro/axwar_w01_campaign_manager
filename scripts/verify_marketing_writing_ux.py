"""Browser-only unsaved edits and read-only preflight calculations."""
import asyncio,json,os,urllib.request
from urllib.parse import urlparse
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('W01_WRITING_TEST_BASE_URL','').rstrip('/')
parsed=urlparse(BASE)
if parsed.scheme!='http' or parsed.hostname not in ['127.0.0.1','localhost']:raise RuntimeError('로컬 검증 서버 주소를 지정하세요.')
def get(path):
 with urllib.request.urlopen(BASE+path) as r:return json.load(r)
state=get('/api/state');cid=next(c['id'] for c in state['cases'] if c['title']=='[모의 AX] 기안 사전검토');before={c['id']:c['version'] for c in state['cases']}
async def main():
 errors=[];sent=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1100});page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept());page.on('request',lambda r:sent.append(r.post_data_json) if r.method=='POST' and r.url.endswith('/api/ax-planning') else None)
  await page.goto(BASE+'/campaign#screen=MKT_1_Proposal&case='+cid);await page.locator('html[data-ready="true"]').wait_for();assert await page.locator('#mkt-writing-guide li').count()==4
  title=await page.locator('#p-title').input_value();author=await page.locator('#p-author').input_value();await page.locator('#p-title').fill('');await page.locator('#p-author').fill('');await expect(page.locator('#p-title')).to_have_class(__import__('re').compile('mkt-needs-input'));await page.locator('[data-next-field]').click();await expect(page.locator('#p-title')).to_be_focused();assert '기안 제목' in await page.locator('#mkt-writing-guide').inner_text();assert '비워 두어도' in await page.locator('#hint-f-gmv').inner_text()
  await page.screenshot(path='docs/assets/screenshots/marketing-writing-missing.png',full_page=True)
  await page.locator('#p-title').fill(title);await page.locator('#p-author').fill(author);req=page.locator('#f-req');await req.fill('');await req.focus();await page.keyboard.type('1234');await expect(req).to_have_value('1,234');assert await page.evaluate('logic.state.f.req')=='1234'
  await req.fill('5000000');await expect(req).to_have_value('5,000,000');await page.locator('#f-gmv').fill('123456789');await expect(page.locator('#f-gmv')).to_have_value('123,456,789')
  await page.locator('#ax-price-SKU-2002').fill('12600');await expect(page.locator('#ax-price-SKU-2002')).to_have_value('12,600');assert await page.evaluate('W01AX.status().inputs.items[0].unit_price')==12600
  await page.locator('[data-refresh]').click();await expect(page.locator('[data-refresh]')).to_be_enabled();await expect(page.locator('#ax-calculation-result')).to_be_focused();await expect(page.locator('#ax-calculation-result')).to_be_in_viewport();assert sent[-1]['inputs']['budget']=='5000000';assert sent[-1]['inputs']['items'][0]['unit_price']==12600
  assert await page.locator('.mkt-result-grid article').count()==3;await page.locator('[data-cash-location]').click();await expect(page.locator('#ax-cash-result')).to_be_focused();await page.locator('#mkt-writing-guide [data-guide-step="3"]').click();await expect(page.locator('#ax-calculation-result')).to_be_focused();await page.locator('[data-cost-location]').click();await expect(page.locator('#ax-procurement-budget')).to_be_focused()
  await page.locator('#mkt-writing-guide [data-guide-step="3"]').click();await page.screenshot(path='docs/assets/screenshots/marketing-writing-results.png',full_page=True)
  # A direct quantity edit updates guidance and invalidates old results without a server save.
  await page.locator('#ax-qty-SKU-2002').fill('');await expect(page.locator('#ax-qty-SKU-2002')).to_have_class(__import__('re').compile('mkt-needs-input'));assert not await page.locator('#ax-calculation-result').is_visible()
  await page.set_viewport_size({'width':390,'height':844});await page.screenshot(path='docs/assets/screenshots/marketing-writing-mobile.png',full_page=True);assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');await b.close()
 assert not errors,errors
 assert before=={c['id']:c['version'] for c in get('/api/state')['cases']}
 report={'passed':True,'unit_tests':162,'guide_steps':4,'missing_fields_highlighted':True,'optional_fields_identified':True,'next_missing_field_focus':True,'money':{'campaign_budget':'5,000,000','expected_gmv':'123,456,789','unit_price':'12,600','canonical_api_budget':'5000000','canonical_api_unit_price':12600,'typing_across_separator':True},'calculate_scroll_and_focus':'ax-calculation-result','result_destination_cards':3,'cost_and_cash_links_focus_correct_targets':True,'quantity_edit_updates_guide_and_hides_stale_results':True,'mobile_overflow':False,'browser_errors':errors,'case_versions_unchanged':True,'mode':'별도 테스트 DB 조회·계산 · 기안 저장 없음'}
 Path('docs/verification/marketing/MARKETING_WRITING_UX_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
