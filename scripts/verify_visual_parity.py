"""Compare original DC markup and generated runtime at identical states/viewports."""
import asyncio,hashlib,json,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8087')
if urlparse(BASE).hostname not in ['localhost','127.0.0.1','::1']:raise SystemExit('Local verification only')
ROOT=Path(__file__).resolve().parent.parent
async def main():
 manifest=json.loads((ROOT/'web/screens/manifest.json').read_text());errors=[];report={'source':'W01_screens','comparisons':[]}
 out=ROOT/'docs/assets/screenshots/visual-parity';out.mkdir(exist_ok=True)
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox']);page=await browser.new_page(device_scale_factor=1)
  page.on('pageerror',lambda e:errors.append(str(e)))
  for width,height in [(1440,1000),(390,844)]:
   await page.set_viewport_size({'width':width,'height':height})
   for s in manifest['screens']:
    images=[];geometry=[]
    for mode in ['reference','parity']:
     await page.goto(BASE+'/?'+mode+'=1#screen='+s['id']);await page.wait_for_selector('html[data-ready="true"]',timeout=10000);await page.evaluate("""async () => { await Promise.all([400,500,600,700].map(w => document.fonts.load(w+' 14px "IBM Plex Sans KR"', '캠페인'))); await document.fonts.ready; render(); await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))); }""")
     assert await page.evaluate("document.fonts.check('400 14px \"IBM Plex Sans KR\"')"),'Font not ready'
     if s['id']=='SCM_1_Check':
      assert await page.locator('section[aria-label="재고 입고 대조표"] tbody tr').count()==3
      assert 'SKU-2001' in await page.locator('tbody').first.inner_text()
     assert 'undefined' not in await page.locator('main').inner_text(),s['id']
     img=await page.screenshot(full_page=True,animations='disabled');images.append(img)
     geometry.append(await page.locator('main section').evaluate_all('(ns)=>ns.map(n=>({name:n.getAttribute("aria-label"),x:n.getBoundingClientRect().x,y:n.getBoundingClientRect().y,width:n.getBoundingClientRect().width,height:n.getBoundingClientRect().height}))'))
    same=images[0]==images[1]
    if not same:
     (out/'reference-mismatch.png').write_bytes(images[0]);(out/'runtime-mismatch.png').write_bytes(images[1])
    assert geometry[0]==geometry[1],(s['id'],width,'layout mismatch')
    assert same,(s['id'],width,'PNG mismatch')
    if width==1440:(out/(s['id']+'.png')).write_bytes(images[1])
    report['comparisons'].append({'screen':s['id'],'viewport':[width,height],'identical_png':same,'sha256':hashlib.sha256(images[1]).hexdigest(),'section_geometry_identical':True})
    print(s['id'],width,'identical',flush=True)
  # Original modal interactions: source structure and states survive the port.
  await page.set_viewport_size({'width':1440,'height':1000});await page.goto(BASE+'/?parity=1#screen=MKT_1_Proposal');await page.wait_for_selector('#p-title')
  await page.locator('#p-title').fill('시안 입력 검증');assert await page.locator('#p-title').input_value()=='시안 입력 검증'
  await page.get_by_role('button',name='이전 캠페인 불러오기',exact=False).click();await page.locator('#cm-q').wait_for(timeout=3000)
  await browser.close()
 assert not errors,errors
 report.update(passed=True,browser_errors=errors,source_files_unchanged=all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h for f,h in manifest['files'].items()),scope='원본 Design Component를 지원하는 동일 로컬 바인더/브라우저에서 동일 초기 상태 비교. 실데이터 텍스트/행 수에 따른 차이는 별도.')
 (ROOT/'docs/verification/screen-reviews/14-visual-parity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('Visual parity passed',len(report['comparisons']))
if __name__=='__main__':asyncio.run(main())
