"""Read-only server calls and unsaved browser edits for batch application."""
import asyncio,json,os,urllib.request
from urllib.parse import urlparse
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('W01_BATCH_TEST_BASE_URL','http://127.0.0.1:8088').rstrip('/')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost']:raise RuntimeError('로컬 미리보기만 사용하세요.')
def get(path):
 with urllib.request.urlopen(BASE+path) as r:return json.load(r)
state=get('/api/state');cid=next(c['id'] for c in state['cases'] if '기초 라인' in c['title']);before={c['id']:c['version'] for c in state['cases']}
async def main():
 errors=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(20000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
  await page.goto(BASE+'/campaign#screen=MKT_1_Proposal&case='+cid);await page.locator('html[data-ready="true"]').wait_for()
  await page.evaluate("()=>{logic.state.f.pl='색조';logic.state.f.start='2026-09-01';logic.state.f.end='2026-09-25';logic.state.pick={'SKU-3001':true,'SKU-3002':true,'SKU-3003':true};logic.state.dem={'SKU-3001':100,'SKU-3002':100,'SKU-3003':100};render();}")
  assert await page.locator('[data-order]').count()==0
  assert not any(t in ['입력 필요','입력됨'] for t in await page.locator('small').all_text_contents())
  for sid in ['SKU-3001','SKU-3002','SKU-3003']:
   assert await page.locator('#ax-qty-'+sid).input_value()=='';assert await page.locator('#ax-price-'+sid).input_value()==''
  budget=await page.evaluate('logic.state.f.req');await page.locator('[data-refresh]').click();await expect(page.locator('[data-refresh]')).to_be_enabled();expected=await page.evaluate('W01AX.status().result.items.map(r=>({id:r.sku_id,qty:r.chosen_qty,price:r.chosen_unit_price}))');cost=await page.evaluate('W01AX.status().result.schedule.procurement_budget')
  button=page.get_by_role('button',name='발주량과 비용 적용하기',exact=True);await expect(button).to_be_enabled();await button.click();await expect(page.locator('.mkt-apply-status')).to_contain_text('3개 제품')
  for row in expected:
   assert await page.locator('#ax-qty-'+row['id']).input_value()==str(row['qty']);assert await page.locator('#ax-price-'+row['id']).input_value()==format(row['price'],',')
  assert await page.evaluate('logic.state.f.req')==str(cost)
  assert await page.locator('#f-req').input_value()==format(cost,',')
  assert str(cost) in (await page.locator('#ax-procurement-budget').inner_text()).replace(',','')
  assert await page.locator('[data-order]').count()==0
  assert not any(t in ['입력 필요','입력됨'] for t in await page.locator('small').all_text_contents())
  await page.screenshot(path='docs/assets/screenshots/marketing-batch-applied.png',full_page=True);await page.set_viewport_size({'width':390,'height':844});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');await b.close()
 assert not errors,errors;assert before=={c['id']:c['version'] for c in get('/api/state')['cases']}
 report={'passed':True,'status_words_removed':True,'per_sku_order_import_removed':True,'single_apply_button':True,'applied_fields':expected,'procurement_cost':cost,'campaign_budget_autofilled':True,'money_comma_display':True,'mobile_overflow':False,'browser_errors':errors,'case_versions_unchanged':True,'mode':'로컬 미리보기에서 저장하지 않은 3개 SKU 계산·일괄 적용 검증'}
 Path('docs/verification/marketing/BATCH_ESTIMATE_APPLY_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
