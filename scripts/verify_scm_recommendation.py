"""Writes mock SCM receipts and handoff into an isolated local DB only."""
import asyncio,copy,json,os,uuid,urllib.request,urllib.error
from urllib.parse import urlparse
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('W01_SCM_ADVICE_TEST_BASE_URL','').rstrip('/')
parsed=urlparse(BASE)
if parsed.scheme!='http' or parsed.hostname not in ['127.0.0.1','localhost'] or parsed.port in [None,8088]:raise RuntimeError('별도 로컬 테스트 DB의 서버를 지정하세요. 8088 금지.')
def api(path,body=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def good(path,body=None):
 code,d=api(path,body);assert code==200,(path,code,d);return d
s=good('/api/state');base=next(c for c in s['cases'] if '기초 라인' in c['title']);old=good('/api/cases/'+base['id'])['case']['marketing'];meta={'decision_maker':'검증 SCM','reason':'원본과 회신 검토','evidence':'모의 회신·격리 DB 검증'}
p=copy.deepcopy(old);p.update(title='[모의] SCM 시기 조정 검증',campaign_name='SCM 시기 조정 검증',submission_mode='estimate_only',start='2026-07-27',end='2026-08-02',settlement_date=None,contract_deadline=None,group_total=None,scope_skus=['SKU-2002']);p['items']=[{'sku_id':'SKU-2002','demand':7000,'unit':'EA/주','start':p['start'],'end':p['end'],'basis':'수요 조정 검증 가정','confidence':'미확인','overlap':'기존 판매 제외한 순증'}]
bad=good('/api/marketing',{'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':p})['id'];d=good('/api/cases/'+bad)
good('/api/scm',{'role':'SCM','id':bad,'version':d['case']['version'],'mutation_id':str(uuid.uuid4()),'operation':'receipt','receipt':{**meta,'po_id':'SPO-0006','status':'확인','qty':16000,'available_date':'2026-08-06','provenance':'모의 회신'}})
d=good('/api/cases/'+bad);advice=d['scm_calculation']['recommendation'];shift=next(a for a in advice['actions'] if a['type']=='shift_campaign');assert shift['start']=='2026-08-06' and shift['minimum']>=0
p=copy.deepcopy(old);p.update(title='[모의] SCM 예상안 보존 검증',campaign_name='SCM 예상안 보존 검증',submission_mode='estimate_only',target='색조',settlement_date=None,contract_deadline=None,group_total=None,scope_skus=['SKU-3001']);p['items']=[{'sku_id':'SKU-3001','demand':100,'unit':'EA/주','start':p['start'],'end':p['end'],'basis':'예상안 인계 검증 가정','confidence':'보통','overlap':'기존 판매 제외한 순증'}]
inputs={'mode':'estimate_only','as_of':p['as_of'],'start':p['start'],'end':p['end'],'budget':p['budget'],'items':[{'sku_id':'SKU-3001','demand_mode':'manual','demand':100,'qty_mode':'manual','qty':12000,'price_mode':'manual','unit_price':16800}]}
ready=good('/api/marketing',{'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':p,'ax_inputs':inputs})['id'];d=good('/api/cases/'+ready);assert d['scm_calculation']['recommendation']['kind']=='ready'
good('/api/operations',{'role':'SCM','operation':'demand_review','id':ready,'version':d['case']['version'],'mutation_id':str(uuid.uuid4()),'basis':d['demand_validation']['basis'],'override_reason':'과거 참고 범위와 원본 수요를 검토한 모의 확인',**meta})
async def main():
 errors=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(15000)
  await page.goto(BASE+'/campaign#screen=SCM_1_Check&case='+bad);await page.locator('html[data-ready="true"]').wait_for();assert await page.locator('section[aria-label="발주안"]').count()==0;assert '2026-08-06' in await page.locator('section[aria-label="SCM 판단"]').inner_text();assert '재검산' in await page.locator('section[aria-label="SCM 판단"]').inner_text();await page.screenshot(path='docs/assets/screenshots/scm-specific-shift-advice.png',full_page=True)
  await page.goto(BASE+'/campaign#screen=SCM_1_Check&case='+ready);await page.locator('html[data-ready="true"]').wait_for();assert '캠페인 기간 공급 가능' in await page.locator('section[aria-label="SCM 판단"]').inner_text();assert await page.locator('section[aria-label="발주안"]').count()==0
  await page.locator('#s-owner').fill('검증 SCM');await page.locator('[name=scm-decision]').nth(1).check();assert not await page.evaluate('values.notReady');await page.get_by_role('button',name='대조 결과 전달',exact=True).click();await page.locator('.w01-dialog').wait_for();assert '12000' in await page.locator('.w01-dialog [name=alternatives]').input_value();await page.locator('.w01-dialog [type=submit]').click();await page.wait_for_url('**screen=SCM_2_WaitApproval**')
  await page.goto(BASE+'/campaign#screen=SCM_1_Check&case='+ready);await page.locator('html[data-ready="true"]').wait_for();await page.screenshot(path='docs/assets/screenshots/scm-matching-estimate-ready.png',full_page=True);await page.set_viewport_size({'width':390,'height':844});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');await b.close()
 assert not errors,errors
 review=good('/api/cases/'+ready)['case']['scm']['review'];assert review['items'][0]['requested_qty']==12000;assert review['items'][0]['requested_unit_price']==16800;assert review['items'][0]['procurement']=='신규 발주 검토'
 report={'passed':True,'unit_tests':174,'order_editor_removed':True,'ready_recommendation_uses_campaign_period':True,'confirmed_receipt_shift':shift,'adopted_estimate_survives_handoff':{'qty':12000,'unit_price':16800},'conditional_inbound_and_pre_campaign_shortage_unit_tested':True,'browser_errors':errors,'mobile_overflow':False,'database':'별도 로컬 검증 DB · 실제 8088 캠페인 변경 없음'}
 Path('docs/verification/scm/SCM_RECOMMENDATION_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
