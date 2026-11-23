"""Read-only browser and persistence checks for role landing/admin separation."""
import asyncio,json,os,urllib.request
from pathlib import Path
from urllib.parse import urlparse,quote
from playwright.async_api import async_playwright
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8088')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost','::1']:raise SystemExit('Local only')
def read(path):
 with urllib.request.urlopen(BASE+path) as r:return json.load(r)
async def main():
 before={c['id']:c['version'] for c in read('/api/state')['cases']};checks=[];errors=[];posts=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox']);page=await browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
  for role in ['마케팅','SCM','재무','승인권자']:
   r=read('/api/home?role='+quote(role));await page.goto(BASE+'/#role='+quote(role));await page.locator('#todo-list').wait_for();assert await page.locator('main>section').count()==2
   assert await page.locator('#todo-list article').count()==len(r['todo']);assert await page.locator('#processed-list article').count()==len(r['processed']);assert await page.locator('#new-campaign').count()==(1 if role=='마케팅' else 0)
   assert not set(c['id'] for c in r['todo'])&set(c['id'] for c in r['processed']);text=await page.locator('main').inner_text();assert not any(w in text for w in ['연체 회수','전속계약','주간 현금 재전망'])
   checks.append({'role':role,'todo':len(r['todo']),'processed':len(r['processed']),'two_sections':True})
   await page.screenshot(path='docs/assets/screenshots/home-'+{'마케팅':'marketing','SCM':'scm','재무':'finance','승인권자':'approval'}[role]+'.png',full_page=True)
  await page.goto(BASE+'/#role='+quote('마케팅'));await page.locator('#new-campaign').click();await page.locator('#p-title').wait_for();assert '/campaign' in page.url
  # Old bookmarked hash routes still resolve to the same campaign form.
  await page.goto(BASE+'/#screen=MKT_1_Proposal');await page.locator('#p-title').wait_for();assert '/campaign' in page.url
  await page.goto(BASE+'/admin#tab=data&role=SCM');await page.locator('#admin-content').wait_for();assert '연체 회수·지급 확인' in await page.locator('body').inner_text();assert '별도 계약 검토·통보' in await page.locator('#admin-content').inner_text();assert await page.locator('[data-action=contract-notice]').count()==0
  await page.screenshot(path='docs/assets/screenshots/admin-separate.png',full_page=True)
  for tab in ['data','audit']:
   await page.goto(BASE+'/admin#'+tab);await page.locator('#admin-content').wait_for();assert await page.locator('#admin-content table').count()>0
  await page.set_viewport_size({'width':390,'height':844});await page.goto(BASE+'/#role=SCM');await page.locator('#todo-list').wait_for();assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth+2');await page.screenshot(path='docs/assets/screenshots/home-mobile.png',full_page=True)
  # Explicit empty and error responses; no source data writes.
  await page.route('**/api/home?*',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps({'role':'SCM','todo':[],'processed':[]})))
  await page.reload();await page.locator('#todo-list .empty').wait_for();assert await page.locator('.empty').count()==2
  await page.unroute('**/api/home?*');await page.route('**/api/home?*',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"DB unavailable"}'))
  await page.reload();await page.locator('[role=alert]').wait_for();assert await page.locator('#retry').count()==1
  await browser.close()
 after={c['id']:c['version'] for c in read('/api/state')['cases']};assert before==after;assert not errors,errors;assert not posts,posts
 report={'passed':True,'base':BASE,'roles':checks,'admin_separate_work_visible':True,'legacy_and_create_links':True,'mobile_no_page_overflow':True,'empty_error_states':True,'read_only_case_versions_unchanged':True,'posts':posts,'browser_errors':errors}
 Path('docs/verification/workflow/ROLE_HOME_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
