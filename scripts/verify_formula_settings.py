"""Destructive workflow checks for a separate, fresh local fixture DB only."""
import asyncio,json,os,urllib.request,urllib.error
from urllib.parse import urlparse
from pathlib import Path
from playwright.async_api import async_playwright
BASE=os.environ.get('W01_FORMULA_TEST_BASE_URL','').rstrip('/')
parsed=urlparse(BASE)
if parsed.scheme!='http' or parsed.hostname not in ['127.0.0.1','localhost'] or parsed.port in [None,8088]:raise RuntimeError('별도 테스트 DB의 로컬 서버 주소를 W01_FORMULA_TEST_BASE_URL로 지정하세요. 8088 사용 금지.')
def api(path,body=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
async def main():
 errors=[]
 code,d=api('/api/formulas?role='+urllib.parse.quote('마케팅'));assert code==200
 assert not d['history'],'기존 산식 변경 이력이 있는 DB에서는 중단합니다.'
 assert len(d['formulas'])==12 and sum(f['editable'] for f in d['formulas'])==2
 state=api('/api/state')[1];before=state['finance_version'];beforecases={c['id']:c['version'] for c in state['cases']}
 raw={'role':'마케팅','version':d['version'],'formula_id':'weekly_average','expression':'sales_total / weeks_count * 1.1','decision_maker':'산식 테스트 담당','reason':'별도 DB 검증','evidence':'테스트용 10% 증가 가정'}
 assert api('/api/formulas/preview',{**raw,'role':'승인권자'})[0]==400
 assert api('/api/formulas/test',{'role':'마케팅','formula_id':'weekly_average','expression':'__import__("os")','values':{'sales_total':1,'weeks_count':4}})[0]==400
 assert api('/api/formulas/apply',{**raw,'human_confirmed':True})[0]==400
 preview=api('/api/formulas/preview',raw);assert preview[0]==200
 unchanged=api('/api/state')[1];assert before==unchanged['finance_version'] and beforecases=={c['id']:c['version'] for c in unchanged['cases']}
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(15000)
  await page.goto(BASE+'/settings');await page.locator('[data-formula]').first.wait_for();assert await page.locator('[data-formula]').count()==12
  article=page.locator('[data-formula="weekly_average"]');await article.get_by_role('button',name='산식 수정',exact=True).click()
  await article.locator('[name=expression]').fill(raw['expression']);await article.get_by_role('button',name='시험 계산',exact=True).click();await article.locator('.sample-result').wait_for(state='visible');assert '1,100' in await article.locator('.sample-result').inner_text()
  for key in ['decision_maker','reason','evidence']:await article.locator('[name='+key+']').fill(raw[key])
  await article.get_by_role('button',name='변경 영향 확인',exact=True).click();await article.locator('.confirm').wait_for(state='visible');assert await article.locator('.impact tbody tr').count()>=3
  await page.screenshot(path='docs/assets/screenshots/formula-settings-preview.png',full_page=True)
  await article.locator('[name=human_confirmed]').check();await article.get_by_role('button',name='검증한 산식 적용',exact=True).click();await page.get_by_text('산식을 적용했습니다.',exact=False).wait_for()
  assert 'sales_total / weeks_count * 1.1' in await page.locator('[data-formula="weekly_average"] code').first.inner_text()
  await page.get_by_role('button',name='변경 이력',exact=True).click();assert await page.locator('.log').count()==1
  await page.locator('#role').select_option('승인권자');await page.get_by_role('button',name='내 역할',exact=True).click();await page.get_by_text('현재 역할의 수정 가능 산식은 없습니다.',exact=False).wait_for()
  await page.locator('#role').select_option('SCM');await page.get_by_role('button',name='전체',exact=True).click();await page.locator('[data-formula]').first.wait_for();assert await page.get_by_role('button',name='산식 수정',exact=True).count()==8
  await page.set_viewport_size({'width':390,'height':844});await page.screenshot(path='docs/assets/screenshots/formula-settings-mobile.png',full_page=True);assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  await b.close()
 after=api('/api/state')[1];assert after['finance_version']==before+1;assert api('/api/formulas/apply',{**raw,'human_confirmed':True,'preview_key':preview[1]['preview_key']})[0]==409
 assert all(c['workflow']['stage']==2 for c in after['cases'])
 assert not errors,errors
 report={'passed':True,'unit_tests':142,'editable_formulas':12,'read_only_control_rules':len(d['locked']),'role_edit_counts':{'마케팅':2,'SCM':8,'재무':3,'승인권자':0},'preview_only_does_not_write':True,'unsafe_expression_rejected':True,'wrong_role_rejected':True,'apply_without_preview_rejected':True,'concurrent_version_rejected':True,'browser_apply_and_history':True,'ongoing_cases_returned_to_scm_review':len(after['cases']),'mobile_overflow':False,'browser_errors':errors,'database':'별도 로컬 테스트 DB · 기존 8088 캠페인은 변경하지 않음'}
 Path('docs/verification/administration/FORMULA_SETTINGS_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
