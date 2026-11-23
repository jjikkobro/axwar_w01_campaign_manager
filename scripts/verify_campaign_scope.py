"""Read-only campaign presentation audit; no DB mutation or external actions."""
import asyncio,json,re,os
from urllib.parse import urlparse
from pathlib import Path
from playwright.async_api import async_playwright
BASE=os.environ.get('W01_TEST_BASE_URL','http://127.0.0.1:8088')
if urlparse(BASE).hostname not in ['localhost','127.0.0.1','::1']:raise SystemExit('Local verification only')
async def main():
 ids=json.loads(Path('docs/verification/system/UPGRADE_SCENARIOS.json').read_text())['ids'];screens=json.loads(Path('web/screens/manifest.json').read_text())['screens'];errors=[];rows=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
  urls=[('/#screen='+s['id']+'&case='+ids['E'],s['id']) for s in screens]+[('/hub#tab='+t+'&role=재무&case='+ids['E'],'hub-'+t) for t in ['queue','consult','history','comparison']]+[('/operations#screen=FIN_1_Review&case='+ids['E'],'operations-finance')]
  for url,name in urls:
   await page.goto(BASE+url)
   await page.wait_for_selector('#view,html[data-ready="true"],#role-choice',timeout=20000)
   await page.wait_for_timeout(100)
   text=await page.locator('body').inner_text();bad=[x.strip() for x in text.splitlines() if re.search('전속|연간계약|연체 확인|연체 회수|자동 갱신|contract_notice|global:overdue',x)]
   rows.append({'screen':name,'outside':bad[:8]});print(name,json.dumps(bad[:8],ensure_ascii=False),flush=True)
  # Pure browser projection must preserve source objects, every daily cash value,
  # and hidden review targets on unrelated campaign edits.
  await page.goto(BASE+'/hub#tab=comparison&role=재무&case='+ids['E']);await page.locator('#view').wait_for()
  invariants=await page.evaluate("""async ()=>{
   const raw=await fetch('/api/state').then(r=>r.json()),before=JSON.stringify(raw),shown=W01CampaignScope.present(raw);
   const a={id:'annual',kind:'연간전속계약',payments:[{date:'2026-08-21',amount:2800000000}],basis:'보존 검증'},c={id:'campaign',kind:'캠페인집행',payments:[{date:'2026-09-21',amount:5000000}]};
   const fixture={case:{id:'scope-pure-fixture',finance_review:{targets:[c,a]}},execution:{targets:[c,a]}};
   const projected=W01CampaignScope.present(fixture),req=W01CampaignScope.request('/api/finance-review',{id:'scope-pure-fixture',review:{targets:projected.case.finance_review.targets}});
   const snapshot=JSON.stringify(raw.finance.scenarios)===JSON.stringify(shown.finance.scenarios);
   return {raw_unchanged:before===JSON.stringify(raw),cash_scenarios_unchanged:snapshot,overdue_still_in_raw:raw.finance.overdue.length>0,overdue_not_in_view:!shown.finance.overdue,annual_not_in_review:projected.case.finance_review.targets.length===1,annual_not_in_approval:projected.execution.targets.length===1,hidden_target_preserved:JSON.stringify(req.review.targets.find(t=>t.id==='annual'))===JSON.stringify(a),no_implicit_decision:!('decisions' in req)};
  }""")
  assert all(invariants.values()),invariants
  await page.screenshot(path='docs/assets/screenshots/campaign-scope.png',full_page=True)
  await b.close()
 assert not errors and all(not r['outside'] for r in rows),{'errors':errors,'rows':rows}
 print('표시 범위·내부 계산 보존 검증 통과');Path('docs/verification/workflow/CAMPAIGN_SCOPE_RESULTS.json').write_text(json.dumps({'passed':True,'base':BASE,'rows':rows,'browser_errors':errors,'invariants':invariants,'mode':'브라우저 읽기 전용 · DB 변경 없음'},ensure_ascii=False,indent=2)+'\n')
asyncio.run(main())
