"""Local modal verification; intercept SCM submission to preserve campaign records."""
import asyncio,json,urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
BASE='http://127.0.0.1:8088'
def state():
 with urllib.request.urlopen(BASE+'/api/state') as r:return json.load(r)
async def main():
 before=state();cid=before['cases'][0]['id'];versions=[(c['id'],c['version']) for c in before['cases']];results=[];errors=[];payloads=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);p=await b.new_page();p.on('pageerror',lambda e:errors.append(str(e)))
  async def block(route):
   payloads.append(route.request.post_data_json);await route.fulfill(status=400,json={'error':'검증용 차단 · 저장 안 함'})
  await p.route('**/api/scm',block)
  for screen,fn in [('MKT_1_Proposal','submitMarketing'),('SCM_1_Check','submitScm'),('FIN_1_Review','submitFinance'),('APR_2_Normal','submitApproval'),('SCM_3_PO','submitOrder'),('SCM_5_Receipt','submitReceipt'),('MKT_4_Close','submitClose')]:
   await p.goto(BASE+'/campaign#screen='+screen+'&case='+cid);await p.locator('html[data-ready=true]').wait_for()
   await p.evaluate("""()=>{values.notReady=false;if(screen==='MKT_1_Proposal')window.W01AX.package=()=>undefined;if(screen==='SCM_1_Check'){details.demand_validation.ready=false;details.demand_validation.items.forEach(i=>i.missing=false);details.scm_calculation.recommendation.kind='procurement';logic.state.decision='ok';}if(screen.startsWith('APR_'))logic.state.campaignDecision='승인';}""")
   await p.evaluate('()=>{void '+fn+'()}');modal=p.locator('.w01-dialog');await modal.wait_for();assert await modal.locator('input[type=checkbox]').count()==0
   if screen=='SCM_1_Check':
    for field in await modal.locator('textarea[required],input[required]').all():
     if not await field.input_value():await field.fill('검증 근거')
    await modal.locator('[type=submit]').click();await modal.locator('[role=alert]').filter(has_text='검증용 차단').wait_for();assert payloads[-1]['demand_confirmation']['checked'] is True;assert payloads[-1]['replenishment_checked'] is True
   await modal.get_by_role('button',name='닫기',exact=True).click();results.append({'screen':screen,'modal_checkboxes':0})
  await b.close()
 assert not errors,errors;assert [(c['id'],c['version']) for c in state()['cases']]==versions
 result={'screens':results,'scm_submit_without_checks':True,'submit_request_intercepted_no_save':True,'case_versions_unchanged':True,'browser_errors':errors};Path('docs/verification/workflow/MODAL_CHECKBOX_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
asyncio.run(main())
