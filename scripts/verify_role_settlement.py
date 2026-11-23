"""Read-only local role-switch and predicted settlement verification; no API writes."""
import asyncio,json,urllib.request
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE='http://127.0.0.1:8088'
def get(path):
 with urllib.request.urlopen(BASE+path) as r:return json.load(r)
async def main():
 before=get('/api/state');versions=[(c['id'],c['version']) for c in before['cases']];c=next(c for c in before['cases'] if c.get('marketing',{}).get('settlement_draft') and not c.get('finance_review'));cid=c['id'];expected=c['marketing']['settlement_draft']['date'];errors=[];posts=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);p=await b.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
  await p.goto(BASE+'/campaign#screen=MKT_1_Proposal&case='+cid+'&role=SCM');await p.locator('#role-switch').wait_for();await expect(p.locator('#role-switch')).to_be_enabled();await p.locator('#role-switch').click();await p.locator('.w01-dialog [name=role]').select_option('재무');await p.locator('.w01-dialog [type=submit]').click();await expect(p.locator('html')).to_have_attribute('data-screen','FIN_1_Review');assert await p.evaluate('role')=='재무';assert await p.evaluate('readOnly') is False
  payment=await p.evaluate("details.finance_review_initial.routes.find(r=>r.kind==='캠페인집행').payment.date");assert payment==expected
  label=await p.evaluate('details.finance_review_view.recommendation.label');assert label!='캠페인 집행비 지급일 확인';assert '현금 전망' in label,label
  basis=await p.evaluate("details.finance_review_initial.routes.find(r=>r.kind==='캠페인집행').basis");assert '예측 지급일' in basis
  await p.evaluate('()=>{void submitFinance()}');await p.locator('.w01-dialog').wait_for();assert await p.locator('[name=date-0-0]').input_value()==expected;await p.get_by_role('button',name='닫기',exact=True).click()
  await p.locator('nav[aria-label="현업 절차 단계"] a[href*="screen=SCM_1_Check"]').first.click();await expect(p.locator('#role-switch')).to_contain_text('재무 · 읽기 전용');assert await p.locator('#app input:not(:disabled),#app textarea:not(:disabled),#app select:not(:disabled)').count()==0
  await p.set_viewport_size({'width':390,'height':844});assert await p.evaluate('document.documentElement.scrollWidth<=innerWidth');await p.locator('#role-switch').click();await p.locator('.w01-dialog [name=role]').select_option('SCM');await p.locator('.w01-dialog [type=submit]').click();await expect(p.locator('html')).to_have_attribute('data-role','SCM');await expect(p.locator('#role-switch')).to_have_text('SCM ▾');assert await p.evaluate('role')=='SCM';assert await p.evaluate('readOnly') is False
  assert not posts,posts;assert not errors,errors;await b.close()
 assert [(c['id'],c['version']) for c in get('/api/state')['cases']]==versions
 result={'role_switch_in_readonly':True,'switch_to_department_review':True,'readonly_preserved_until_explicit_switch':True,'marketing_predicted_payment':expected,'finance_prefilled_payment':payment,'recommendation':label,'date_provenance_retained':True,'finance_modal_prefilled':True,'mobile_overflow':False,'case_versions_unchanged':True,'no_post_requests':True,'errors':errors};Path('docs/verification/workflow/ROLE_SETTLEMENT_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
asyncio.run(main())
