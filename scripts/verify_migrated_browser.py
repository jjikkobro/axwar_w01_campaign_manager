"""Bounded browser verification of all migrated layouts against a local server."""
import asyncio,json,os,urllib.request
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8087')
if urlparse(BASE).hostname not in ['localhost','127.0.0.1','::1']:raise SystemExit('Local only')
async def main():
 manifest=json.loads(Path('web/screens/manifest.json').read_text());report={'base':BASE,'screens':[],'errors':[]}
 with urllib.request.urlopen(BASE+'/api/state') as r:state=json.load(r)
 cid=next(c['id'] for c in state['cases'] if c.get('marketing'))
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
  page=await browser.new_page(viewport={'width':1440,'height':1000})
  page.on('pageerror',lambda e:report['errors'].append(str(e)))
  for s in manifest['screens']:
   print('Checking',s['id'],flush=True)
   await page.goto(BASE+'/#screen='+s['id']+'&case='+cid);await page.locator('#screen-choice').wait_for(timeout=6000)
   await page.wait_for_timeout(120)
   text=await page.locator('main').inner_text()
   assert 'PLAN-026' not in text and 'PLAN-027' not in text and '8.63억' not in text,(s['id'],'embedded example leaked')
   assert not await page.locator('[href$=".dc.html"]').count(),s['id']
   assert await page.locator('nav[aria-label="현업 절차 단계"] a').count()==7,s['id']
   empty=await page.locator('main section:empty').count();assert not empty,(s['id'],empty)
   assert len(text)>100,(s['id'],text)
   assert await page.locator('#role-choice').input_value()==s['role']
   overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth+2')
   assert not overflow,(s['id'],'desktop overflow')
   report['screens'].append({'id':s['id'],'role':s['role'],'passed':True,'sections':await page.locator('main section').count()})
   if s['id'] in ['MKT_1_Proposal','APR_1_CEO','SCM_5_Receipt']:await page.screenshot(path='docs/assets/screenshots/'+s['id']+'-migrated.png',full_page=True)
  await page.set_viewport_size({'width':390,'height':844})
  for s in manifest['screens']:
   await page.goto(BASE+'/#screen='+s['id']+'&case='+cid);await page.locator('#screen-choice').wait_for(timeout=6000);await page.wait_for_timeout(80)
   overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth+2')
   assert not overflow,(s['id'],'mobile overflow')
  await page.screenshot(path='docs/assets/screenshots/migration-mobile.png',full_page=True)
  await browser.close()
 assert not report['errors'],report['errors']
 report['passed']=True;report['mobile_screens']=13
 Path('docs/verification/screen-reviews/13-screen-browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
