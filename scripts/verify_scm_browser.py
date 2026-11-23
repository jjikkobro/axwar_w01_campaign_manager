"""SCM UI check. Requires Playwright and a dedicated local test server."""
import json,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from scripts.verify_scm import create,call,get,BASE
if urlparse(BASE).hostname not in ['127.0.0.1','localhost']:raise SystemExit('Local only')
Path('/tmp/w01-verify').mkdir(exist_ok=True)
with sync_playwright() as p:
 cid,_=create()
 b=p.chromium.launch(headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':1440,'height':1000})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(BASE+'/#screen=2&case='+cid,wait_until='networkidle');page.wait_for_selector('#scm-handoff')
 assert page.locator('section[aria-label="재고·입고표 대조표"]').count()==1
 assert 'SPO-0006' in page.locator('#app').inner_text()
 assert '4,319' in page.locator('#app').inner_text()
 assert '6,659' in page.locator('#app').inner_text()
 page.fill('#scm--decision_maker','SCM 브라우저 시연 담당');page.fill('#scm--reason','기간 이행 가능성과 보충 검토를 분리')
 page.fill('#scm--evidence','원본 재고·주간 판매·기안 수요 가정')
 page.select_option('#scm-0-supply_result',label='가능');page.click('[data-direction="재고로 가능"]')
 page.fill('#scm-0-target_qty','22000');page.fill('#scm-0-target_basis','설명용 목표 수량')
 page.click('#scm-preview');page.get_by_text('현재 입력으로 계산했습니다. 저장·인계·승인이 아닙니다.',exact=True).wait_for()
 assert '1,529' in page.locator('.scm-proposal-result').inner_text()
 assert '16,000' in page.locator('.scm-proposal-result').inner_text()
 page.click('#scm-save');page.get_by_text('SCM 검토를 저장했습니다. 단계는 진행하지 않았습니다.',exact=True).wait_for()
 assert get(cid)['case']['marketing_stage']=='SCM 검토 요청'
 page.click('#scm-attach');page.set_input_files('input[type=file]',{'name':'scm-proof.txt','mimeType':'text/plain','buffer':b'SCM mock evidence'})
 page.get_by_role('button',name='첨부 저장',exact=True).click();page.locator('.design-overlay').wait_for(state='detached');page.wait_for_selector('#scm-handoff')
 page.screenshot(path='/tmp/w01-verify/scm-screen.png',full_page=True)
 page.click('#scm-handoff');page.get_by_text('③ 재무 확인 작업과 미승인 인계 패킷을 저장했습니다.',exact=True).wait_for()
 assert get(cid)['case']['marketing_stage']=='재무 검토 요청'
 assert get(cid)['case']['scm']['finance_packet']['documents'][0]['name']=='scm-proof.txt'
 page.select_option('#screen-choice','0');page.wait_for_selector('.stage-link');assert '③ 재무' in page.locator('section[aria-label="캠페인 요약"]').inner_text()
 page.select_option('#screen-choice','2');page.wait_for_selector('#scm-handoff')
 assert page.locator('nav[aria-label="현업 절차 단계"] a[aria-current=step]').inner_text().startswith('③')
 page.reload(wait_until='networkidle');page.wait_for_selector('#scm-handoff')
 assert page.input_value('#scm--decision_maker')=='SCM 브라우저 시연 담당'
 # Record an unknown reply. It must not add supply or keep prior handoff valid.
 box=page.locator('[data-po="SPO-0006"]');box.locator('summary').click()
 box.locator('[data-receipt=decision_maker]').fill('공급 회신 시연 담당')
 box.locator('[data-receipt=reason]').fill('공급 일정은 아직 미확인')
 box.locator('[data-receipt=evidence]').fill('모의 미확인 회신')
 box.locator('[data-save-receipt]').click()
 page.get_by_text('공급 회신을 기록하고 재계산했습니다. 이전 인계는 재검토 대상입니다.',exact=True).wait_for()
 assert get(cid)['case']['marketing_stage']=='SCM 재검토 필요'
 assert not get(cid)['case']['scm']['review']['valid']
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.screenshot(path='/tmp/w01-verify/scm-mobile.png',full_page=True)
 assert not errors,errors
 Path('docs/verification/screen-reviews/02-scm-browser.json').write_text(json.dumps({'base':BASE,'browser':'Chromium','checks':['시안 ② 섹션 유지','실제 기존 PO·완료 4주·기간 재고 표시','목표량→원본 권고량→MOQ 계산 갱신','검토 저장은 단계 유지','명시적 인계 후 ③ 표시','다른 페이지 열람·새로고침 후 상태 보존','미확인 공급 회신 후 인계 재검토','390px 가로 넘침 없음'],'errors':errors,'case_id':cid,'provenance':'격리 로컬 DB · 모의 기안/회신'},ensure_ascii=False,indent=2)+'\n')
 b.close();print('SCM browser checks passed')
