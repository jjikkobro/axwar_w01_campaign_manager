"""Empty and failure states, without changing database contents."""
import asyncio,json,os,urllib.request
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8087')
if urlparse(BASE).hostname not in ['localhost','127.0.0.1','::1']:raise SystemExit('Local only')
async def main():
 with urllib.request.urlopen(BASE+'/api/state') as r:state=json.load(r)
 state.update(cases=[],tasks=[],events=[]);manifest=json.loads(Path('web/screens/manifest.json').read_text());errors=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(args=['--no-sandbox']);page=await b.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  async def empty(route):await route.fulfill(status=200,content_type='application/json',body=json.dumps(state))
  await page.route('**/api/state',empty)
  for s in manifest['screens']:
   await page.goto(BASE+'/#screen='+s['id']);await page.locator('#screen-choice').wait_for(timeout=6000)
   if s['id']!='MKT_1_Proposal':assert '선택된 캠페인이 없습니다.' in await page.locator('main').inner_text()
   else:assert await page.locator('#submit-plan').is_visible()
  await page.unroute('**/api/state',empty)
  async def fail(route):await route.fulfill(status=503,content_type='application/json',body=json.dumps({'error':'검증용 DB 연결 실패'}))
  await page.route('**/api/state',fail);await page.goto(BASE+'/');await page.locator('#retry').wait_for(timeout=6000);assert '검증용 DB 연결 실패' in await page.locator('body').inner_text()
  await page.unroute('**/api/state',fail);await page.locator('#retry').click();await page.locator('#submit-plan').wait_for(timeout=6000)
  await b.close()
 assert not errors,errors
 report={'passed':True,'empty_screens':13,'failure_message':True,'retry_recovery':True,'browser_errors':errors,'method':'브라우저 읽기 응답만 대체, DB 수정 없음'}
 Path('docs/verification/screen-reviews/13-screen-empty-error.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report)
if __name__=='__main__':asyncio.run(main())
