"""Optional Playwright verification of the user-supplied design baseline. Local test DB only."""
import json,os,uuid
from urllib.parse import urlparse
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8080')
if urlparse(BASE).hostname not in ['127.0.0.1','localhost'] or urlparse(BASE).scheme!='http':raise SystemExit('Local isolated test server only')
Path('/tmp/w01-verify').mkdir(exist_ok=True)
TITLE='시안 기준 기안 검증 '+str(uuid.uuid4())[:8]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(BASE,wait_until='networkidle');page.wait_for_selector('#screen-choice')
 print('root',page.title(),'flow',page.locator('.stage-link').count())
 assert page.locator('.stage-link').count()==7
 assert page.locator('#shell').count()==0
 page.screenshot(path='/tmp/w01-verify/source-overview.png',full_page=True)
 for i in range(2,9):
  page.select_option('#screen-choice',str(i));page.wait_for_function('() => document.querySelector("#screen-choice")?.value === "'+str(i)+'"')
  if i==2:
   assert page.locator('#scm-handoff').count()==1
  else:
   assert '검토 대기 · 첨부 시안의 예시 화면' in page.locator('#app').inner_text()
   assert page.locator('main button:enabled').count()==0,(i,'enabled action')
  assert '{{' not in page.locator('#app').inner_text()
  print('page',i,'pass')
 page.goto(BASE+'/#screen=1',wait_until='networkidle');page.wait_for_selector('#p-title')
 assert page.locator('dialog').count()==0
 assert page.locator('section[aria-label="개요 (목적·배경)"]').count()==1
 page.fill('#p-title',TITLE)
 page.fill('#p-name','마케팅 시연 담당자')
 page.fill('#p-purpose','시안의 업무 배치와 원본 근거를 유지하는 검증')
 page.fill('#p-start','2026-07-13');page.fill('#p-end','2026-07-19')
 page.fill('#p-target','기초 제품 구매 고객');page.fill('#p-how','라이브 집행 검토')
 page.fill('#extra-performance_unknown_reason','성과·비용 범위 확인 요청')
 for sku in ['SKU-2001','SKU-2002','SKU-2003']:
  page.fill('#dem-'+sku,'700');page.fill('#basis-'+sku,'시연용 주간 순증 가정')
 assert '4,079.25' in page.locator('#app').inner_text()
 page.screenshot(path='/tmp/w01-verify/source-marketing.png',full_page=True)
 page.click('#save-marketing');page.get_by_text('기안을 서버 DB에 저장했습니다.',exact=True).wait_for()
 assert 'case=' in page.url
 # Original attachment controls now upload real bytes, not a local toggle.
 page.get_by_role('button',name='집행 비용 견적서',exact=False).click()
 page.set_input_files('input[type=file]',{'name':'source-ui-proof.txt','mimeType':'text/plain','buffer':b'source design real attachment'})
 page.get_by_role('button',name='첨부 저장',exact=True).click()
 page.get_by_role('link',name='source-ui-proof.txt',exact=False).wait_for()
 # Invalid file upload must not mark an attachment as saved.
 page.get_by_role('button',name='예상 매출액 분석표',exact=False).click()
 page.set_input_files('input[type=file]',{'name':'bad.exe','mimeType':'application/octet-stream','buffer':b'not supported'})
 page.get_by_role('button',name='첨부 저장',exact=True).click()
 page.locator('.design-overlay [role=alert]').filter(has_text='파일만 첨부').wait_for()
 page.locator('.design-overlay [type=button]').click()

 page.locator('button',has_text='기안 제출 · SCM 검토 요청').click()
 page.get_by_text('기안 저장 · SCM 검토 요청을 기록했습니다. 승인·발주·지급이 아닙니다.',exact=True).wait_for()
 page.select_option('#screen-choice','0');page.wait_for_selector('.stage-link')
 assert '② SCM' in page.locator('section[aria-label="캠페인 요약"]').inner_text()
 print('saved and handoff',page.url)
 before=page.locator('section[aria-label="캠페인 요약"]').inner_text()
 page.locator('.stage-link').nth(3).click();page.get_by_text('검토 대기 · 첨부 시안의 예시 화면',exact=False).wait_for()
 assert page.locator('nav[aria-label="현업 절차 단계"] a[aria-current=step]').inner_text().startswith('②')
 page.select_option('#screen-choice','0');page.wait_for_selector('.stage-link')
 assert page.locator('section[aria-label="캠페인 요약"]').inner_text()==before
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 # Empty and error states are displayed without fabricating a campaign.
 baseline=page.request.get(BASE+'/api/state').json()
 page.route('**/api/state',lambda route:route.fulfill(json={**baseline,'cases':[]}))
 page.goto(BASE,wait_until='networkidle');page.get_by_text('캠페인 기안 없음',exact=True).wait_for()
 page.unroute('**/api/state')
 page.route('**/api/state',lambda route:route.abort())
 page.reload(wait_until='networkidle');page.get_by_text('화면을 불러오지 못했습니다.',exact=True).wait_for()
 page.unroute('**/api/state');page.click('#retry');page.wait_for_selector('.stage-link')
 assert not errors,errors
 Path('docs/verification/screen-reviews/ui-reset-results.json').write_text(json.dumps({'base':BASE,'browser':'Chromium','checks':['첨부 시안의 9개 페이지 전환','시안의 7단계 플로우 유지','기존 사이드바·모달 기안서 제거','미검토 페이지 예시 표시·처리 버튼 비활성','① 원본 페이지 구성 유지','완료 4주 평균 4079.25 재현','제품 3종 별도 수요·근거 저장','실제 파일 첨부·미지원 파일 오류','① 제출 후 실제 ② 단계 표시','다른 담당자 화면 열람 후 현재 단계 불변','390px 가로 넘침 없음','자료 없음·통신 오류·재시도 상태'],'page_errors':errors,'source_of_state':'로컬 검증용 PostgreSQL','external_operations':'실행하지 않음'},ensure_ascii=False,indent=2)+'\n')
 b.close();print('All source UI checks passed')
