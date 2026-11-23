"""Mock-provider integration only; isolated local server, never main preview or paid calls."""
import asyncio,json,os,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('W01_GPT_TEST_BASE_URL','').rstrip('/');u=urlparse(BASE)
if u.scheme!='http' or u.hostname not in ['127.0.0.1','localhost'] or u.port!=8089:raise RuntimeError('GPT 모의 테스트 서버 8089만 허용합니다.')
TEST_KEY='sk-test-browser-placeholder'
def api(path,body=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req) as r:return json.load(r)
async def main():
 before=api('/api/state');versions=[(c['id'],c['version']) for c in before['cases']];cid=before['cases'][0]['id'];report={};errors=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);p=await b.new_page(viewport={'width':1440,'height':1000});p.on('pageerror',lambda e:errors.append(str(e)))
  await p.goto(BASE+'/admin#tab=prompts&role=SCM');await p.locator('#gpt-settings').wait_for();await p.locator('#gpt-settings [name=api_key]').fill(TEST_KEY);await p.locator('#gpt-settings [name=enabled]').select_option('true');await p.get_by_role('button',name='연결 설정 저장',exact=True).click();await expect(p.locator('#gpt-settings [name=api_key]')).to_have_value('');await expect(p.locator('#gpt-test')).to_be_enabled()
  public=api('/api/ai-settings');assert public['configured'] and TEST_KEY not in json.dumps(public);assert TEST_KEY not in json.dumps(api('/api/state'))
  form=p.locator('[data-prompt=scm] form');prompt=await form.locator('[name=prompt]').input_value();assert '개조식' in prompt;await form.locator('[name=prompt]').fill(prompt+'\n테스트 전용 지침');await form.locator('[name=decision_maker]').fill('SCM 시연 담당');await form.locator('[name=reason]').fill('개조식 검토 지침');await form.locator('[name=evidence]').fill('단계별 근거');await form.get_by_role('button',name='프롬프트 저장').click();await expect(p.locator('[data-prompt=scm] [name=prompt]')).to_have_value(prompt+'\n테스트 전용 지침')
  await p.locator('#gpt-test').click();await expect(p.locator('#gpt-status')).to_have_text('OpenAI 연결을 확인했습니다.');await p.screenshot(path='docs/assets/screenshots/gpt-admin-desktop.png',full_page=True)
  await p.goto(BASE+'/campaign#screen=SCM_1_Check&case='+cid);await p.locator('html[data-ready=true]').wait_for();await p.locator('label').filter(has_text='재고로 가능').first.click();assert await p.locator('label').filter(has_text='정기 보충 확인 필요').count()==0
  reason=await p.locator('#s-reason').input_value();print('SCM reason',reason[:100]);assert '정기 보충' in reason
  panel=p.locator('#gpt-stage-review');await panel.get_by_role('button',name='검토 초안 생성',exact=True).click();await expect(panel.locator('.ai-review-output')).to_contain_text('테스트 전용 지침이 적용');assert '미검증' not in await p.locator('#s-reason').input_value();await panel.get_by_role('button',name='검토 의견에 반영').click();await expect(p.locator('#s-reason')).to_have_value(__import__('re').compile('.*모의 GPT.*',__import__('re').S));await p.locator('#s-reason').fill('담당자 직접 의견');await expect(panel.get_by_role('button',name='검토 의견에 반영')).to_be_disabled()
  await p.screenshot(path='docs/assets/screenshots/gpt-scm-desktop.png',full_page=True)
  tested=[]
  for screen in ['FIN_1_Review','APR_2_Normal','SCM_3_PO','SCM_5_Receipt','MKT_4_Close']:
   page=await b.new_page();page.on('pageerror',lambda e:errors.append(str(e)));await page.goto(BASE+'/campaign#screen='+screen+'&case='+cid);await page.locator('html[data-ready=true]').wait_for();panel=page.locator('#gpt-stage-review');await panel.get_by_role('button',name='검토 초안 생성',exact=True).click();await expect(panel.locator('.ai-review-output')).to_contain_text('모의 GPT',timeout=15000);tested.append(screen);await page.close()
  m=await b.new_page();m.on('pageerror',lambda e:errors.append(str(e)));await m.goto(BASE+'/campaign#screen=MKT_1_Proposal');await m.locator('html[data-ready=true]').wait_for();await m.evaluate("logic.state.f={...logic.state.f,title:'[모의] GPT 기안',name:'GPT 기안',media:['오프라인'],country:'국내',sales:'자사몰',pl:'색조',start:'2026-11-16',end:'2026-11-20',req:''};logic.state.pick={'SKU-3001':true};logic.state.dem={};dirty=true;render()")
  await expect(m.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=15000);panel=m.locator('#gpt-stage-review');await panel.get_by_role('button',name='검토 초안 생성',exact=True).click();await expect(panel.locator('.ai-review-output')).to_contain_text('모의 GPT');await m.set_viewport_size({'width':390,'height':844});assert await m.evaluate('document.documentElement.scrollWidth<=innerWidth');await m.screenshot(path='docs/assets/screenshots/gpt-marketing-mobile.png',full_page=True)
  state=api('/api/state');assert [(c['id'],c['version']) for c in state['cases']]==versions;assert TEST_KEY not in json.dumps(state);assert not errors,errors
  settings=api('/api/ai-settings');api('/api/ai-settings',{'role':'SCM','version':settings['version'],'clear_key':True});assert not api('/api/ai-settings')['configured']
  report={'provider':'OpenAI Responses API · 외부 응답 모의','api_key_never_returned':True,'api_key_not_in_audit':True,'prompt_runtime_applied':True,'scm_regular_under_stock_possible':True,'auto_scm_reason':True,'all_seven_stages':True,'stale_apply_blocked':True,'case_versions_unchanged':True,'mobile_overflow':False,'errors':errors,'real_paid_call':False};Path('docs/verification/administration/GPT_REVIEW_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));await b.close()
asyncio.run(main())
