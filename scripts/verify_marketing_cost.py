"""Marketing-budget adoption and formula settings in an isolated local DB."""
import asyncio,json,os,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright,expect
B=os.environ.get('W01_MARKETING_COST_TEST_BASE_URL','').rstrip('/');u=urlparse(B)
if u.scheme!='http' or u.hostname not in ['127.0.0.1','localhost'] or u.port in [None,8088]:raise RuntimeError('격리 테스트 서버만 허용합니다. 8088 금지.')
def api(p,b=None):
 req=urllib.request.Request(B+p,data=json.dumps(b).encode() if b else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def good(p,b=None):
 status,d=api(p,b);assert status==200,(status,d);return d
async def prepare(page,title):
 await page.goto(B+'/campaign#screen=MKT_1_Proposal');await page.locator('html[data-ready=true]').wait_for()
 await page.evaluate("title=>{logic.state.f={...logic.state.f,title,name:title,media:['오프라인'],country:'국내',sales:'자사몰',pl:'색조',start:'2026-11-16',end:'2026-11-20',req:''};logic.state.pick={'SKU-3001':true};logic.state.dem={'SKU-3001':21};dirty=true;render()}",title)
 await expect(page.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000);await page.locator('#ax-calculation-result').wait_for()
 await page.get_by_role('button',name='발주량과 비용 적용하기',exact=True).click();await expect(page.get_by_role('button',name='캠페인 신청',exact=True)).to_be_enabled()
async def submit(page,scope=False):
 await page.get_by_role('button',name='캠페인 신청',exact=True).click();d=page.get_by_role('dialog')
 assert await d.locator('[name=marketing_scope_ack]').count()==0
 await d.get_by_role('button',name='기안 저장·SCM 검토 요청',exact=True).click();await page.locator('html[data-screen="MKT_2_Wait"][data-ready=true]').wait_for();return await page.evaluate('caseId')
async def main():
 errors=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);p=await b.new_page(viewport={'width':1440,'height':1000});p.on('pageerror',lambda e:errors.append(str(e)))
  await prepare(p,'[모의] 조달비 없이 마케팅비만 있는 캠페인');r=await p.evaluate('W01AX.status().result');cost=r['marketing_cost']['recommended_budget']
  assert r['schedule']['procurement_budget']==0 and cost>0;assert int((await p.locator('#f-req').input_value()).replace(',',''))==cost
  await p.locator('.marketing-cost-evidence>summary').click();await p.screenshot(path='docs/assets/screenshots/marketing-cost-desktop.png',full_page=True)
  cid=await submit(p,True);saved=good('/api/cases/'+cid)['case'];assert saved['marketing']['budget']==cost;assert saved['marketing']['budget_basis'];assert saved['ax_plan']['marketing_cost']['scope_confirmation']['decision_maker'];assert not saved.get('approval');assert not saved.get('execution',{}).get('orders')
  # Explicit zero is still valid when the person enters it, rather than confusing it with procurement zero.
  await prepare(p,'[모의] 담당자가 직접 0원을 입력한 캠페인');await p.locator('#f-req').fill('0');await expect(p.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000);await expect(p.get_by_role('button',name='캠페인 신청',exact=True)).to_be_enabled();zero=await submit(p);assert good('/api/cases/'+zero)['case']['marketing']['budget']==0
  # Changing the centrally managed model changes current recommendations, not the recorded adopted budget.
  state=good('/api/state');raw={'role':'마케팅','version':state['finance_version'],'formula_id':'marketing_variable_budget','expression':'round_krw(reference_daily * campaign_days * 1.2)','decision_maker':'마케팅 검증 담당','reason':'비용 산식 변경 전파 검증','evidence':'격리 DB 검증'}
  preview=good('/api/formulas/preview',raw);assert any(c['marketing_budget_after']>c['marketing_budget_before'] for c in preview['cases'])
  good('/api/formulas/apply',{**raw,'preview_key':preview['preview_key'],'human_confirmed':True})
  updated=good('/api/ax-planning',{'role':'마케팅','id':cid,'inputs':saved['ax_plan']['inputs']});assert updated['marketing_cost']['recommended_budget']>cost;assert good('/api/cases/'+cid)['case']['marketing']['budget']==cost
  settings=good('/api/formulas?role='+__import__('urllib.parse',fromlist=['quote']).quote('마케팅'));keys=['marketing_fixed_budget','marketing_variable_budget','marketing_execution_budget','campaign_total_requirement'];assert all(any(f['id']==k and f['editable'] for f in settings['formulas']) for k in keys)
  await p.goto(B+'/campaign#screen=MKT_1_Proposal&case='+cid);await p.locator('html[data-ready=true]').wait_for();await expect(p.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000);await p.locator('.marketing-cost-evidence').wait_for();await p.set_viewport_size({'width':390,'height':844});await p.locator('.marketing-cost-evidence>summary').click();assert await p.evaluate('document.documentElement.scrollWidth<=innerWidth');await p.screenshot(path='docs/assets/screenshots/marketing-cost-mobile.png',full_page=True)
  assert not errors,errors
  report={'case_id':cid,'procurement_cost':0,'recommended_marketing_budget':cost,'saved_campaign_budget':saved['marketing']['budget'],'scope_confirmation_saved':True,'manual_zero_saved':True,'formula_setting_keys':keys,'updated_recommendation':updated['marketing_cost']['recommended_budget'],'adopted_budget_not_overwritten':True,'comparables':r['marketing_cost']['items'],'sources':r['marketing_cost']['sources'],'cash_scope':'표본 기반 마케팅 가정은 전사 현금에 자동 합산하지 않음','approval':None,'orders':[],'mobile_overflow':False,'errors':errors};Path('docs/verification/marketing/MARKETING_COST_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['procurement_cost','recommended_marketing_budget','manual_zero_saved','updated_recommendation','errors']},ensure_ascii=False));await b.close()
asyncio.run(main())
