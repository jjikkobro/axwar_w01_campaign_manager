import asyncio,json,os,urllib.request
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8087')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost','::1']:raise SystemExit('Local only')
async def main():
 with urllib.request.urlopen(BASE+'/api/state') as r:state=json.load(r)
 cid=next(c['id'] for c in state['cases'] if c.get('marketing'))
 report={'passed':False,'case_id':cid,'screens':[],'errors':[]}
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox']);page=await browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:report['errors'].append(str(e)))
  for s in json.loads(Path('web/screens/manifest.json').read_text())['screens']:
   await page.goto(BASE+'/#screen='+s['id']+'&case='+cid);await page.wait_for_selector('html[data-ready="true"][data-screen="'+s['id']+'"]',timeout=10000)
   body=await page.locator('body').inner_text();assert '화면을 불러오지 못했습니다' not in body,(s['id'],body)
   assert 'undefined' not in body,(s['id'],body)
   assert not await page.locator('#role-choice,#screen-choice,#case-choice,.design-panel').count(),s['id']
   assert await page.locator('main').count()==1
   report['screens'].append(s['id']);print('live',s['id'],flush=True)
  await browser.close()
 assert not report['errors'],report['errors'];report['passed']=True
 Path('docs/verification/screen-reviews/14-source-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':asyncio.run(main())
