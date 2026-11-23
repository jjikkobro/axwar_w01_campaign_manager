import asyncio,json,urllib.request,uuid,os
from urllib.parse import urlparse
from pathlib import Path
from playwright.async_api import async_playwright
B=os.environ.get('W01_REPLENISHMENT_TEST_BASE_URL','').rstrip('/')
u=urlparse(B)
if u.scheme!='http' or u.hostname not in ['localhost','127.0.0.1'] or u.port in [None,8088]:raise RuntimeError('격리 테스트 서버만 허용합니다. 8088 금지.')
def api(p,b=None):return json.load(urllib.request.urlopen(urllib.request.Request(B+p,data=json.dumps(b).encode() if b else None,headers={'Content-Type':'application/json'})))
p=api('/api/cases/4774d5b9-980c-456c-919b-d520870a6410')['case']['marketing'];p['title']='[모의] 수요 누락 보완 검증';p['scope_skus'].append('SKU-2002')
cid=api('/api/marketing',{'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':p})['id']
async def main():
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await b.new_page();errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
  await page.goto(B+'/campaign#screen=SCM_1_Check&case='+cid);await page.locator('html[data-ready=true]').wait_for()
  await page.locator('#scm-demand-evidence summary').first.click();await page.get_by_role('button',name='이 화면에서 수요 보완',exact=True).click()
  d=page.get_by_role('dialog');await d.locator('[name=qty-3]').fill('100');await d.locator('[name=basis-3]').fill('모의 회신 · 마케팅 추가 수요 확인')
  await d.get_by_role('button',name='수요 보완 저장 · 다시 대조',exact=True).click();await d.wait_for(state='hidden');await page.locator('html[data-ready=true]').wait_for()
  result=api('/api/cases/'+cid)
  assert not any(i['missing'] for i in result['demand_validation']['items']);assert result['case']['marketing_stage']=='SCM 검토 요청';assert not result['case'].get('approval');assert not errs,errs
  assert '/campaign' in page.url and '/hub' not in page.url
  report={'case_id':cid,'scope_sku':'SKU-2002','explicit_input':100,'saved':True,'state':result['case']['marketing_stage'],'no_navigation':True,'approval':None,'errors':errs};Path('docs/verification/scm/SCM_DEMAND_INLINE_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('누락 수요를 같은 화면에서 입력·저장하고 재대조하는 검증 통과');await b.close()
asyncio.run(main())
