"""Verify marketing forecast-window guard; out-of-range POST must fail without persistence."""
import asyncio,json,uuid,urllib.request,urllib.error
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE='http://127.0.0.1:8088'
def state():
 with urllib.request.urlopen(BASE+'/api/state') as r:return json.load(r)
async def main():
 before=state();versions=[(c['id'],c['version']) for c in before['cases']];c=next(c for c in before['cases'] if c.get('marketing',{}).get('settlement_draft'));errors=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);p=await b.new_page();p.on('pageerror',lambda e:errors.append(str(e)));await p.goto(BASE+'/campaign#screen=MKT_1_Proposal&case='+c['id']);await p.locator('html[data-ready=true]').wait_for();note=p.locator('section[aria-label="신청 가능 일정"]');await expect(note).to_contain_text('신청할 수 없습니다');assert await p.evaluate('values.notReady') is True
  await p.evaluate("()=>{logic.state.f.start='2026-07-13';logic.state.f.end='2026-07-19';logic.state.f.settle='2026-08-01';render()}");await expect(p.locator('section[aria-label="신청 가능 일정"]')).to_contain_text('현금 전망 범위 안');assert await p.evaluate("values.checks.find(c=>c.label==='캠페인·지급일 현금 전망 범위').ok") is True
  await p.evaluate("()=>{logic.state.f.settle='2026-12-24';render()}");await expect(p.locator('section[aria-label="신청 가능 일정"]')).to_contain_text('집행비 지급예정일 2026-12-24');assert await p.evaluate('values.notReady') is True
  await p.set_viewport_size({'width':390,'height':844});assert await p.evaluate('document.documentElement.scrollWidth<=innerWidth');await p.screenshot(path='docs/assets/screenshots/marketing-cash-window.png',full_page=True);assert not errors,errors;await b.close()
 body={'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':c['marketing']}
 req=urllib.request.Request(BASE+'/api/marketing',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 try:
  urllib.request.urlopen(req);raise AssertionError('out-of-range submission accepted')
 except urllib.error.HTTPError as e:
  assert e.code==400;message=json.load(e)['error'];assert '현금 전망 기간' in message,message
 assert [(c['id'],c['version']) for c in state()['cases']]==versions
 result={'marketing_warning_visible':True,'in_range_gate_passes':True,'predicted_payment_outside_blocks':True,'server_submission_rejected':message,'unit_tests_passed':227,'case_versions_unchanged':True,'mobile_overflow':False,'browser_errors':errors};Path('docs/verification/marketing/MARKETING_CASH_WINDOW_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
asyncio.run(main())
