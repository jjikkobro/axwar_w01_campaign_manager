"""Record real Chromium UI on the isolated 8091 demo DB. Never writes preview 8088.
Prerequisite: w01_demo_video_20261112, local server, configured server-only GPT key.
Setup fixtures use API outside recording; every recorded business change uses visible UI.
"""
import asyncio,json,sys,time,re,urllib.request,urllib.error,uuid,shutil
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE='http://127.0.0.1:8091';OUT=Path('artifacts/demo-2026-11-12');OUT.mkdir(parents=True,exist_ok=True)
IDS=Path('/tmp/w01-demo-ids.json');REPORT=OUT/'clips.json';CHROME='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome'
def api(path,body=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
 except urllib.error.HTTPError as e:raise RuntimeError(path+' '+e.read().decode())
def ids():return json.loads(IDS.read_text())
def get(key='A'):return api('/api/cases/'+ids().get(key,key))
async def pause(p,ms=1000):await p.wait_for_timeout(ms)
async def caption(p,text):
 await p.evaluate("""t=>{let n=document.getElementById('demo-caption');if(!n){n=document.createElement('div');n.id='demo-caption';n.style='position:fixed;bottom:12px;left:24px;right:24px;z-index:99999;padding:12px 18px;background:rgba(15,23,42,.94);color:white;border-radius:10px;font:16px IBM Plex Sans KR,sans-serif;pointer-events:none;box-shadow:0 3px 12px #0003';document.body.append(n)}n.textContent=t}""",text)
async def click(p,loc):
 await loc.scroll_into_view_if_needed();await loc.hover();await pause(p,450);await loc.click();await pause(p,800)
async def fill(p,selector,text):
 loc=p.locator(selector);await loc.scroll_into_view_if_needed();await loc.fill(str(text));await loc.press('Tab');await pause(p,650)
async def ready(p,screen,key='A'):
 cid=ids().get(key,key);await p.goto(BASE+'/campaign#screen='+screen+'&case='+cid);await p.locator('html[data-ready=true]').wait_for();await pause(p,1000)
async def complete_meta(p,reason=None):
 form=p.locator('.w01-dialog');await form.wait_for()
 for name in ['decision_maker','reason','evidence','demand_override','alternatives','performance_basis']:
  field=form.locator('[name='+name+']')
  if await field.count() and (not await field.input_value() or name=='reason' and reason):await field.fill(reason if name=='reason' and reason else '시연 담당자 근거 확인 · 원본 자료와 모의 협의 조건 구분')
async def modal_submit(p):
 form=p.locator('.w01-dialog');await click(p,form.locator('[type=submit]'));await form.wait_for(state='detached',timeout=25000)
async def record(browser,name,title,work):
 context=await browser.new_context(viewport={'width':1440,'height':900},record_video_dir=str(OUT/'raw'),record_video_size={'width':1440,'height':900},locale='ko-KR');page=await context.new_page();page.set_default_timeout(18000);page.on('dialog',lambda d:d.accept());errors=[];page.on('pageerror',lambda e:errors.append(str(e)));start=time.monotonic();ok=False
 try:
  await work(page);await pause(page,1800);assert not errors,errors;ok=True
 finally:
  await page.screenshot(path=str(OUT/(name+'-end.png')),full_page=False);video=page.video;await context.close();target=OUT/(name+('' if ok else '-incomplete')+'.webm');await video.save_as(str(target));await video.delete();report=json.loads(REPORT.read_text()) if REPORT.exists() else [];report=[r for r in report if r['id']!=name];report.append({'id':name,'title':title,'file':target.name,'complete':ok,'wall_seconds':round(time.monotonic()-start,1),'errors':errors,'silent':True,'resolution':'1440x900','server':BASE});REPORT.write_text(json.dumps(sorted(report,key=lambda r:r['id']),ensure_ascii=False,indent=2)+'\n');print(name, 'OK' if ok else 'INCOMPLETE',flush=True)
async def scope(p):
 await ready(p,'MKT_1_Proposal');await caption(p,'01 | 현금 전망 범위 밖 일정은 마케팅 신청 단계에서 차단합니다.');await fill(p,'#f-start','2026-11-16');await fill(p,'#f-end','2026-11-20');await p.locator('[aria-label="신청 가능 일정"]').scroll_into_view_if_needed();await pause(p,2500);assert await p.evaluate('values.notReady');await caption(p,'기획 단계에서 확인: 현재 전망 7/1~9/28 · 범위 밖 캠페인은 SCM으로 전달되지 않습니다.');await pause(p,2500)
async def marketing(p):
 await ready(p,'MKT_1_Proposal');await caption(p,'02 | 마케팅 기안 · 같은 캠페인에 수요·발주 예상·항목별 예산을 연결합니다.');await fill(p,'#p-title','[시연 A] 색조 캠페인 공급 준비');await p.locator('#budget-receipt').scroll_into_view_if_needed();await pause(p,2000);await p.locator('.ax-planning').scroll_into_view_if_needed();await pause(p,2000);await click(p,p.get_by_role('button',name='발주량과 비용 적용하기',exact=True));await pause(p,1500);await caption(p,'원본 통계 기반 예상안 · 최종 신청은 담당자가 근거와 지급예정일을 확인합니다.');await click(p,p.get_by_role('button',name='캠페인 신청',exact=True));await complete_meta(p);await pause(p,2200);await modal_submit(p);await p.locator('html[data-screen=MKT_2_Wait][data-ready=true]').wait_for();assert get()['execution']['stage']==2;await caption(p,'SCM 검토 요청 저장 완료 · 담당자와 단계가 갱신됩니다.');await pause(p,1800)
async def readonly(p):
 await ready(p,'SCM_1_Check');await caption(p,'03 | SCM에서 기안 원문 조회 · 현재 역할을 유지한 읽기 전용 화면입니다.');await click(p,p.get_by_role('link',name='① 기안 원문 보기',exact=True));await p.locator('[aria-label="읽기 전용 안내"]').wait_for();await pause(p,2500);await click(p,p.get_by_role('link',name='SCM 검토로 돌아가기',exact=True));await p.locator('html[data-screen=SCM_1_Check][data-ready=true]').wait_for();await click(p,p.locator('#role-switch'));await p.locator('.w01-dialog [name=role]').select_option('SCM');await pause(p,1200);await modal_submit(p)
async def scm(p):
 await ready(p,'SCM_1_Check');await caption(p,'04 | SCM 검토 · 캠페인 추가 발주 수량·단가·지급 조건을 입력합니다.');await click(p,p.locator('label').filter(has_text='추가 발주 필요').first);await p.locator('#scm-order-editor').wait_for();await p.locator('#scm-select-SKU-3003').check();await fill(p,'#scm-qty-SKU-3003','20000');await fill(p,'#scm-price-SKU-3003','16800');await fill(p,'#scm-due-SKU-3003','2026-09-21');await fill(p,'#s-reason','캠페인 공급 여유 확보를 위한 시연 발주안 20,000EA. 공급처 조건은 모의 가정이며 실제 발주 승인은 별도입니다.');await p.locator('#scm-order-editor').scroll_into_view_if_needed();await pause(p,2200)
 # Generate against current visible draft, then human reviews and edits rather than auto-deciding.
 panel=p.locator('#gpt-stage-review');await panel.scroll_into_view_if_needed();await caption(p,'실제 GPT 호출 | 현재 기안·SCM 작성안과 출처로 위험·대안·확인 질문을 생성합니다.');await click(p,panel.get_by_role('button',name='검토 초안 생성',exact=True));await panel.locator('.ai-review-output').wait_for(timeout=60000);await pause(p,3500);text=await panel.locator('.ai-review-output').inner_text();(OUT/'04-scm-gpt-output.txt').write_text(text);await click(p,panel.get_by_role('button',name='검토 의견에 반영',exact=True));await fill(p,'#s-reason','[담당자 검토] GPT가 제시한 미확정 공급·지급 조건 확인 필요 의견을 반영합니다. 20,000EA 추가 발주안은 승인 후 전달하며 입고는 공급처 회신으로 확인합니다.\n'+text[:1800]);await caption(p,'GPT는 초안만 생성 · 담당자가 근거를 확인해 의견을 수정하고 재무로 전달합니다.');await click(p,p.get_by_role('button',name='대조 결과 전달',exact=True));await complete_meta(p);await pause(p,2000);await modal_submit(p);assert get()['execution']['stage']==3;await caption(p,'SCM 검토·추가 조달비 저장 → 재무 검토 단계로 이동');await pause(p,2000)
async def finance(p):
 await ready(p,'FIN_1_Review');await caption(p,'05 | 재무 검토 · 같은 기안의 예측 지급일·조달비·현금 제약을 검토합니다.');await click(p,p.locator('input[name=scen]').nth(1));await pause(p,1500)
 boxes=p.locator('input[type=checkbox]')
 for i in range(await boxes.count()):
  if not await boxes.nth(i).is_checked():await click(p,boxes.nth(i))
 await click(p,p.locator('input[name=fin-opinion]').nth(0));await fill(p,'#f-reason','9/21 지급 조건은 현재 하회구간 밖입니다. 상품 조달비와 마케팅 집행비의 범위를 구분하고 계산된 승인권자에게 상신합니다.');await pause(p,1800)
 button=p.locator('section[aria-label="상신 전 점검"] button');await click(p,button);await complete_meta(p)
 form=p.locator('.w01-dialog')
 for sel in await form.locator('select[name^=scope-]').all():
  if await sel.input_value()=='미확인':await sel.select_option('전사 현금 반영 확인')
 for field in await form.locator('textarea[required],input[required]').all():
  if not await field.input_value():await field.fill('촬영용 담당자 검토 근거 · 실제 외부 증빙 아님')
 await caption(p,'마케팅 예측 정산일 자동 전달 · 재무가 지급 조건과 비용 범위를 명시적으로 확인');await pause(p,2200);await modal_submit(p);assert get()['execution']['stage']==4;await caption(p,'재무 상신 완료 → 승인 대기 · 시스템 판정과 사람 승인은 구분합니다.')
async def approval(p):
 await ready(p,'APR_2_Normal');await caption(p,'06 | 평시 승인 · 부서 코멘트와 요청 금액을 확인한 뒤 사람이 승인합니다.');await p.locator('[aria-label="결재 문서"]').scroll_into_view_if_needed();await pause(p,2300)
 for _ in range(3):
  pending=[t for t in get()['execution']['targets'] if not t['current'] or t['decision']['decision']!='승인']
  if not pending:break
  authority=pending[0]['authority'];pres=p.get_by_role('group',name='결재자 전환').get_by_role('button');labels=await pres.all_text_contents()
  for i,label in enumerate(labels):
   if authority in label or ('SCM' in label and authority=='SCM 전결') or ('마케팅' in label and authority=='마케팅팀 전결'):
    await click(p,pres.nth(i));break
  await click(p,p.locator('input[name=campaign-decision]').nth(0));await fill(p,'#campaign-memo','부서 의견·현금 제약과 지급 조건을 확인하고 해당 권한 범위의 집행을 승인합니다. 모의 담당자 결정입니다.');await click(p,p.locator('[aria-label="확정 전 점검"] button'));await complete_meta(p);await pause(p,1800);await modal_submit(p);await pause(p,1200)
 assert get()['execution']['stage']==5;await caption(p,'사람 승인 완료 → SCM 발주 작성 대기 · 발주 자체는 아직 실행되지 않았습니다.')
async def order(p):
 await ready(p,'SCM_3_PO');await caption(p,'07 | SCM 발주서 · 승인된 제품·수량·단가·금액을 자동으로 불러옵니다.');await p.locator('#p-due').scroll_into_view_if_needed();await pause(p,1800);await fill(p,'#p-note','[모의 발주] 승인된 20,000EA·단가·9/21 지급 조건 유지. 입고 일정 회신 요청.');await p.locator('#p-ch').select_option('mail');await pause(p,900)
 print('ORDER CHECKS',await p.evaluate('JSON.stringify(values.checks)'),flush=True)
 await click(p,p.locator('section[aria-label="전달 전 점검"] button'));await complete_meta(p);await pause(p,1800);await modal_submit(p);await p.locator('html[data-screen=SCM_5_Receipt][data-ready=true]').wait_for();assert get()['execution']['stage']==6;await caption(p,'모의 발주 전달 저장 → 입고예정 회신 확인으로 연결됩니다.')
async def receipt(p):
 await ready(p,'SCM_5_Receipt');await caption(p,'08 | 모의 공급처 회신 · 승인된 발주의 입고예정일·수량·지급일을 기록합니다.');order=get()['execution']['orders'][0];pid=order['po_id'];await fill(p,'[id="d1-'+pid+'"]','2026-08-12');await fill(p,'[id="q1-'+pid+'"]',order['order_qty']);await click(p,p.locator('input[name=r-dec]').nth(0));await fill(p,'#r-msg','[모의 공급처 회신] SKU-3003 '+str(order['order_qty'])+'EA는 8/12 판매가능 예정, 지급일은 승인된 9/21을 유지합니다. 실제 입고·지급 완료가 아닙니다.');await pause(p,1500);await click(p,p.locator('[aria-label="회신 전 점검"] button'));await complete_meta(p);await pause(p,1600);await modal_submit(p);assert get()['execution']['stage']==7;await caption(p,'회신 기록 저장 → 마케팅 일정 관리로 연결 · 실제 판매 성공과 구분합니다.')
async def close_marketing(p):
 await ready(p,'MKT_4_Close');await caption(p,'08b | 마케팅 일정 · SCM 회신의 입고예정일과 발주 지급일이 연결됩니다.');await pause(p,2000);print('CLOSE',await p.evaluate('JSON.stringify({checks:values.checks,inputs:[...document.querySelectorAll("input,textarea")].map(x=>({id:x.id,t:x.type,v:x.value})),buttons:[...document.querySelectorAll("button")].map(x=>x.textContent)})'),flush=True)
 for box in await p.locator('input[type=checkbox]').all():
  if not await box.is_checked():await click(p,box)
 await click(p,p.locator('[aria-label="종료 전 점검"] button'));await complete_meta(p,'입고예정 회신·발주 지급일·상품 구성 공유 기록을 확인하여 검토 회차를 종료합니다. 실제 입고나 판매 성공이 아닙니다.');await pause(p,1500);await modal_submit(p);assert get()['execution']['closed'];await caption(p,'검토 회차 종료 기록 저장 · 후속 입고·지급·성과 측정 의무는 별도로 남습니다.')
async def payment_change(p):
 await ready(p,'SCM_1_Check','B');await caption(p,'09a | 변경 사건 · 공급처가 같은 발주안의 지급일을 9/21 → 7/21로 앞당겨 요청한 상황');await click(p,p.locator('label').filter(has_text='추가 발주 필요').first);await fill(p,'#scm-due-SKU-3003','2026-07-21');await fill(p,'#s-reason','[모의 공급처 변경 요청] 제품·수량·단가는 유지하되 7/21 선지급 요청이 도착했습니다. 현금·승인 경로 재검토를 재무에 요청합니다.');await click(p,p.get_by_role('button',name='대조 결과 전달',exact=True));await complete_meta(p);await modal_submit(p);await ready(p,'FIN_1_Review','B');await p.locator('[aria-label="결재선 판정"]').scroll_into_view_if_needed();await pause(p,2600);assert any(r['route']['authority']=='CEO/이사회' for r in get('B')['finance_review_initial']['routes']);await caption(p,'같은 금액·변경된 지급일 → 하회구간 신규 유출로 CEO/이사회 경로 재판정')
async def decision_change(p):
 await ready(p,'FIN_1_Review','B');await caption(p,'09 | 조건 변경 · 동일 발주안의 지급일이 9/21에서 7/21로 변경된 모의 사건');await p.locator('[aria-label="결재선 판정"]').scroll_into_view_if_needed();await pause(p,2200)
 await click(p,p.locator('input[name=fin-opinion]').nth(0));await fill(p,'#f-reason','검토 전 의견: 승인 요청 진행을 검토 중입니다.');panel=p.locator('#gpt-stage-review');await panel.scroll_into_view_if_needed();await click(p,panel.get_by_role('button',name='검토 초안 생성',exact=True));await panel.locator('.ai-review-output').wait_for(timeout=60000);await pause(p,3200);text=await panel.locator('.ai-review-output').inner_text();(OUT/'09-finance-gpt-output.txt').write_text(text)
 await click(p,panel.get_by_role('button',name='검토 의견에 반영',exact=True));await click(p,p.locator('input[name=fin-opinion]').nth(1));await fill(p,'#f-reason','검토 후 의견: 7/21 신규 유출은 30억 하회구간입니다. GPT의 위험·확인 질문을 근거 자료와 대조하여 지급 조건 재협의를 먼저 요청합니다. CEO 경로를 자동 우회하지 않습니다.');await caption(p,'담당자 판단 수정: 승인 진행 초안 → 지급 조건 보완 우선 · AI는 승인권한을 바꾸지 않습니다.');await pause(p,2000)
 await click(p,p.get_by_role('button',name='다른 부서에 조정 요청',exact=True));form=p.locator('.w01-dialog');await form.locator('[name=target]').select_option('SCM');await complete_meta(p,'7/21 선지급 부담이 하회구간에 겹칩니다. 공급처와 분할 또는 지급일 조정을 협의하고 수정안을 재무에 전달해 주세요.');await pause(p,1600);await modal_submit(p);await p.locator('[aria-label="조정 요청 내용"]').wait_for();assert get('B')['execution']['stage']==2;await caption(p,'SCM 조정 요청 도착 · 담당 부서와 검토 단계가 실제로 갱신됩니다.')
async def reject_rework(p):
 await ready(p,'APR_1_CEO','C');await caption(p,'10 | CEO 검토 · 현금 하회구간의 신규 지출에 자금 대안이 부족한 모의 상황');await p.locator('[aria-label="결재 문서"]').scroll_into_view_if_needed();await pause(p,1800);await click(p,p.locator('input[name=campaign-decision]').nth(3));await fill(p,'#campaign-memo','7/21 신규 유출의 자금 대안이 확보되지 않았습니다. 지급 조건과 캠페인 수요를 보완한 뒤 재검토해 주세요.');await click(p,p.locator('[aria-label="확정 전 점검"] button'));await complete_meta(p);await modal_submit(p);await pause(p,1600);assert any(t['current'] and t['decision']['decision']=='반려' for t in get('C')['execution']['targets']);await caption(p,'반려 결과와 근거 저장 · 다음 행동은 마케팅의 기안 보완입니다.');await click(p,p.get_by_role('button',name='기안 변경 요청',exact=True));await complete_meta(p,'선지급 부담을 낮출 수 있도록 수요·상품 구성·예산을 재검토하고 SCM 검토를 다시 요청해 주세요.');await pause(p,1600);await modal_submit(p);await p.locator('html[data-screen=MKT_1_Proposal][data-ready=true]').wait_for();await p.locator('[aria-label="조정 요청 내용"]').scroll_into_view_if_needed();await pause(p,2000)
async def marketing_rework(p):
 await ready(p,'MKT_1_Proposal','C');await caption(p,'11 | 마케팅 재작성 · 돌아온 요청을 읽고 담당자가 기존 기안을 직접 수정합니다.');await p.locator('[aria-label="조정 요청 내용"]').scroll_into_view_if_needed();await pause(p,1600);await fill(p,'#p-title','[시연 C] 순증 수요 감량 후 재검토');await fill(p,'#dem-SKU-3003','500');await pause(p,1800);await click(p,p.get_by_role('button',name='발주량과 비용 적용하기',exact=True));await pause(p,1200);await click(p,p.get_by_role('button',name='캠페인 신청',exact=True));await complete_meta(p,'반려·조정 요청에 따라 순증 수요를 1,000EA/주에서 500EA/주로 수정하고 재검토를 요청합니다.');await pause(p,1500);await modal_submit(p);assert get('C')['execution']['stage']==2;await caption(p,'동일 캠페인의 수정 버전으로 SCM 재검토 요청 · 과거 승인·반려 기록은 보존됩니다.')
async def prompt_edit(p):
 await p.goto(BASE+'/admin#tab=prompts&role=SCM');await p.locator('[data-prompt=scm]').wait_for();await caption(p,'12 | 프롬프트 수정 · 근거·위험·대안·담당 부서가 명확해지도록 지침을 보완합니다.');card=p.locator('[data-prompt=scm]');await card.scroll_into_view_if_needed();field=card.locator('[name=prompt]');old=await field.input_value();await field.fill(old+'\n각 위험에 해당 SKU·지급일·금액과 출처를 붙이세요. 대안별 담당 부서와 다음 행동을 한 줄로 작성하고, 미확정 공급은 확정 입고와 구분하세요.');
 for k,v in [('decision_maker','SCM 시연 담당자'),('reason','GPT 출력의 근거와 후속 행동을 명확히 표시'),('evidence','시연 캠페인 검토 피드백 · 내부 운영 가정')]:await card.locator('[name='+k+']').fill(v)
 await pause(p,1800);await click(p,card.get_by_role('button',name='프롬프트 저장',exact=True));await pause(p,1400);await ready(p,'SCM_1_Check','B');await caption(p,'저장된 프롬프트로 다시 생성 · 계산값과 승인권한은 프롬프트가 변경하지 않습니다.');panel=p.locator('#gpt-stage-review');await click(p,panel.get_by_role('button',name='검토 초안 생성',exact=True));await panel.locator('.ai-review-output').wait_for(timeout=60000);(OUT/'12-revised-prompt-output.txt').write_text(await panel.locator('.ai-review-output').inner_text());await pause(p,3000)
async def formula_edit(p):
 await p.goto(BASE+'/admin#tab=formulas&role=SCM');card=p.locator('[data-formula=replenishment_trigger]');await card.wait_for();await caption(p,'13 | 산식 관리 · 리드타임과 안전재고에 1주 여유를 추가하는 시연 가정');await click(p,card.get_by_role('button',name='산식 수정',exact=True));form=card.locator('form');await form.locator('[name=expression]').fill('weekly * (lead_weeks + review_weeks + safety_weeks + 1)')
 for k,v in [('decision_maker','SCM 시연 담당자'),('reason','공급 변동에 대비한 1주 여유 · 시연용 가정'),('evidence','내부 관리 시연 가정. 원본 승인 규정 변경 아님')]:await form.locator('[name='+k+']').fill(v)
 await click(p,form.get_by_role('button',name='시험 계산',exact=True));await pause(p,1600);await click(p,form.get_by_role('button',name='변경 영향 확인',exact=True));await form.locator('.preview-result').wait_for(state='visible');await form.locator('.preview-result').scroll_into_view_if_needed();await pause(p,2500);await form.locator('[name=human_confirmed]').check();await click(p,form.get_by_role('button',name='검증한 산식 적용',exact=True));await pause(p,1800);await ready(p,'SCM_1_Check','B');await caption(p,'새 산식 적용 후 공통 계산 갱신 · 기존 검토와 재무 확정은 새 근거로 재확인합니다.');await pause(p,2000)
async def data_edit(p):
 await p.goto(BASE+'/admin#tab=data&role=SCM');await p.locator('[data-dataset=inventory]').wait_for();await caption(p,'14 | 재고 자료 정정 · 원본 파일은 보존하고 시연 DB 사본 한 행만 수정합니다.');await click(p,p.locator('[data-dataset=inventory] .update'));form=p.locator('.admin-dialog form');await form.wait_for();text=await form.locator('[name=csv]').input_value();lines=text.splitlines();headers=lines[0].split('|');index=headers.index('sku_id');qty=headers.index('on_hand_qty')
 for i,line in enumerate(lines[1:],1):
  cells=line.split('|')
  if cells[index]=='SKU-3003':cells[qty]=str(int(cells[qty])-500);lines[i]='|'.join(cells);break
 await form.locator('[name=csv]').fill('\n'.join(lines))
 for k,v in [('decision_maker','SCM 시연 담당자'),('reason','촬영용 모의 실사 정정: SKU-3003 500EA 감소'),('evidence','모의 담당자 회신 · 실제 실사 증빙 아님')]:await form.locator('[name='+k+']').fill(v)
 await pause(p,1500);await click(p,form.get_by_role('button',name='업데이트 검증',exact=True));await pause(p,1800);await click(p,form.get_by_role('button',name='검증한 자료 저장',exact=True));await p.locator('.dialog-backdrop').wait_for(state='detached');await ready(p,'SCM_1_Check','B');await caption(p,'자료 버전·재고 계산 갱신 → 관련 검토 재확인 · 승인이나 발주는 자동 실행되지 않습니다.');await pause(p,2600)
async def main():
 actions={'01':('01-marketing-scope','마케팅 사전 차단',scope),'02':('02-marketing-submit','기안·예산·SCM 전달',marketing),'03':('03-readonly-role','읽기 전용 조회·역할 선택',readonly),'04':('04-scm-gpt-handoff','SCM 추가 발주·실제 GPT 검토·재무 전달',scm),'05':('05-finance-review','재무 검토',finance),'06':('06-human-approval','사람 승인',approval),'07':('07-order-prefill','발주서 자동 채움·모의 전달',order),'08':('08-supplier-reply','모의 공급처 회신',receipt),'08b':('08b-marketing-schedule','마케팅 일정·기록 종료',close_marketing),'09a':('09a-payment-change','지급일 변경·CEO 재판정',payment_change),'09':('09-gpt-human-decision','실제 GPT 검토 후 사람 판단 수정·SCM 조정 요청',decision_change),'10':('10-ceo-reject-return','CEO 반려·마케팅 조정 요청',reject_rework),'11':('11-marketing-rework','마케팅 직접 수정·재신청',marketing_rework),'12':('12-prompt-settings','프롬프트 수정·실제 GPT 재생성',prompt_edit),'13':('13-formula-settings','산식 시험·영향 확인·적용',formula_edit),'14':('14-data-update','재고 자료 사본 수정·재검토',data_edit)}
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(executable_path=CHROME,args=['--no-sandbox'])
  for key in sys.argv[1:] or ['01','02','03','04']:
   name,title,work=actions[key];await record(browser,name,title,work)
  await browser.close()
if __name__=='__main__':asyncio.run(main())
