"""Real form input / role handoff in Chromium on a disposable local DB."""
import asyncio,json,os,uuid
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8087')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost','::1']:raise SystemExit('Local only')
async def main():
 errors=[];trace=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=True,args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('dialog',lambda d:d.dismiss())
  await page.goto(BASE+'/#screen=MKT_1_Proposal');await page.locator('#submit-plan').wait_for()
  fields={'title':'브라우저 역할 흐름 '+uuid.uuid4().hex[:5],'campaign_name':'신규 기초 캠페인','author':'기안 브라우저','purpose':'실제 입력으로 인계 검증','target':'기초','sales_channel':'자사몰','sns_channel':'YouTube','sns_format':'숏츠','start':'2026-07-13','end':'2026-07-19','budget':'5000000','settlement_date':'2026-09-21','contract_deadline':'2026-07-10','performance_unknown_reason':'신규 시나리오 실적 미확인'}
  for k,v in fields.items():await page.locator('#mkt-'+k).fill(v)
  await page.locator('[data-media="퍼포먼스"]').check();await page.locator('#sku-pick').select_option('SKU-2002');await page.locator('#add-item').click()
  await page.locator('#item-0-demand').fill('100');await page.locator('#item-0-basis').fill('브라우저 검증 순증 가정')
  await page.locator('#submit-plan').click();await page.wait_for_url('**screen=MKT_2_Wait**');await page.locator('#wait-note').wait_for();trace.append('마케팅 기안 제출 → 마케팅 대기')
  cid=(await page.evaluate('location.hash')).split('case=')[1]
  await page.locator('#role-choice').select_option('SCM');await page.locator('#scm-handoff').wait_for()
  for k in ['decision_maker','reason','evidence']:await page.locator('#scm--'+k).fill('SCM 브라우저 확인 근거')
  await page.locator('[data-direction="재고로 가능"]').click();await page.locator('#scm-0-supply_result').select_option('가능');await page.locator('#scm-0-procurement').select_option('추가 조달 없음')
  await page.locator('#scm-handoff').click();await page.wait_for_url('**screen=SCM_2_WaitApproval**');await page.locator('#wait-note').wait_for();trace.append('SCM 검토·인계 → SCM 결재 대기')
  await page.locator('#role-choice').select_option('재무');await page.locator('#fin-decision_maker').wait_for()
  for k in ['decision_maker','reason','evidence','opinion','alternatives','performance_basis']:await page.locator('#fin-'+k).fill('재무 브라우저 근거 · 추가 발주 없음')
  await page.locator('[data-fin-action="submit"]').click();await page.wait_for_url('**screen=FIN_2_Wait**');await page.locator('#wait-note').wait_for();trace.append('재무 검토·상신 → 재무 결재 대기')
  await page.locator('#role-choice').select_option('승인권자');await page.locator('#apr-submit').wait_for();assert 'APR_2_Normal' in page.url
  for k in ['owner','reason','evidence']:await page.locator('#apr-'+k).fill('마케팅팀장 브라우저 검토')
  await page.locator('#apr-0-decision').select_option('승인');await page.locator('#apr-submit').click();await page.get_by_text('저장 완료 · decide',exact=True).wait_for();await page.locator('#apr-submit').wait_for();trace.append('평시 승인권자 분기 · 약정 승인')
  await page.locator('#role-choice').select_option('마케팅');await page.wait_for_url('**screen=MKT_1_Proposal**');await page.locator('#submit-plan').wait_for();await page.locator('#screen-choice').select_option('MKT_4_Close');await page.locator('#close-submit').wait_for()
  for k in ['owner','reason','evidence']:await page.locator('#close-'+k).fill('마케팅 일정표 기록 확인')
  await page.locator('#close-notified').check();await page.locator('#close-submit').click();await page.wait_for_url('**screen=MKT_2_Wait**');await page.locator('#wait-note').wait_for()
  assert '회차 종료' in await page.locator('body').inner_text();trace.append('마케팅 일정표·통보 기록 → 회차 종료')
  await page.screenshot(path='docs/assets/screenshots/role-flow-complete.png',full_page=True)
  await b.close()
 assert not errors,errors
 result={'passed':True,'case_id':cid,'trace':trace,'browser_errors':errors,'mode':'격리 DB · 사람 입력 모의'}
 Path('docs/verification/screen-reviews/13-screen-role-flow.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
