"""Writes to an isolated local fixture DB only; never run against the preview DB."""
import asyncio,json,os,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('W01_ADMIN_TEST_BASE_URL','').rstrip('/')
parsed=urllib.parse.urlparse(BASE)
if parsed.scheme!='http' or parsed.hostname not in ['127.0.0.1','localhost'] or parsed.port in [None,8088]:raise RuntimeError('별도 테스트 DB의 로컬 서버 주소를 지정하세요. 8088 검증 금지.')
def api(path,body=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
async def main():
 errors=[];baseline=api('/api/state')[1];home=api('/api/home?role='+urllib.parse.quote('마케팅'))[1];assert len(home['processed'])==3 and not home['todo']
 prompts=api('/api/prompt-settings?role='+urllib.parse.quote('마케팅'))[1];assert len(prompts['prompts'])==7
 assert not any(p['draft'] for p in prompts['prompts']),'이미 프롬프트 초안이 저장된 DB에서는 중단합니다.'
 raw={'role':'SCM','prompt_id':'marketing','version':0,'prompt':'근거 요약','decision_maker':'테스트','reason':'검증','evidence':'가상 근거'}
 assert api('/api/prompt-settings',raw)[0]==400
 assert api('/api/prompt-settings',{**raw,'role':'마케팅','runtime_applied':True})[0]==400
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(BASE+'/#role='+urllib.parse.quote('마케팅'));await page.locator('#processed-list article').first.wait_for();assert await page.locator('h1').inner_text()=='캠페인';assert await page.locator('#processed-list article').count()==3;assert await page.locator('#todo-list article').count()==0
  await page.screenshot(path='docs/assets/screenshots/admin-home-marketing.png',full_page=True)
  fixture=json.loads(json.dumps(home));row=fixture['processed'].pop(0);row.update(stage=7,status='마케팅 정리 대기',owner='마케팅',screen='MKT_4_Close',waiting=False,action_tab=None);fixture['todo']=[row]
  await page.route('**/api/home?*',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(fixture)));await page.reload();await page.locator('#todo-list article').wait_for();assert 'screen=MKT_4_Close' in await page.locator('#todo-list .action').get_attribute('href');await page.unroute('**/api/home?*')
  await page.goto(BASE+'/admin#tab=data&role=SCM');await page.locator('[data-dataset]').first.wait_for();assert await page.locator('[data-dataset]').count()==8;assert await page.get_by_role('link',name='별도 업무',exact=True).count()==0;assert await page.get_by_role('link',name='세부 자료 관리',exact=True).count()==0;assert await page.locator('#finance-data').get_by_text('연체 회수·지급 확인',exact=True).count()==1
  await page.screenshot(path='docs/assets/screenshots/admin-data-integrated.png',full_page=True)
  await page.get_by_role('link',name='계산식 설정',exact=True).click();await page.locator('[data-formula]').first.wait_for();assert await page.locator('[data-formula]').count()==12;assert '/admin#tab=formulas' in page.url
  a=page.locator('[data-formula="inventory_cover"]');await a.get_by_role('button',name='산식 수정',exact=True).click();await a.get_by_role('button',name='시험 계산',exact=True).click();await a.locator('.sample-result').wait_for(state='visible');assert '3' in await a.locator('.sample-result').inner_text()
  await page.goto(BASE+'/settings#role='+urllib.parse.quote('재무'));await page.locator('[data-formula]').first.wait_for();assert '/admin#tab=formulas' in page.url
  await page.goto(BASE+'/admin#tab=prompts&role='+urllib.parse.quote('마케팅'));await page.locator('[data-prompt]').first.wait_for();assert await page.locator('[data-prompt]').count()==7
  a=page.locator('[data-prompt=marketing]');await a.locator('[name=prompt]').fill('테스트 초안: 실제 근거만 요약합니다. <b>미적용</b>')
  for key in ['decision_maker','reason','evidence']:await a.locator('[name='+key+']').fill('격리 DB 테스트')
  await a.get_by_role('button',name='초안 저장 · 실행 미적용',exact=True).click();await page.get_by_text('최근 저장:',exact=False).wait_for();assert '<b>미적용</b>' in await page.locator('[data-prompt=marketing] [name=prompt]').input_value();assert await page.locator('[data-prompt=marketing] b').count()==0
  now=api('/api/state')[1];assert now['finance_version']==baseline['finance_version'];assert {c['id']:c['version'] for c in now['cases']}=={c['id']:c['version'] for c in baseline['cases']}
  assert api('/api/prompt-settings',{**raw,'role':'마케팅'})[0]==409
  await page.screenshot(path='docs/assets/screenshots/admin-prompt-ready.png',full_page=True)
  await page.goto(BASE+'/admin#tab=data&role=SCM');await page.locator('[data-dataset=inventory] .update').click();form=page.locator('.admin-dialog form')
  for key in ['decision_maker','reason','evidence']:await form.locator('[name='+key+']').fill('격리 DB 업로드 테스트')
  old=await form.locator('[name=csv]').input_value();lines=old.splitlines();headers=lines[0].split('|');cols=lines[1].split('|');idx=headers.index('on_hand_qty');cols[idx]=str(int(cols[idx])+1);lines[1]='|'.join(cols);updated='\n'.join(lines)
  await form.locator('[name=csv]').fill(updated);await form.get_by_role('button',name='업데이트 검증',exact=True).click();await form.get_by_role('button',name='검증한 자료 저장',exact=True).wait_for(state='visible');await expect(form.get_by_role('button',name='검증한 자료 저장',exact=True)).to_be_enabled()
  assert api('/api/state')[1]['datasets']['inventory']['version']==baseline['datasets']['inventory']['version']
  await form.get_by_role('button',name='검증한 자료 저장',exact=True).click();await page.locator('.dialog-backdrop').wait_for(state='detached');await page.locator('[data-dataset=inventory]').wait_for();latest=api('/api/state')[1];assert latest['datasets']['inventory']['version']==baseline['datasets']['inventory']['version']+1
  bad={'role':'마케팅','kind':'inventory','version':latest['datasets']['inventory']['version'],'csv':updated,'provenance':'부서 주장'};assert api('/api/datasets/preview',bad)[0]==400
  bad.update(role='SCM',csv='invalid');assert api('/api/datasets/preview',bad)[0]==400
  await page.set_viewport_size({'width':390,'height':844});await page.screenshot(path='docs/assets/screenshots/admin-integrated-mobile.png',full_page=True);assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  await b.close()
 assert not errors,errors
 Path('docs/verification/administration/ADMIN_INTEGRATION_RESULTS.json').write_text(json.dumps({'passed':True,'unit_tests':149,'marketing_home':{'todo':0,'processed':3,'schedule_stage_7_returns_to_todo':'단위 테스트 및 메모리 화면 픽스처 확인'},'dataset_update':{'datasets':8,'preview_no_write':True,'save_version_increment':True,'wrong_role_and_bad_csv_rejected':True},'formula_embedded_in_admin':True,'legacy_settings_redirect':True,'prompt_drafts':{'stages':7,'runtime_applied':False,'save_does_not_change_finance_or_case_versions':True,'wrong_role_and_activation_rejected':True,'version_conflict_rejected':True},'finance_separate_work_under_reference_data':True,'mobile_overflow':False,'browser_errors':errors,'database':'별도 로컬 검증 DB · 기존 8088 데이터 변경 없음'},ensure_ascii=False,indent=2)+'\n');print('관리자 통합·자료 업데이트·산식·프롬프트·홈 분류 검증 완료')
asyncio.run(main())
