"""Use original design controls and evidence dialogs to complete a real DB flow."""
import asyncio,json,os,uuid
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8087')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost','::1']:raise SystemExit('Local only')
async def ready(page,screen):await page.locator('html[data-ready="true"][data-screen="'+screen+'"]').wait_for(timeout=10000)
async def metadata(page,**more):
 d=page.locator('.w01-dialog')
 for k,v in {'decision_maker':'시안 검증 담당','reason':'실제 입력·현업 인계 검증','evidence':'격리 DB 모의 검증 근거',**more}.items():await d.locator('[name="'+k+'"]').fill(v)
async def change_role(page,role,target):
 await page.keyboard.press('Alt+m');d=page.get_by_role('dialog',name='업무 화면·기안 선택');await d.locator('[name=role]').select_option(role);await d.locator('[name=screen]').select_option(target);await d.locator('[type=submit]').click();await ready(page,target)
async def main():
 trace=[];errors=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox']);page=await browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.dismiss())
  await page.goto(BASE+'/#screen=MKT_1_Proposal');await ready(page,'MKT_1_Proposal');await page.get_by_role('button',name='새 캠페인 작성',exact=False).click()
  for key,value in {'p-title':'원본 UI 흐름 '+uuid.uuid4().hex[:6],'p-author':'마케팅 기안자','f-name':'원본 UI 기초 캠페인','f-start':'2026-07-13','f-end':'2026-07-19','f-req':'5000000','f-settle':'2026-09-21','f-dl':'2026-07-10'}.items():await page.locator('#'+key).fill(value)
  await page.get_by_label('퍼포먼스 광고',exact=True).check()
  for key,value in {'f-country':'국내','f-sns':'YouTube','f-fmt':'숏츠','f-sales':'자사몰','f-pl':'기초'}.items():await page.locator('#'+key).select_option(value)
  await page.locator('#dem-SKU-2002').fill('100')
  await page.get_by_role('button',name='기안 상신',exact=True).click();await metadata(page,performance_basis='신규 캠페인 성과 미확인',**{'basis-SKU-2002':'기간 순증 수요의 모의 가정'})
  await page.locator('.w01-dialog [type=submit]').click();await ready(page,'MKT_2_Wait');cid=(await page.evaluate('location.hash')).split('case=')[1];trace.append('원본 기안·제품라인·선택 수요 → DB 저장·마케팅 대기')
  await change_role(page,'SCM','SCM_1_Check');await page.locator('#s-owner').fill('SCM 원본 담당');await page.locator('#s-reason').fill('완료 4주·현재고 대조 · 추가 발주 없음')
  await page.locator('section[aria-label="SCM 판단"] label').filter(has_text='재고로 가능').locator('input[type=radio]').check()
  await page.get_by_role('button',name='대조 결과 전달',exact=True).click();await metadata(page);await page.locator('.w01-dialog [type=submit]').click();await ready(page,'SCM_2_WaitApproval');trace.append('원본 SCM 판단·확인 → 재무 인계·대기')
  await change_role(page,'재무','FIN_1_Review');await page.locator('#f-owner').fill('재무 원본 담당');await page.locator('#f-reason').fill('금액·시나리오·표본 범위 확인')
  await page.locator('label').filter(has_text='적용 시나리오의 하회 구간').locator('input[type=checkbox]').check();await page.locator('label').filter(has_text='약정별 판정을 확인했습니다').locator('input[type=checkbox]').check()
  await page.locator('section[aria-label="상신 의견"] label').filter(has_text='조건 없이 진행').locator('input[type=radio]').check()
  await page.locator('section[aria-label="상신 전 점검"] button').first.click();await metadata(page,alternatives='추가 발주 없음 · 다른 대안 불필요',performance_basis='신규 캠페인 표본 성과 없음',**{'basis-0':'단독 기안 500만원 · 표본 현금 합산 제외'})
  await page.locator('.w01-dialog [name=scenario]').select_option('exclude_pay');await page.locator('.w01-dialog [type=submit]').click();await ready(page,'FIN_2_Wait');trace.append('원본 재무 확인·의견 → 검토 상신·대기')
  await change_role(page,'승인권자','APR_2_Normal');await page.locator('#a-owner').fill('마케팅팀장 원본 담당')
  await page.locator('section[aria-label="결정"] label').filter(has_text='승인').filter(has_not_text='조건부').locator('input[type=radio]').check()
  await page.get_by_role('button',name='결정 확정',exact=True).click();await metadata(page,decision_maker='마케팅팀장 원본 담당');await page.locator('.w01-dialog [type=submit]').click();await page.locator('.w01-layer').wait_for(state='detached');await ready(page,'APR_2_Normal');trace.append('원본 평시 승인권자 → 약정별 사람 승인')
  await change_role(page,'마케팅','MKT_4_Close');await page.locator('#m-owner').fill('마케팅 정리 담당');await page.locator('label').filter(has_text='상대방에 계약 확정 통보').locator('input[type=checkbox]').check();await page.locator('label').filter(has_text='기안 · 결재 · 발주 · 회신 기록이 서로 맞는지').locator('input[type=checkbox]').check()
  await page.get_by_role('button',name='일정 확정 · 기록 정리 완료',exact=True).click();await metadata(page);await page.locator('.w01-dialog [type=submit]').click();await ready(page,'MKT_2_Wait');assert '회차 종료' in await page.locator('body').inner_text();trace.append('원본 일정표·연결 기록·통보 확인 → 회차 종료')
  await browser.close()
 assert not errors,errors
 result={'passed':True,'case_id':cid,'trace':trace,'errors':errors,'scope':'원본 화면 컨트롤과 근거 확인 대화상자로 실제 로컬 DB 흐름 검증'}
 Path('docs/verification/screen-reviews/14-original-role-flow.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
