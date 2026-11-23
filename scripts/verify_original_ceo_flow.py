import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
from scripts.verify_screen_migration import create,command,get,BASE
from scripts.verify_original_role_flow import ready,metadata
async def main():
 cid,_,_=create('원본 UI CEO 발주·분할 회신','2026-08-21')
 t=next(t for t in get(cid)['execution']['targets'] if t['kind']=='캠페인집행');command(cid,'decide','승인권자',authority=t['authority'],decisions=[{'id':t['id'],'decision':'승인'}])
 errors=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.dismiss())
  await page.goto(BASE+'/#screen=APR_1_CEO&case='+cid);await ready(page,'APR_1_CEO');await page.locator('#a-owner').fill('CEO 원본 화면 검증');await page.get_by_label('승인',exact=True).check()
  await page.get_by_role('button',name='결정 확정',exact=True).click();await metadata(page,decision_maker='CEO 원본 화면 검증');await page.locator('.w01-dialog [type=submit]').click();await page.locator('.w01-layer').wait_for(state='detached');await ready(page,'APR_1_CEO')
  await page.goto(BASE+'/#screen=SCM_3_PO&case='+cid);await ready(page,'SCM_3_PO');await page.locator('#p-owner').fill('SCM 발주 담당');await page.locator('#p-ch').select_option(index=1);await page.locator('#w-SKU-2002').fill('2026-07-14')
  await page.get_by_role('button',name='Corevia에 발주서 전달 (1건)',exact=True).click();await metadata(page);await page.locator('.w01-dialog [type=submit]').click();await ready(page,'SCM_4_WaitReply')
  po=get(cid)['execution']['orders'][0]['po_id'];await page.goto(BASE+'/#screen=SCM_5_Receipt&case='+cid);await ready(page,'SCM_5_Receipt');await page.locator('#r-owner').fill('SCM 회신 담당')
  for name,val in [('d1','2026-07-14'),('q1','8000'),('d2','2026-07-16'),('q2','8000')]:await page.locator('#'+name+'-'+po).fill(val)
  await page.locator('label').filter(has_text='일정대로 진행').locator('input[type=radio]').check();await page.get_by_role('button',name='마케팅에 회신',exact=False).click();await metadata(page);await page.locator('.w01-dialog [type=submit]').click();await ready(page,'SCM_4_WaitReply')
  assert get(cid)['execution']['receipt']['clear'];await b.close()
 assert not errors,errors
 result={'passed':True,'case_id':cid,'errors':errors,'trace':['서버 SCM·재무 검토 준비','원본 CEO 화면에서 하회구간 발주 승인','원본 발주 화면에서 승인 범위 일치·모의 전달','원본 회신 화면에서 2회 분할 공급 회신 저장'],'note':'캠페인 평시 승인 준비는 API, CEO·발주·회신은 브라우저 원본 컨트롤 사용'}
 Path('docs/verification/screen-reviews/14-original-ceo-flow.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result)
if __name__=='__main__':asyncio.run(main())
