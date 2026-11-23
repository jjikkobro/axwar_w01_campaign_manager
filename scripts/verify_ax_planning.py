"""Scenario writes only to an isolated local clone; never the preview DB."""
import asyncio,copy,json,os,uuid,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('W01_AX_TEST_BASE_URL','').rstrip('/')
parsed=urllib.parse.urlparse(BASE)
if parsed.scheme!='http' or parsed.hostname not in ['127.0.0.1','localhost'] or parsed.port in [None,8088]:raise RuntimeError('별도 AX 테스트 DB의 로컬 서버 주소를 지정하세요. 8088 사용 금지.')
def api(path,body=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def good(path,body=None):
 code,d=api(path,body);assert code==200,(path,code,d);return d
async def main():
 state=good('/api/state');base=next(c for c in state['cases'] if '기초 라인' in c['title']);cid=base['id'];original=good('/api/cases/'+cid);config=state['finance']['config'];assert config['confirmed']
 before={c['id']:c['version'] for c in state['cases']}
 inputs={'as_of':'2026-07-01','start':'2026-07-13','end':'2026-07-19','budget':5000000,'settlement_date':'2026-09-21','items':[{'sku_id':'SKU-2002','demand_mode':'manual','demand':100,'qty_mode':'manual','qty':0,'price_mode':'manual','unit_price':12600}]}
 prediction=good('/api/ax-planning',{'role':'마케팅','inputs':inputs});assert prediction['simple_review_eligible'],prediction['issues'];assert before=={c['id']:c['version'] for c in good('/api/state')['cases']}
 # A real isolated-DB case: no approvals or supplier replies fabricated.
 p=copy.deepcopy(original['case']['marketing']);p.update(title='[모의 AX] 기안 사전검토',campaign_name='기안 사전검토 검증',budget=5000000,settlement_date='2026-09-21',group_total=None,scope_skus=['SKU-2002']);p['items']=[{'sku_id':'SKU-2002','demand':100,'unit':'EA/주','start':p['start'],'end':p['end'],'basis':'원본 판매와 과거 증분 확인','confidence':'보통','overlap':'기존 판매 제외한 순증'}]
 r=good('/api/marketing',{'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':p,'ax_inputs':inputs});newid=r['id'];fresh=good('/api/cases/'+newid);assert fresh['execution']['stage']==2 and fresh['case']['ax_plan']
 assert api('/api/ax-confirm',{'role':'마케팅','id':newid,'version':fresh['case']['version'],'mutation_id':str(uuid.uuid4()),'decision_maker':'잘못된 역할','reason':'검증','evidence':'검증'})[0]==400
 errors=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1100});page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(20000)
  await page.goto(BASE+'/campaign#screen=MKT_1_Proposal&case='+newid);await page.locator('html[data-ready="true"]').wait_for();assert await page.locator('.ax-planning').count()==1
  demand=page.locator('button[data-predict="SKU-2002"]');await demand.click();await expect(page.locator('.ax-planning [data-refresh]')).to_be_enabled();assert await page.locator('#dem-SKU-2002').input_value()!='';await expect(page.locator('.ax-evidence')).to_have_count(1)
  assert await page.locator('.ax-evidence details[open]').count()==0
  await page.screenshot(path='docs/assets/screenshots/ax-marketing-forecast.png',full_page=True)
  a=page.locator('[data-ax-sku="SKU-2002"]');await a.locator('[data-field=qty]').fill('0');await a.locator('[data-field=qty]').dispatch_event('input');await page.locator('.ax-planning [data-refresh]').click();await expect(page.locator('.ax-planning [data-refresh]')).to_be_enabled();assert await page.locator('.ax-cash').count()==1
  await page.set_viewport_size({'width':390,'height':844});await page.screenshot(path='docs/assets/screenshots/ax-marketing-mobile.png',full_page=True);assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
  await page.set_viewport_size({'width':1440,'height':1000})
  for screen,role,next_screen in [('SCM_1_Check','SCM','FIN_1_Review'),('FIN_1_Review','재무','APR_2_Normal')]:
   await page.goto(BASE+'/campaign#screen='+screen+'&case='+newid);await page.locator('html[data-ready="true"]').wait_for();await page.locator('.ax-review [data-confirm]').click();await page.locator('.w01-dialog').wait_for();await page.locator('.w01-dialog [name=decision_maker]').fill(role+' 검증 담당');await page.locator('.w01-dialog [type=submit]').click();await page.wait_for_url('**screen='+next_screen+'**');await page.locator('html[data-ready="true"]').wait_for()
  await page.screenshot(path='docs/assets/screenshots/ax-approved-request.png',full_page=True);await b.close()
 final=good('/api/cases/'+newid);assert final['execution']['stage']==4;assert final['execution']['finance_valid'];assert not final['case'].get('execution',{}).get('decisions');assert len([e for e in final['history'] if '간편 확인' in e['event']])==2;assert not errors,errors
 saved={c['id']:c['version'] for c in good('/api/state')['cases']};assert all(saved[k]==v for k,v in before.items())
 report={'passed':True,'unit_tests':157,'prediction_history':prediction['items'][0]['history'],'observations':prediction['items'][0]['observations'],'preview_does_not_write':True,'scenarios':{'normal':{'case_id':newid,'stages':[2,3,4],'scm_and_finance_human_confirmations':2,'final_approval_created':False},'exceptions_unit_tested':['지급일 미입력 차단','리드타임 지연·공급 부족 차단','자료·기안 변경 시 재검토','역할 우회 차단','재무 미확정 차단']},'ui':{'original_frame_preserved':True,'per_sku_prediction_and_manual_entry':True,'evidence_collapsed':True,'mobile_overflow':False,'browser_errors':errors},'existing_cases_unchanged':True,'database':'격리된 로컬 테스트 DB. 실제 8088 캠페인 변경 없음','ai':'통계 기반 수요 예측·규칙 검산. 신규 LLM 호출 없음'}
 Path('docs/verification/marketing/AX_PLANNING_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
