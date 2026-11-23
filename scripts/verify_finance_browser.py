import json
from pathlib import Path
from playwright.sync_api import sync_playwright
result=json.loads(Path('docs/verification/screen-reviews/03-finance-results.json').read_text());cid=result['case_id']
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8086/#screen=3&case='+cid);page.wait_for_selector('#fin-opinion')
 assert page.locator('#fin-feedback').count()==1
 assert page.get_by_text('금액·현금 영향·승인권한을 확인했나요?',exact=True).count()==1
 assert '12,660' not in page.locator('section[aria-label="현금 재전망"]').inner_text()
 page.fill('#fin-opinion','브라우저 검증 재무 의견');page.click('[data-fin-action=save]');page.locator('#fin-feedback').filter(has_text='저장 완료').wait_for()
 page.reload();page.wait_for_selector('#fin-opinion');assert page.input_value('#fin-opinion')=='브라우저 검증 재무 의견'
 page.click('[data-fin-action=preview]');page.locator('#fin-feedback').filter(has_text='현재 입력').wait_for()
 assert not errors,errors
 desktop_overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
 page.screenshot(path='docs/assets/screenshots/03-finance-desktop.png',full_page=True)
 page.set_viewport_size({'width':390,'height':844});page.screenshot(path='docs/assets/screenshots/03-finance-mobile.png',full_page=True)
 mobile_overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
 Path('docs/verification/screen-reviews/03-finance-browser.json').write_text(json.dumps({'passed':not errors and not desktop_overflow and not mobile_overflow,'errors':errors,'desktop_overflow':desktop_overflow,'mobile_overflow':mobile_overflow,'checks':['real render','persistent form save and reload','preview','desktop and mobile overflow']},ensure_ascii=False,indent=2)+'\n')
 print('browser',errors,'overflow',desktop_overflow,mobile_overflow);browser.close()
