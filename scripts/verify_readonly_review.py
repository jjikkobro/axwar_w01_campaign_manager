"""Read-only local browser verification; no campaign writes or paid calls."""
import asyncio,json,urllib.request
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE='http://127.0.0.1:8088'
def get(path):
 with urllib.request.urlopen(BASE+path) as r:return json.load(r)
async def main():
 state=get('/api/state');versions=[(c['id'],c['version']) for c in state['cases']];cid=next((c['id'] for c in state['cases'] if c['id']=='c1d48072-9c55-40dc-95f7-1d4457acc9ba'),versions[0][0]);errors=[];posts=[];results=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);p=await b.new_page(viewport={'width':1440,'height':1000});p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
  for owner,origin,targets in [('SCM','SCM_1_Check',['MKT_1_Proposal']),('재무','FIN_1_Review',['MKT_1_Proposal','SCM_1_Check'])]:
   await p.goto(BASE+'/campaign#screen='+origin+'&case='+cid);await p.locator('html[data-ready=true]').wait_for();assert await p.get_by_role('link',name='SCM·재무 협의',exact=True).count()==0
   for target in targets:
    await p.locator('nav[aria-label="현업 절차 단계"] a[href*="screen='+target+'"]').first.click();await expect(p.locator('html')).to_have_attribute('data-screen',target);await p.locator('section[aria-label="읽기 전용 안내"]').wait_for();assert await p.evaluate('role')==owner;assert await p.evaluate('readOnly') is True
    assert await p.locator('#app input:not(:disabled),#app select:not(:disabled),#app textarea:not(:disabled),#app button:not(:disabled):not(#role-switch)').count()==0
    assert await p.locator('#app .campaign-list-link').get_attribute('href')=='/#role='+__import__('urllib.parse',fromlist=['quote']).quote(owner)
    blocked=await p.evaluate("async()=>{try{await api('/api/execution',{operation:'note'});return false}catch(e){return e.message.includes('읽기 전용')}}");assert blocked
    await p.reload();await p.locator('section[aria-label="읽기 전용 안내"]').wait_for();assert await p.evaluate('role')==owner
    await p.set_viewport_size({'width':390,'height':844});assert await p.evaluate('document.documentElement.scrollWidth<=innerWidth');await p.set_viewport_size({'width':1440,'height':1000})
    if target=='SCM_1_Check':await p.screenshot(path='docs/assets/screenshots/finance-scm-readonly.png',full_page=True)
    await p.get_by_role('link',name=owner+' 검토로 돌아가기',exact=True).click();await expect(p.locator('html')).to_have_attribute('data-screen',origin);assert await p.evaluate('readOnly') is False;assert await p.locator('section[aria-label="읽기 전용 안내"]').count()==0
    results.append({'role':owner,'view':target,'role_preserved':True,'inputs_disabled':True,'post_blocked':True,'reload_preserved':True,'return_to_own_review':True})
  assert not errors,errors;assert not posts,posts;await b.close()
 assert [(c['id'],c['version']) for c in get('/api/state')['cases']]==versions
 result={'url':BASE,'cases':results,'consult_button_removed':True,'no_post_requests':True,'case_versions_unchanged':True,'browser_errors':errors};Path('docs/verification/workflow/READ_ONLY_REVIEW_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
asyncio.run(main())
