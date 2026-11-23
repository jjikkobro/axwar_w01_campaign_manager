"""Read-only verification: handed-off marketing campaign cards open waiting pages."""
import asyncio,json,os,urllib.request
from pathlib import Path
from urllib.parse import quote,urlparse,parse_qs
from playwright.async_api import async_playwright
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8088')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost','::1']:raise SystemExit('Local only')
def read(path):
 with urllib.request.urlopen(BASE+path) as r:return json.load(r)
async def main():
 home=read('/api/home?role='+quote('마케팅'));rows=[c for c in home['todo']+home['processed'] if c.get('waiting')];assert rows,'대기 캠페인이 있는 로컬 시연 DB가 필요합니다.'
 before={c['id']:c['version'] for c in read('/api/state')['cases']};results=[];errors=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path=os.environ.get('W01_CHROMIUM','/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome'),args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
  for c in rows:
   assert c['screen']=='MKT_2_Wait' and c['action_tab'] is None
   await page.goto(BASE+'/#role='+quote('마케팅'));await page.locator('#todo-list').wait_for();card=page.locator('article[data-case="'+c['id']+'"]');await card.get_by_role('link',name='현재 위치 보기',exact=False).click();await page.locator('html[data-ready="true"]').wait_for()
   h=parse_qs(urlparse(page.url).fragment);assert h['screen']==['MKT_2_Wait'] and h['case']==[c['id']];assert await page.locator('#p-title').count()==0
   results.append({'id':c['id'],'stage':c['stage'],'screen':'MKT_2_Wait','passed':True})
  await page.screenshot(path='docs/assets/screenshots/marketing-wait-fixed.png',full_page=True);await b.close()
 assert not errors,errors;assert before=={c['id']:c['version'] for c in read('/api/state')['cases']}
 Path('docs/verification/marketing/MARKETING_WAIT_RESULTS.json').write_text(json.dumps({'passed':True,'campaigns':results,'browser_errors':errors,'case_versions_unchanged':True},ensure_ascii=False,indent=2)+'\n');print('마케팅 대기 이동 확인:',len(results),'건')
if __name__=='__main__':asyncio.run(main())
