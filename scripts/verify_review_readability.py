"""Read-only review presentation checks: no workflow writes or live GPT calls."""
import asyncio,json,urllib.request
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE='http://127.0.0.1:8088'
def state():
 with urllib.request.urlopen(BASE+'/api/state') as r:return json.load(r)
async def main():
 before=state();versions=[(c['id'],c['version']) for c in before['cases']];cid=next(c['id'] for c in before['cases'] if c['id']=='8ebf088a-1740-41c6-94b5-758a0d99cb81');errors=[];posts=[];screens=[];out=Path('docs/assets/screenshots');out.mkdir(parents=True,exist_ok=True)
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);p=await b.new_page(viewport={'width':1440,'height':1000});p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:posts.append(r.url) if r.method=='POST' and '/api/ax-planning' not in r.url else None)
  await p.goto(BASE+'/campaign#screen=SCM_1_Check&case='+cid+'&role='+__import__('urllib.parse',fromlist=['quote']).quote('마케팅'));await p.locator('html[data-ready=true]').wait_for();await p.locator('.review-summary').wait_for();assert await p.evaluate('role')=='마케팅';assert await p.locator('.review-saved .review-meta').count()==1;assert await p.locator('.review-saved details[open]').count()==0
  expected=await p.evaluate("details.case.scm.review.evidence");assert await p.locator('.review-saved').text_content() and [x.strip() for x in expected.splitlines() if x.strip()]==await p.locator('.review-saved details').last.locator('li').all_text_contents();await p.locator('.review-saved details').last.locator('summary').click();await expect(p.locator('.review-saved details').last).to_have_attribute('open','');assert await p.locator('#app input:not(:disabled),#app textarea:not(:disabled),#app select:not(:disabled)').count()==0;await p.locator('.review-saved details').last.locator('summary').click();await p.screenshot(path=str(out/'review-readability-readonly.png'))
  screens_to_check=['MKT_1_Proposal','MKT_2_Wait','SCM_1_Check','SCM_2_WaitApproval','FIN_1_Review','FIN_2_Wait','APR_1_CEO','APR_2_Normal','SCM_3_PO','SCM_4_WaitReply','SCM_5_Receipt','MKT_3_Hold','MKT_4_Close']
  for screen in screens_to_check:
   await p.goto(BASE+'/campaign#screen='+screen+'&case='+cid);await p.locator('html[data-ready=true]').wait_for();assert await p.locator('h1,h2').count()>0
   if screen=='SCM_1_Check':
    await expect(p.locator('.review-condition')).to_contain_text('현재 확인된 공급');assert await p.locator('.review-summary .review-table tbody tr').count()==2;assert (await p.locator('#s-reason').input_value()).count('정기 보충 계획을 반영하면')<=1;await p.locator('[aria-label="SCM 판단"]').scroll_into_view_if_needed();await p.screenshot(path=str(out/'review-readability-scm.png'));assert not await p.locator('.review-summary details').first.get_attribute('open')
   if screen=='FIN_1_Review':assert await p.locator('.review-summary').count()==1
   if screen=='APR_1_CEO':assert await p.locator('.approval-department .review-prose').count()==3
   await p.set_viewport_size({'width':390,'height':844});assert await p.evaluate('document.documentElement.scrollWidth<=innerWidth'),screen
   if screen=='SCM_1_Check':await p.screenshot(path=str(out/'review-readability-mobile.png'))
   await p.set_viewport_size({'width':1440,'height':1000});screens.append(screen)
  # Display-only hostile and nonstandard model output; never invokes GPT or workflow APIs.
  checks=await p.evaluate("""()=>{const raw='[요약]\\n- <img src=x onerror=alert(1)>\\n[위험]\\n- 재고 확인\\n[대안]\\n- 담당자 협의\\n[확인 질문]\\n- 날짜 확인\\n[근거]\\n- 원본 자료';const n=document.createElement('div');n.innerHTML=W01ReviewPresentation.ai(raw);return {sections:n.querySelectorAll('.review-ai-group').length,images:n.querySelectorAll('img').length,text:n.textContent,empty:W01ReviewPresentation.prose(' ')}}""");assert checks['sections']==5 and checks['images']==0;assert '<img src=x' in checks['text'];assert '미기록' in checks['empty'];assert not errors,errors;await b.close()
 assert [(c['id'],c['version']) for c in state()['cases']]==versions;assert not posts,posts
 report={'screens':screens,'screen_count':len(screens),'scm_data_table':True,'conditional_and_confirmed_supply_separate':True,'readonly_original_evidence_preserved':True,'full_evidence_expandable':True,'gpt_grouped_sections':5,'html_escaped':True,'mobile_overflow':False,'case_versions_unchanged':True,'no_paid_gpt_calls':True,'browser_errors':errors};Path('docs/verification/workflow/REVIEW_READABILITY_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
