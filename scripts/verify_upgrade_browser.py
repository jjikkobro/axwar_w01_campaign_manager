"""Read all upgrade views; use a human review/proposal/reply without auto-approval."""
import asyncio,json,os,urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
from scripts.verify_upgrade import BASE,get
async def main():
 report=json.loads(Path('docs/verification/system/UPGRADE_SCENARIOS.json').read_text());ids=report['ids'];cid=ids['D'];errors=[];checks=[];posts=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
  for tab in ['queue','portfolio','demand','comparison','consult','history','assistant']:
   await page.goto(BASE+'/hub#tab='+tab+'&role=SCM&case='+cid);await page.locator('#view').wait_for(timeout=15000);await page.locator('#hub-refresh').wait_for();assert 'undefined' not in await page.locator('body').inner_text();assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth+2'),tab
   checks.append({'tab':tab,'passed':True});await page.screenshot(path='docs/assets/screenshots/upgrade-'+tab+'.png',full_page=tab not in ['portfolio','history'])
  await page.goto(BASE+'/hub#tab=comparison&role=재무&case='+cid);await page.locator('[data-action=official]').wait_for();before=get(cid)['case']['version'];count=len(posts);await page.locator('[data-action=official]').click();await page.locator('[data-action=reforecast]').click();assert len(posts)==count;assert get(cid)['case']['version']==before;checks.append({'test':'반사실 비교 토글은 실제 승인/시나리오를 변경하지 않음','passed':True})
  # Shared task UI is based on real requests. Confirm assumptions, then request and answer work.
  fid=ids['F'];await page.goto(BASE+'/hub#tab=demand&role=SCM&case='+fid);await page.locator('[data-action=review-demand]').wait_for();await page.locator('[data-action=review-demand]').click();await fill(page,override_reason='원본 비교 관측 한계를 확인한 모의 부서 검토');await page.locator('.w01-dialog [type=submit]').click();await page.locator('.w01-layer').wait_for(state='detached');await page.locator('#view').wait_for()
  await page.goto(BASE+'/hub#tab=assistant&role=SCM&case='+fid);await page.locator('[data-action=assistant-propose]').wait_for();await page.locator('[data-action=assistant-propose]').click();await fill(page);await page.locator('.w01-dialog [type=submit]').click();await page.locator('.w01-layer').wait_for(state='detached');await page.locator('[data-action=assistant-accept]').wait_for();proposal=get(fid)['case']['assistant_proposals'][-1]
  assert not get(fid)['case'].get('execution',{}).get('decisions');await page.locator('[data-action=assistant-accept]').first.click();await fill(page);await page.locator('.w01-dialog [type=submit]').click();await page.locator('.w01-layer').wait_for(state='detached');await page.locator('#view').wait_for();assert not get(fid)['case'].get('execution',{}).get('decisions')
  await page.goto(BASE+'/hub#tab=consult&role=SCM&case='+fid);await page.locator('[data-action=answer]').wait_for();await page.locator('[data-action=answer]').last.click();await fill(page);await page.locator('.w01-dialog [type=submit]').click();await page.locator('.w01-layer').wait_for(state='detached');assert get(fid)['case']['execution']['notes'][-1]['answer'];checks.append({'test':'수요 확인 → 보조 제안 → 사람 채택 → 담당 작업/회신, 자동 승인 없음','passed':True,'mode':proposal['mode']})
  await page.set_viewport_size({'width':390,'height':844});await page.goto(BASE+'/hub#tab=queue&role=SCM&case='+cid);await page.locator('#view').wait_for();assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth+2');await page.screenshot(path='docs/assets/screenshots/upgrade-mobile.png',full_page=True);await b.close()
 assert not errors,errors
 result={'passed':True,'checks':checks,'browser_errors':errors,'base':BASE,'mode':'실제 로컬 DB 입력 · 외부 승인/회신은 모의'}
 Path('docs/verification/system/UPGRADE_BROWSER.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':True,'checks':len(checks)},ensure_ascii=False))
async def fill(page,**extra):
 d=page.locator('.w01-dialog')
 for k,v in {'decision_maker':'브라우저 SCM 검토자','reason':'계산 근거와 미확인 항목을 사람이 확인','evidence':'격리 DB 브라우저 모의 회신',**extra}.items():await d.locator('[name="'+k+'"]').fill(v)
if __name__=='__main__':asyncio.run(main())
