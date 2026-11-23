import asyncio,json,os
from pathlib import Path
from playwright.async_api import async_playwright
BASE='http://127.0.0.1:8088'
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox'])
  page=await browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(BASE)
  state=await (await page.request.get(BASE+'/api/state')).json();manifest=await (await page.request.get(BASE+'/screens/manifest.json')).json()
  ids={x['title']:x['id'] for x in state['cases']};cid=next(v for k,v in ids.items() if '기초 라인' in k)
  results=[]
  for screen in manifest['screens']:
   print(screen['id'],flush=True)
   await page.goto(BASE+'/campaign#screen='+screen['id']+('&case='+cid if screen['id']!='MKT_1_Proposal' else ''))
   try:await page.locator('html[data-ready=true]').wait_for(timeout=10000)
   except:
    print((await page.locator('body').inner_text())[:1200],errors,flush=True);raise
   result=await page.evaluate("({owner:logic.state.owner,author:logic.state.f?.author,role,actor:window.W01Identity.name(role),error:document.querySelector('.w01-loading h1')?.textContent})")
   assert not result.get('error'),result
   expected=screen['role']+' 담당자 (시연)'
   assert result['actor']==expected,(screen,result)
   if screen['id']=='MKT_1_Proposal':assert result['author']==expected,result
   elif result.get('owner') is not None:assert result['owner']==expected,result
   results.append({'screen':screen['id'],**result})
  await page.goto(BASE+'/campaign#screen=SCM_1_Check&case='+cid);await page.locator('html[data-ready=true]').wait_for()
  await page.locator('#s-owner').fill('직접 수정 담당자');await page.locator('#s-owner').dispatch_event('change')
  await page.evaluate("logic.setState({decision: details.scm_calculation.recommendation.kind==='ready'?'ok':'po'})")
  assert await page.locator('#s-owner').input_value()=='직접 수정 담당자'
  assert await page.evaluate('!values.notReady'), await page.evaluate('values.checks')
  await page.screenshot(path='docs/assets/screenshots/actor-autofill-scm.png',full_page=True)
  await page.evaluate("void dialog('자동 입력 검증',metaFields())")
  assert await page.locator('[name=decision_maker]').input_value()=='SCM 담당자 (시연)'
  await page.get_by_role('button',name='닫기',exact=True).click()
  await page.goto(BASE+'/admin#tab=data&role=SCM');await page.get_by_role('button',name='업데이트',exact=False).first.wait_for()
  await page.get_by_role('button',name='업데이트',exact=False).first.click()
  assert await page.locator('[name=decision_maker]').input_value()=='SCM 담당자 (시연)'
  await page.route('**/api/session',lambda route:route.fulfill(json={'authenticated':True,'user':{'display_name':'접속 사용자 검증','individual_authentication':False}}))
  await page.goto(BASE+'/campaign#screen=MKT_1_Proposal');await page.locator('html[data-ready=true]').wait_for()
  assert await page.locator('#p-author').input_value()=='접속 사용자 검증'
  final_state=await (await page.request.get(BASE+'/api/state')).json()
  assert {c['id']:c['version'] for c in state['cases']}=={c['id']:c['version'] for c in final_state['cases']}
  assert not errors,errors
  report={'screens':results,'scm_handoff_enabled_after_required_decision':True,'manual_edit_preserved':True,'handoff_modal_prefill':True,'admin_prefill':True,'configured_profile_used':True,'database_writes':0,'errors':errors}
  Path('docs/verification/workflow/ACTOR_AUTOFILL_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'screens':len(results),'errors':errors,'passed':True},ensure_ascii=False))
  await browser.close()
asyncio.run(main())
