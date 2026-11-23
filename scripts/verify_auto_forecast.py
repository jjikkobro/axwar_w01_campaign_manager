import asyncio,json,os
from pathlib import Path
from urllib.parse import urlparse
B=os.environ.get("W01_AUTO_FORECAST_TEST_BASE_URL", "").rstrip("/")
u=urlparse(B)
if u.scheme!="http" or u.hostname not in ("127.0.0.1", "localhost") or u.port in (None,8088): raise RuntimeError("격리 테스트 서버만 허용합니다")
from playwright.async_api import async_playwright,expect
async def main():
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox'])
  p=await b.new_page(); errs=[];p.on('pageerror',lambda e:errs.append(str(e)))
  await p.goto(B+'/campaign#screen=MKT_1_Proposal');await p.locator('html[data-ready=true]').wait_for()
  await p.evaluate("logic.state.f={...logic.state.f,title:'[모의] 자동 예측',name:'자동 예측',media:['오프라인'],country:'국내',sales:'자사몰',pl:'색조',start:'',end:'',req:''};logic.state.pick={'SKU-3001':true};logic.state.dem={};dirty=true;render()")
  assert await p.get_by_role('button',name='예측치 가져오기').count()==0
  await p.locator('#f-start').fill('2026-11-16');await p.locator('#f-end').fill('2026-11-20');await expect(p.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000)
  initial=await p.evaluate('W01AX.status().inputs.items[0]');assert initial['demand']==21 and initial['qty']==0 and initial['qty_mode']=='forecast'
  await p.get_by_role('button',name='직접 입력',exact=True).first.click();await p.locator('#dem-SKU-3001').fill('999');await p.locator('#dem-SKU-3001').press('Tab');await expect(p.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000)
  assert await p.locator('#dem-SKU-3001').input_value()=='999'
  await p.locator('#receipt-qty-0').fill('12000');await p.locator('#receipt-qty-0').press('Tab');await expect(p.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000)
  await p.locator('#f-end').fill('2026-11-21');await expect(p.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000)
  assert await p.locator('#dem-SKU-3001').input_value()=='999' and await p.locator('#receipt-qty-0').input_value()=='12,000'
  await p.get_by_role('button',name='+ 제품 추가').click()
  await p.get_by_role('button',name='SKU-3002 추가').click();await p.locator('#pm-title').locator('..').get_by_role('button',name='닫기').click();await expect(p.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000)
  assert await p.locator('#dem-SKU-3002').input_value()=='0' and await p.locator('#receipt-qty-1').input_value()!=''
  await p.get_by_role('button',name='+ 제품 추가').click();await p.get_by_role('button',name='SKU-5001 추가').click();await p.locator('#pm-title').locator('..').get_by_role('button',name='닫기').click();await expect(p.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000)
  assert await p.locator('#dem-SKU-5001').input_value()=='';assert await p.get_by_text('비교 자료 부족 · 직접 입력 필요').count()>=1
  await p.locator('#f-end').fill('');assert await p.locator('#dem-SKU-3001').input_value()=='999';assert await p.locator('#dem-SKU-3002').input_value()==''
  await p.locator('#f-end').fill('2026-11-22');await expect(p.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000)
  started=asyncio.Event(); requests=[]
  async def race(route):
   body=json.loads(route.request.post_data);requests.append(body['inputs']['end'])
   response=await route.fetch()
   if len(requests)==1:
    started.set();await asyncio.sleep(1.5)
   await route.fulfill(response=response)
  await p.route('**/api/ax-planning',race)
  await p.locator('#f-end').fill('2026-11-23');await asyncio.wait_for(started.wait(),10)
  await p.locator('#f-end').fill('2026-11-24');await expect(p.locator('.ax-planning')).to_have_attribute('data-state','ready',timeout=30000)
  await asyncio.sleep(2);assert await p.evaluate('W01AX.status().result.inputs.end')=='2026-11-24',requests
  assert await p.locator('#dem-SKU-3001').input_value()=='999'
  await p.unroute('**/api/ax-planning',race)
  await p.screenshot(path='docs/assets/screenshots/auto-forecast-desktop.png',full_page=True)
  await p.set_viewport_size({'width':390,'height':844});assert await p.evaluate('document.documentElement.scrollWidth<=innerWidth');await p.screenshot(path='docs/assets/screenshots/auto-forecast-mobile.png',full_page=True)
  assert not errs,errs
  report={'date_auto_forecast':initial,'manual_demand_and_order_survive_date_change':True,'added_sku_auto_forecast':True,'missing_history_left_blank':True,'stale_response_discarded':True,'cleared_date_clears_only_forecast':True,'mobile_overflow':False,'browser_errors':errs,'approval_or_purchase_performed':False}
  Path('docs/verification/marketing/AUTO_FORECAST_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));await b.close()
asyncio.run(main())
