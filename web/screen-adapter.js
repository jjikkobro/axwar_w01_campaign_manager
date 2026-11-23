/* Only values and command handlers change here. Original sections/styles stay intact. */
const OK=['#e7f4ec','#1e6b3a'],WARN=['#fff1e0','#9a3412'],BAD=['#fdecea','#b42318'];
const dateMS=d=>Date.parse(d+'T00:00:00Z'),md=d=>d?d.slice(5).replace(/^0/,'').replace('-','/').replace('/0','/'):'미확인';
const dateOr=(d,f='2026-07-01')=>d||f;
function catalog(){return workspace.datasets.sku.rows.map(s=>{const inv=workspace.datasets.inventory.rows.find(i=>i.sku_id===s.sku_id);const sales=workspace.datasets.sales.rows.filter(r=>r.sku_id===s.sku_id&&dateMS(r.week)+7*864e5<=dateMS(details?.case.as_of||'2026-07-01')).sort((a,b)=>a.week.localeCompare(b.week)).slice(-4);const po=workspace.datasets.purchase.rows.find(p=>p.sku_id===s.sku_id);return {id:s.sku_id,name:s.sku_name,cat:s.sku_name.split(' ')[0],pl:s.product_id,src:'Corevia',ss:+s.safety_stock_weeks_min,ssMin:+s.safety_stock_weeks_min,ssMax:+s.safety_stock_weeks_max,moq:+s.moq,lt:+s.lead_time_weeks,oh:+inv.on_hand_qty,it:+inv.in_transit_qty,avg:details?.scm_calculation?.items.find(x=>x.sku_id===s.sku_id)?.weekly??workspace.planning_catalog?.find(x=>x.sku_id===s.sku_id)?.weekly_average??0,po:po?{id:po.po_id,date:po.order_date,qty:+po.order_qty,lt:+s.lead_time_weeks,amt:+po.amount_krw,due:po.payment_due_date}:{id:'미확인',date:'2026-07-01',qty:1,lt:+s.lead_time_weeks,amt:0,due:'2026-07-01'}};});}
function planLabel(){return details?'W01-'+details.case.id.slice(0,8):'미저장';}
function setChecks(v,checks,readyLabel){v.checks=checks;v.doneCount=checks.filter(c=>c.ok).length;v.totalCount=checks.length;v.notReady=v.doneCount!==v.totalCount;v.submitBg=v.notReady?'#9aa3af':'#1f5fbf';v.submitLabel=v.notReady?'필수 항목을 채우면 처리할 수 있습니다':readyLabel;}
function validCampaignBudget(value){return value!==null&&value!==undefined&&String(value).trim()!==''&&Number.isSafeInteger(Number(value))&&Number(value)>=0;}
function check(label,ok){return {label,ok,mark:ok?'✓':'!',bg:ok?OK[0]:WARN[0],fg:ok?OK[1]:WARN[1],text:ok?'#374151':'#9a3412'};}
function noMockPresets(v){if(v.presets)v.presets=[{label:planLabel()+' · 서버 저장 기안',on:'true',bg:'#fff',fg:'#1a1d23',pick:()=>workspaceDialog()}];if(v.sims)v.sims=v.sims.map(x=>({...x,off:true,go:()=>notify('실제 단계는 담당자의 저장·상신·결정으로 변경됩니다.')}));}
function hydrateScreen(){
 if(screen==='MKT_1_Proposal'){
  logic.SKU=catalog();const r=workspace.marketing_reference;
  logic.D.C=r.campaigns.rows.map(c=>[c.campaign_id,c.campaign_name,c.influencer_id,c.country,c.sns_channel,c.sns_format,c.sales_channel,c.product_line,c.start_date,c.end_date,+c.attribution_window_days]);logic.D.I=Object.fromEntries(r.influencers.rows.map(i=>[i.influencer_id,[i.influencer_name,i.tier,i.primary_country,i.platform,i.fee_type]]));logic.D.P=r.plans.rows.map(p=>[p.plan_id,p.campaign_id,p.requested_budget_krw,p.expected_gmv_krw,p.settlement_date,p.contract_deadline]);
  if(details){const p=details.case.marketing;Object.assign(logic.state,{f:{title:p.title,author:p.author,name:p.campaign_name||p.title,media:p.media||[],inf:p.influencer_id,country:p.country,sns:p.sns_channel,fmt:p.sns_format,sales:p.sales_channel,pl:p.target,start:p.start,end:p.end,req:p.budget??'',gmv:p.expected_gmv??'',settle:p.settlement_draft?.date||p.settlement_date||'',settleBasis:p.settlement_draft?.basis||'',dl:p.contract_deadline||''},ref:p.reference?.campaign?.campaign_id||'',mode:p.reference?'ref':'new',pick:Object.fromEntries(p.items.map(i=>[i.sku_id,true])),dem:Object.fromEntries(p.items.map(i=>[i.sku_id,i.unit==='EA/주'?i.demand:i.total_quantity*7/((dateMS(i.end)-dateMS(i.start))/864e5+1)])),ver:details.case.version,submitted:false});}
 }
 if(!details)return;
 const c=details.case,p=c.marketing,x=details.execution,a=details.scm_calculation,cat=catalog(),label=planLabel();adapter.catalog=cat;
 if(screen==='SCM_1_Check'){
  logic.SKU=cat;logic.PLAN={id:label,title:c.title,pl:p.target||cat.find(k=>k.id===p.items[0]?.sku_id)?.cat||'기초',start:p.start,end:p.end,sales:p.sales_channel,media:(p.media||[]).join('·'),dl:p.contract_deadline||p.start,author:p.author,asof:p.as_of,dem:Object.fromEntries(p.items.map(i=>[i.sku_id,i.total_quantity*7/((dateMS(i.end)-dateMS(i.start))/864e5+1)]))};
  const r=c.scm?.review;Object.assign(logic.state,{owner:r?.decision_maker||'',reason:r?.reason||'',decision:({'재고로 가능':'ok','정기 보충 확인 필요':'ok','추가 발주 필요':'po','공급 불가':'hard'})[r?.direction]||'',poOn:Object.fromEntries(p.items.map(i=>[i.sku_id,r?.items.find(s=>s.sku_id===i.sku_id)?.procurement==='신규 발주 검토'])),qty:Object.fromEntries((r?.items||[]).filter(i=>i.requested_qty!=null).map(i=>[i.sku_id,String(i.requested_qty)])),odate:r?.items[0]?.planned_order_date||p.as_of,due:r?.items[0]?.requested_payment_date||'',ver:c.version});
 }
 if(screen==='FIN_1_Review'){
  if(details.finance_review_initial){details.finance_review_view=details.finance_review_initial;adapter.financePreview=true;}
  logic.F.fc=workspace.datasets.forecast.rows.map(r=>[r.week,Number(r.projected_closing_krw)]);
  const r=c.finance_review;const skus=c.scm?.review?.items.filter(i=>['신규 발주 검토','기존 발주 변경'].includes(i.procurement))||[];const amount=skus.reduce((n,i)=>n+(i.requested_qty||0)*(i.requested_unit_price||0),0);const ref=p.reference?.campaign?.campaign_id;
  adapter.review=r?structuredClone(r):details.finance_review_draft?structuredClone(details.finance_review_draft):{decision_maker:'',reason:'',evidence:'',opinion:'',alternatives:'',performance_basis:'',requests:[],targets:[{id:'campaign',kind:'캠페인집행',change:'신규 계약',proposal_total:p.group_total??p.budget,annual_amount:null,deadline:p.contract_deadline,basis:'',cash_scope:'표본·현금 합산 제외',payments:[{date:p.settlement_date,amount:p.budget}]},...skus.map(i=>({id:'po-'+i.sku_id,sku_id:i.sku_id,reference_po:i.reference_po||null,kind:'재고발주',change:i.procurement==='기존 발주 변경'?'증량':'추가발주',cash_scope:'미확인',basis:i.note||'',proposal_total:null,annual_amount:null,payments:[{date:i.requested_payment_date,amount:i.requested_qty!=null&&i.requested_unit_price!=null?i.requested_qty*i.requested_unit_price:null}]}))]};
  const fallbackRef=logic.F.camps[ref]?ref:Object.keys(logic.F.camps)[0],inf=logic.F.infs[p.influencer_id]?p.influencer_id:Object.keys(logic.F.infs)[0];logic.PRE.actual={label:label,pid:label,title:c.title,inf,infName:workspace.marketing_reference.influencers.rows.find(i=>i.influencer_id===inf)?.influencer_name||'해당 없음',ref:fallbackRef,req:p.budget||0,settle:p.settlement_date||p.start,dl:p.contract_deadline||p.start,poAmt:amount,poDue:skus[0]?.requested_payment_date||p.start,poEta:skus[0]?.proposed_available_date||p.end,poCount:skus.length,linked:false};
  logic.state.pre='actual';logic.state.kase=skus.length?'po':'no';logic.state.owner=r?.decision_maker||'';logic.state.reason=r?.reason||'';logic.state.op=({'승인':'ok','조건부 승인':'cond','반려':'no'})[r?.opinion]||'';logic.state.scen=workspace.finance.confirmed?({exclude_pay:'nn',collect_pay:'yy',collect_exclude:'yn',exclude_exclude:'nm'})[workspace.finance.selected]:'union';
  // Original chart shapes, authoritative server day series, never embedded sample arithmetic.
  logic.run=(ar,ap,extra)=>{const sid=ar?(ap?'collect_pay':'collect_exclude'):(ap?'exclude_pay':'exclude_exclude');const s=details.finance_review_view.scenarios[sid];return (extra?s.impact_daily:s.daily).map(d=>({t:dateMS(d.date),b:d.closing}));};
 }
 if(screen.startsWith('APR_')){
  const ceo=screen==='APR_1_CEO';const possible=x.targets.filter(t=>(t.authority==='CEO/이사회')===ceo);const names=[...new Set(possible.map(t=>t.authority))];adapter.authorityKeys={};
  const cfg=authority=>{const ts=possible.filter(t=>t.authority===authority);const groups=['캠페인집행','재고발주','연간전속계약'].map((kind,i)=>({key:['camp','po','ctr'][i],kind:['camp','po','ctr'][i],targets:ts.filter(t=>t.kind===kind)})).filter(g=>g.targets.length);return {head:authority||'결재 대상 없음',pid:label,title:c.title,approverRole:'결재 · '+(authority||'해당 없음'),finOp:{label:'재무 의견',memo:c.finance_review?.opinion||'미상신',c:WARN},facts:[['현재 단계',x.status,'#1a1d23','서버 기록'],['하회 구간',cashWindow(),'#b42318','재무 시나리오'],['확정기한',p.contract_deadline||'미확인','#9a3412','마케팅 요청']],w5:reportRows().map(r=>[r.k,r.v]),why:{rule:authority||'판정 대기',ruleNote:'규정 계산 · 신규 유출일과 하회구간 대조',date:ts.flatMap(t=>t.payments).map(d=>d.date||'미확인').join(' · '),sibling:'다른 약정은 해당 결재선에서 별도 결정'},items:groups.map(g=>({key:g.key,kind:g.kind,_targets:g.targets,name:g.targets.map(t=>t.id).join(' · '),sub:g.targets.length+'건 · '+won(g.targets.reduce((n,t)=>n+t.payments.reduce((m,q)=>m+Number(q.amount||0),0),0))+'원 · '+g.targets.map(t=>t.cash_scope).join(' · '),dl:p.contract_deadline||'기한 미확인',dlc:WARN,rec:'ok',recSrc:'재무 검토 의견 · 확정 아님',recWhy:c.finance_review?.opinion||'의견 미확인',condPh:'조건과 재검토 범위를 입력하세요.'}))};};
  if(ceo){logic.CFG.ceo=cfg('CEO/이사회');adapter.authority='CEO/이사회';}else{
   names.forEach((n,i)=>{const k=({'Masil 대표 승인 + 그룹 보고':'ceoM','마케팅팀 전결':'team','SCM 전결':'scm','Masil 대표 승인':'annual'})[n]||'route'+i;logic.CFG.norm[k]=cfg(n);adapter.authorityKeys[k]=n;});
   if(!names.length){logic.CFG.norm.ceoM=cfg('');adapter.authorityKeys.ceoM='';}logic.state.pre=Object.keys(adapter.authorityKeys)[0];
  }
  const ts=ceo?possible:possible.filter(t=>t.authority===adapter.authorityKeys[logic.state.pre]);for(const kind of ['캠페인집행','재고발주','연간전속계약']){const selected=ts.filter(t=>t.kind===kind);const k=({'캠페인집행':'camp','재고발주':'po','연간전속계약':'ctr'})[kind];if(selected.length&&selected.every(t=>t.current)){const d=selected[0].decision;logic.state.dec[k]=({'승인':'ok','조건부 승인':'cond','반려':'no','보류':'no'})[d.decision];logic.state.cond[k]=d.condition;logic.state.memo[k]=d.reason;}}
 }
 if(screen==='SCM_3_PO'){
  const ts=x.targets.filter(t=>t.kind==='재고발주'&&t.change==='추가발주');adapter.orderTargets=ts;
  const lines=ts.map(t=>{const i=c.scm.review.items.find(i=>i.sku_id===t.sku_id),k=cat.find(k=>k.id===t.sku_id);return {id:t.sku_id,name:k.name,moq:k.moq,lt:k.lt,unit:i.requested_unit_price||0,qty:i.requested_qty||0};});
  logic.PRE.actual={label,pid:label,href:approvalHref(),navSub:'서버 승인 기록',dec:ts.length&&ts.every(t=>t.current&&t.decision.decision==='승인')?'승인':'승인 대기',decT:ts.every(t=>t.current&&t.decision.decision==='승인')?'ok':'cond',who:ts.map(t=>t.authority).join(' · '),at:'약정별 사건 이력 참조',cond:ts.map(t=>t.decision?.condition||'조건 없음').join(' · '),condNote:'조건부 승인·범위 변경은 사람 재승인 전 전달 불가',minDue:'',defDue:ts[0]?.payments[0]?.date||'',lines:lines.length?lines:[{id:cat[0].id,name:cat[0].name,moq:cat[0].moq,lt:cat[0].lt,unit:0,qty:1}],existing:c.scm.review?.items.map(i=>i.reference_po).filter(Boolean).join(' · ')||'별도 확인'};logic.state=logic.init('actual');const draft=orderFormDraft(details,cat);Object.assign(logic.state,{owner:draft.owner,f:draft.f,qty:draft.qty,want:draft.want});adapter.orderDraft=draft;
 }
 if(screen==='SCM_5_Receipt'){
  logic.SKU=Object.fromEntries(cat.map(k=>[k.id,k]));const orders=x.orders,receipt=x.receipt;
  const lines=orders.map(o=>{const r=receipt?.lines.find(r=>r.po_id===o.po_id),ships=r?.shipments||[];return {po:o.po_id,id:o.sku_id,qty:o.order_qty,r:{d1:ships[0]?.available_date||'',q1:ships[0]?.qty||'',d2:ships[1]?.available_date||'',q2:ships[1]?.qty||''}};});
  logic.PRE.actual={label,pid:label,href:approvalHref(),navSub:'승인·발주 기록',title:c.title,approver:orders.map(o=>o.approval.authority).join(' · ')||'발주 미전달',cs:p.start,ce:p.end,dem:Object.fromEntries(p.items.map(i=>[i.sku_id,i.total_quantity*7/((dateMS(i.end)-dateMS(i.start))/864e5+1)])),odate:orders[0]?.order_date||p.as_of,reqPay:orders[0]?.payment_due_date||p.as_of,minPay:'',replyDl:orders[0]?.reply_deadline||p.as_of,recv:receipt?.at?.slice(0,10)||p.as_of,pay:receipt?.lines[0]?.payment_date||orders[0]?.payment_due_date||p.as_of,lines:lines.length?lines:[{po:'미전달',id:cat[0].id,qty:0,r:{d1:'',q1:'',d2:'',q2:''}}]};logic.state=logic.init('actual');logic.state.owner=receipt?.decision_maker||c.scm?.review?.decision_maker||'';logic.state.msg=receipt?.message??null;
 }
 if(screen==='MKT_4_Close'){
  const camp=x.targets.find(t=>t.kind==='캠페인집행'),r=x.receipt;
  logic.PRE.actual={label,pid:label,title:c.title,href:approvalHref(),navSub:'약정별 결정 기록',approver:camp?.authority||'승인 대기',campDec:camp?.current?camp.decision.decision:'승인 대기',campCond:camp?.decision?.condition||'',minStart:'',maxReq:p.budget||0,origReq:p.budget||0,origStart:p.start,origEnd:p.end,settle:p.settlement_date||p.start,dl:p.contract_deadline||p.start,infTask:false,poDec:x.orders.length?'서버 발주 기록':'추가 발주 없음',pos:x.orders.map(o=>o.po_id).join(' · ')||'없음',reply:r?r.message:x.supply_review?(x.supply_review.mode==='stock_only'?'현재 재고 기준 SCM 확인 완료':'등록된 공급 회신 검토 완료'):'입고예정 확인 대기',receipts:(r?.lines||[]).flatMap(l=>l.shipments.map(s=>[s.available_date,l.sku_id+' '+s.qty+'EA'])),pay:r?.lines[0]?.payment_date||p.settlement_date||p.start,pending:r?!r.clear:!x.closed&&!x.supply_review,scmMsg:r?.message||x.supply_review?.reason||'⑥ SCM 입고예정 확인 후 일정 정리',skus:p.items.map(i=>({id:i.sku_id,name:cat.find(k=>k.id===i.sku_id)?.name||i.sku_id,ready:p.as_of,tail:'',note:'원본 재고·확인 입고로 종료 시 재검산'}))};logic.state=logic.init('actual');logic.state.owner=x.closed?.decision_maker||'';logic.state.done=!!x.closed;
 }
}
function cashWindow(){const ds=workspace.finance.active_breach_dates;return ds.length?md(ds[0])+' ~ '+md(ds.at(-1)):'하회 없음';}
function approvalHref(){return details.execution.targets.some(t=>t.authority==='CEO/이사회')?'APR_1_CEO.dc.html':'APR_2_Normal.dc.html';}
function reportRows(){const c=details.case,p=c.marketing;return [{k:'누가',v:p.author+' → SCM '+(c.scm?.review?.decision_maker||'미확인')+' → 재무 '+(c.finance_review?.decision_maker||'미확인')},{k:'무엇을',v:c.title+' · '+p.items.map(i=>i.sku_id).join(' · ')},{k:'언제',v:p.start+' ~ '+p.end+' / 확정기한 '+(p.contract_deadline||'미확인')},{k:'어디서',v:'Masil · '+p.sales_channel},{k:'왜',v:p.purpose},{k:'어떻게',v:c.finance_review?.opinion||'담당자 검토·약정별 사람 승인'}];}
function marketingCashGate(){
 const calendar=Object.values(workspace.finance.scenarios)[0].calendar,start=calendar[0].date,end=calendar.at(-1).date,f=logic.state.f;
 const dates=[['캠페인 시작일',f.start],['캠페인 종료일',f.end],['집행비 지급예정일',f.settle]];
 const errors=dates.filter(([label,date])=>!date||date<start||date>end).map(([label,date])=>date?label+' '+date+' · 현금 전망 범위 밖':label+' 입력 필요');
 return {start,end,errors};
}
function renderMarketingCashGate(){
 if(screen!=='MKT_1_Proposal'||readOnly)return;const gate=marketingCashGate(),note=document.createElement('section');note.className='workflow-card';note.setAttribute('aria-label','신청 가능 일정');note.innerHTML=`<h2>신청 가능 일정</h2><p>현재 현금 전망: ${escapeHTML(gate.start)} ~ ${escapeHTML(gate.end)}</p>${gate.errors.length?`<p class="w01-warning" role="alert">${gate.errors.map(escapeHTML).join('<br>')}<br>현재 자료로 재무 판정이 불가능하여 신청할 수 없습니다. 일정을 검토하거나 해당 기간 현금 자료와 전망 범위를 갱신하세요.</p>`:'<p>캠페인 기간과 지급예정일이 현금 전망 범위 안에 있습니다. 재고·현금·결재선은 부서 검토 후 결정됩니다.</p>'}`;
 const info=app.querySelector('section[aria-label="기안 작성"]');if(info)info.after(note);
}
function bindScreen(v){
 if(screen==='MKT_1_Proposal'){
  v.planIdText=details?planLabel()+' · v'+details.case.version:'상신 시 부여';v.pidLabel=details?planLabel():'새 기안';v.submit=submitMarketing;
  const ax=window.W01AX?.status();const estimates=!!ax?.fresh&&ax.inputs.items.length>0&&ax.inputs.items.every(i=>i.demand!==null&&i.qty!==null&&(i.qty===0||i.unit_price>0));
  const budgetMatches=!ax?.fresh||ax.inputs.marketing_cost_inputs?.budget_mode!=='items'||(ax.result.marketing_cost?.adopted_budget!=null&&validCampaignBudget(logic.state.f.req)&&Number(logic.state.f.req)===ax.result.marketing_cost.adopted_budget);
  setChecks(v,[...v.checks.filter(q=>!q.label.includes('정산일')&&!q.label.includes('확정기한')).map(q=>q.label==='요청액'?check('캠페인 집행 예산',validCampaignBudget(logic.state.f.req)):q),check('예상 발주량·비용 계산',estimates),check('마케팅 비용 항목 합계',budgetMatches),check('캠페인·지급일 현금 전망 범위',!marketingCashGate().errors.length)],'캠페인 신청');
  for(const group of v.out||[])for(const row of group.items||[])if(row.label?.startsWith('요청액')){const ok=validCampaignBudget(logic.state.f.req);Object.assign(row,{label:ok?'캠페인 집행 예산 '+won(Number(logic.state.f.req))+'원':'캠페인 집행 예산 미입력',mark:ok?'준비':'누락',bg:ok?OK[0]:WARN[0],fg:ok?OK[1]:WARN[1]});}
  if(v.dlChip?.text.includes('자동 확정'))v.dlChip.text='기한 경과 · 계약 효과·상대방 통보 확인 필요';
  return v;
 }
 if(!details){v.submit=()=>workspaceDialog();return v;}
 const c=details.case,p=c.marketing,x=details.execution,s=logic.state;noMockPresets(v);
 if(v.statusChip)v.statusChip={...v.statusChip,text:x.status+' · v'+c.version};
 if(screen==='SCM_1_Check'){
  const a=details.scm_calculation,ids=new Set(p.items.map(i=>i.sku_id));v.rows=a.items.map(a=>{const old=v.rows.find(r=>r.id===a.sku_id)||v.rows[0]||{};return {...old,id:a.sku_id,name:a.sku.sku_name,oh:won(a.inventory.on_hand_qty),it:won(a.inventory.in_transit_qty),avg:won(a.weekly),inc:won(a.demand.total_quantity)+'EA / 기간',cov0:won(a.cover),cov1:won(a.simple_cover),ss:a.sku.safety_stock_weeks_min,ssText:a.simple_cover>=Number(a.sku.safety_stock_weeks_min)?'이상':'미달',covFg:a.simple_cover>=Number(a.sku.safety_stock_weeks_min)?'#1e6b3a':'#9a3412',poId:a.existing_orders.map(o=>o.original.po_id).join(' · '),poQty:a.existing_orders.map(o=>won(o.original.order_qty)).join(' · '),poDate:a.existing_orders.map(o=>md(o.original.order_date)).join(' · '),poLt:a.sku.lead_time_weeks,poEta:a.existing_orders.map(o=>o.receipt_current&&o.receipt?.status==='확인'?md(o.receipt.available_date):'회신 미확인').join(' · '),so0:a.first_short_in_campaign?md(a.first_short_in_campaign)+'부터 부족':'기간 내 부족 없음',so0Bg:a.first_short_in_campaign?BAD[0]:OK[0],so0Fg:a.first_short_in_campaign?BAD[1]:OK[1],so1:a.procurement.effective_proposal_qty?won(a.procurement.effective_proposal_qty)+'EA 신청 예상안 · 입고 조건 확인':'추가 조달안 없음',so1Bg:WARN[0],so1Fg:WARN[1],v:a.model_status,vBg:a.first_short_in_campaign?WARN[0]:OK[0],vFg:a.first_short_in_campaign?WARN[1]:OK[1]};});
  const advice=a.recommendation,tone=advice.kind==='ready'?OK:advice.kind==='adjust'?BAD:WARN;
  v.poRows=scmOrderRows(a,s);
  v.po={...v.po,count:v.poRows.filter(r=>r.on).length,total:won(v.poRows.reduce((n,i)=>n+(i.amount||0),0))};
  v.rows.forEach(row=>{row.planLabel=advice.kind==='procurement'?(advice.campaign_extra_required?'정기 보충·캠페인 추가 조달 가정':'기존 발주·정기 보충 가정'):'신청 예상안 · 입고 가정';const scenario=advice.scenario?.find(i=>i.sku_id===row.id);if(scenario){row.so1='가정 입고 반영 최소 '+won(scenario.minimum)+'EA';row.so1Bg=OK[0];row.so1Fg=OK[1];if(row.so0!=='기간 내 부족 없음')row.v=advice.kind==='procurement'?'보충 계획 가능 · 공급 조건 확인':'신청안 가능 · 입고 조건 확인';}});
  v.adjHint=advice.actions.find(a=>a.type==='shift_campaign')?.text||advice.actions[0]?.text||'캠페인 기간 공급 검산 결과를 확인하세요.';
  v.rec={...v.rec,label:advice.label,bg:tone[0],bd:tone[0],fg:tone[1],why:[...advice.why,...advice.actions.map(a=>a.text)].map(t=>({t}))};
  const regularOnly=advice.kind==='procurement'&&!advice.campaign_extra_required&&!v.poRows.some(r=>r.on);
  const recommended=advice.kind==='procurement'?(regularOnly?'ok':advice.campaign_extra_required&&v.poRows.some(r=>r.on)?'po':''):advice.kind==='adjust'||advice.kind==='missing'?'':v.poRows.some(r=>r.on)?'po':'ok';
  v.opts.forEach(o=>o.recTag=({'재고로 가능':'ok','추가 발주 필요':'po','공급 어려움':'hard'})[o.label]===recommended?'추천':'');
  if(!readOnly&&s.decision==='ok'&&regularOnly&&!s.scmRegularReasonAdded){const text='정기 보충 계획을 반영하면 캠페인 추가 발주 없이 진행 가능. '+a.replenishment.items.map(i=>i.sku_id+' 정기 보충 '+won(i.regular_qty)+'EA · 캠페인 추가 '+won(i.incremental_qty)+'EA').join(' / ')+'. 미확인 기존 발주와 정기 보충의 입고일·공급능력은 SCM 후속 확인.';if(!s.reason?.includes(text))s.reason=(s.reason?.trim()?s.reason.trim()+'\n':'')+text;s.scmAutoReason=text;s.scmRegularReasonAdded=true;}
  if(s.decision!=='ok'&&s.scmRegularReasonAdded&&!s.scmReasonEdited&&s.reason.endsWith(s.scmAutoReason)){s.reason=s.reason.slice(0,-s.scmAutoReason.length).trim();s.scmRegularReasonAdded=false;}
  v.reason=s.reason;v.onReason=e=>{logic.setState({reason:e.target.value,scmReasonEdited:true,done:false});};
  const differs=!!s.decision&&!!recommended&&s.decision!==recommended;v.reasonReq=differs?'* 추천과 다른 판단의 근거':'(선택)';v.reasonPh=differs?'추천과 다른 판단의 근거를 적어 주세요.':'검토 의견 (선택)';
  v.scmReasonRequired=String(v.reasonReq||'').startsWith('*');
  setChecks(v,[check('대조 담당자',!!s.owner.trim()),check('SCM 판단 선택',!!s.decision),check('SKU·수요 확인',p.items.length>0),check(v.scmReasonRequired?'검토 사유 (필수)':'검토 사유 (선택)',!v.scmReasonRequired||!!s.reason.trim()),check('추가 발주 제품·수량·단가',s.decision!=='po'||v.poRows.some(r=>r.on)&&v.poRows.every(r=>r._ok))],'대조 결과 전달');v.submit=submitScm;
 }
 if(screen==='FIN_1_Review'){
  const fv=details.finance_review_view,b=workspace.finance;v.inp={...v.inp,inf:p.influencer_id||'해당 없음',infName:workspace.marketing_reference.influencers.rows.find(i=>i.influencer_id===p.influencer_id)?.influencer_name||'해당 없음',ref:p.reference?.campaign?.campaign_id||'신규 · 참조 없음'};v.w5=reportRows();v.cases=v.cases.map(r=>({...r,pick:()=>notify('발주안의 변경은 SCM 재검토 후 반영합니다.')}));v.nextHref=approvalHref();v.nextRole=x.targets.some(t=>t.authority==='CEO/이사회')?'CEO/이사회':'평시 승인권자';v.nextLabel='④ '+v.nextRole+' 결재 화면으로';
  const words=[['재무 확정 전','위험일 모두 포함'],['회수 제외·7/1 지급','회수일 미확인'],['7/1 회수·7/1 지급','둘 다 반영한 가정'],['7/1 회수·지급 제외','지급일 미확인'],['회수·지급 모두 제외','두 날짜 모두 미확인']];v.scen=v.scen.map((r,i)=>({...r,label:words[i][0],desc:words[i][1],pick:()=>refreshFinanceScenario(['union','nn','yy','yn','nm'][i])}));
  v.financePreview=!!adapter.financePreview;v.fc.version=adapter.financePreview?'미저장 계산':'현재 재무 기준';v.cashFacts=[{label:'기초 현금',value:won(b.opening)+'원',kind:b.opening_provenance||'원본 사실',source:b.opening_source},{label:'공식 전망 최저',value:won(Math.min(...workspace.datasets.forecast.rows.map(r=>Number(r.projected_closing_krw))))+'원',kind:'부서 전망의 최저값',source:workspace.datasets.forecast.source}];
  v.commits=fv.routes.map(r=>({name:r.kind+' · '+r.id,from:adapter.financePreview?'기안·SCM 입력값':'저장된 재무 검토',date:r.payment.date||(r.kind==='캠페인집행'&&p.settlement_draft?.date)||'미확인',dateNote:!r.payment.date&&r.kind==='캠페인집행'&&p.settlement_draft?'마케팅 참고 초안 · 미확정':adapter.financePreview?'재무 확인 전':'재무 입력값',amt:r.payment.amount==null?'미확인':won(r.payment.amount)+'원',amtNote:r.cash_scope,normal:r.route.normal||'판정 대기',verdict:r.route.status==='판정 불가'?'정보 확인 필요':r.route.authority,vFg:r.route.authority==='CEO/이사회'?'#b42318':'#1d4ed8',rule:r.route.reason.join(' · '),inText:r.route.status,inBg:r.route.authority==='CEO/이사회'?BAD[0]:OK[0],inFg:r.route.authority==='CEO/이사회'?BAD[1]:OK[1],label:r.route.status,bg:r.route.authority==='CEO/이사회'?BAD[0]:OK[0],fg:r.route.authority==='CEO/이사회'?BAD[1]:OK[1]}));
  v.noCommits=v.commits.length===0;
  const perf=fv.performance.sample;v.perf=perf?[{label:'실질 ROAS · '+perf.campaign_id,value:perf.real_roas?.toFixed(2)+' · '+perf.rank+'/'+perf.rank_population+'위',note:'원본 표본 · 비용 가정 별도 확인',fg:perf.real_roas<0?'#b42318':'#1a1d23'},{label:'공헌이익',value:won(perf.contribution)+'원',note:'표본 · 광고비 '+won(perf.marketing_spend)+'원',fg:perf.contribution<0?'#b42318':'#1a1d23'},{label:'반품률',value:(100*perf.refund_rate).toFixed(1)+'%',note:'원본 환불/GMV · 기준일 2026-07-01',fg:'#1a1d23'}]:[{label:'성과·비용 근거',value:'신규 / 원본 참조 없음',note:'성과 미확인 · 재무 확인 필요',fg:'#9a3412'}];const advice=fv.recommendation,tone=advice?.tone==='bad'?BAD:advice?.tone==='ok'?OK:WARN;
  v.rec={...v.rec,label:adapter.financeLoading?'재계산 중':adapter.financeError?'재계산 필요':advice?.label||advice?.action||'검토 데이터 확인',bg:tone[0],fg:tone[1],bd:tone[0],why:adapter.financeLoading?[{t:'선택한 가정으로 현금·승인 경로를 다시 계산합니다.'}]:adapter.financeError?[{t:adapter.financeError}]:advice?.why.map(t=>({t}))||[{t:'판정에 필요한 자료가 없습니다.'}]};
  if(p.settlement_draft&&!fv.routes.some(r=>r.kind==='캠페인집행'&&r.payment.date))v.rec.why.push({t:'마케팅 지급일 초안 '+p.settlement_draft.date+' · '+p.settlement_draft.basis+' · 재무 확인 전 결재 판정에는 반영하지 않습니다.'});
  const labels=['승인 요청 진행','보완 후 승인 요청','보류·재검토'],keys=['ok','cond','no'];v.opts=v.opts.map((o,i)=>({...o,label:labels[i],tag:keys[i]===advice?.opinion?'추천':'',desc:i===0?'계산된 승인권자에게 상신':i===1?'누락 정보·조건 보완 후 상신':'공급·기안 조건 다시 검토'}));
  const differ=!!s.op&&s.op!==advice?.opinion;v.reasonReq=differ?'* 추천과 다른 의견':'(선택)';v.reasonPh=differ?'추천과 다른 의견의 근거':'의견 메모';
  setChecks(v,v.checks.map(q=>q.label.includes('의견 사유')?check('의견 사유',!differ||!!s.reason.trim()):q),advice?.action||'재무 검토 전달');
  if(adapter.financeLoading||adapter.financeError){v.notReady=true;v.submitLabel=adapter.financeLoading?'재계산 중':'재계산 후 진행';}
  v.deadlineNote='다음 처리: '+(advice?.label||advice?.action||'정보 확인')+' · 확정기한 '+(p.contract_deadline||'미확인')+(fv.hypothetical?' · 선택 가정 검토 중':' · 현재 재무 기준');v.dlBox={...v.dlBox,bg:tone[0],fg:tone[1]};v.w5=v.w5.map(r=>r.k==='어떻게'?{...r,v:advice?.action||'정보 확인'}:r);
  const ceo=advice?.items.some(i=>i.ceo_required);v.nextHref=ceo?'APR_1_CEO.dc.html':'APR_2_Normal.dc.html';v.nextRole=ceo?'CEO/이사회':'평시 승인권자';v.nextLabel='④ '+v.nextRole+' 승인 요청';if(advice?.action==='지급정보 보완'){v.nextRole='정보 보완';v.nextHref='FIN_1_Review.dc.html';v.nextLabel='정보 보완 후 재판정';}if(advice?.action==='공급 조정 우선'){v.nextRole='SCM 재검토';v.nextHref='SCM_1_Check.dc.html';v.nextLabel='② 공급 조정 요청';}v.submit=submitFinance;
 }
 if(screen.startsWith('APR_'))return bindCampaignApproval(v);
 if(screen==='SCM_3_PO'){
  const ts=adapter.orderTargets,ids=new Set(ts.map(t=>t.sku_id));v.orderDraftNotes=adapter.orderDraft?.notes||[];v.orderNoTargets=ts.length===0;v.orderHasTargets=ts.length>0;v.orderNextHref=x.stage>=6?'SCM_5_Receipt.dc.html':x.stage===3?'FIN_1_Review.dc.html':x.stage<3?'SCM_1_Check.dc.html':approvalHref();v.orderNextLabel=x.stage>=6?'⑥ 입고예정 회신 확인':x.stage===3?'재무 검토 확인':x.stage<3?'SCM 검토 확인':'승인 현황 확인';
  const review=c.scm?.review,hasPlan=review?.items.some(i=>i.procurement==='신규 발주 검토');
  v.orderPageTitle=v.orderHasTargets?'발주서 작성':hasPlan?'발주안 연결 확인':'추가 발주 없음';
  v.noOrderTitle=hasPlan?'발주안 승인 연결 필요':'추가 발주가 없는 캠페인';v.noOrderMessage=hasPlan?'SCM 발주안이 재무의 신규 발주 승인 대상에 연결되지 않았습니다.':review?.direction==='재고로 가능'?'SCM이 현재 재고로 진행하기로 검토해 새 발주 대상이 없습니다.':'연결된 신규 발주안이 없습니다. SCM 검토 결과를 확인하세요.';
  v.campaignProducts=(p.scope_skus||p.items.map(i=>i.sku_id)).map(id=>{const item=p.items.find(i=>i.sku_id===id),k=adapter.catalog.find(k=>k.id===id),r=review?.items.find(i=>i.sku_id===id);return {id,name:k?.name||'제품명 미확인',demand:item?won(item.total_quantity)+' EA/기간':'수요 미확인',stock:k?won(k.oh)+' EA':'재고 미확인',judgment:r?.supply_result||'검토 전',procurement:r?.procurement||'검토 전'};});v.lines=v.lines.filter(l=>ids.has(l.id));v.rec=v.rec.filter(l=>ids.has(l.sku));v.tot.n=v.lines.length;
  const qtyOK=v.lines.every(l=>Number(l.qty)===l._L.qty&&Number.isInteger(Number(l.qty))&&Number(l.qty)>=l._L.moq),approvalOK=ts.every(t=>t.current&&t.decision.decision==='승인')&&x.targets.filter(t=>t.kind==='캠페인집행').every(t=>t.current&&t.decision.decision==='승인');
  const datesOK=ts.every(t=>t.payments.length===1&&t.payments[0].date===s.f.due);v.lines.forEach((l,i)=>{const po='W01-'+c.id.slice(0,8)+'-'+(i+1),old=l.po;l.po=po;l.qNote=qtyOK?'승인 수량 그대로 · MOQ 최소량 충족':'검토 수량·MOQ와 다름 · 재상신 필요';l.qBd=qtyOK?'#cfd5dd':'#b42318';v.rec.forEach(r=>{if(r.po===old)r.po=po;});v.out.forEach(o=>o.items.forEach(item=>{item.label=item.label.replace(old,po);}));});
  v.dueNote={text:datesOK?'승인된 지급일과 일치 · 하회구간 여부는 승인권한 판정에 반영됨':'승인된 지급일과 다릅니다. 재무 재판정·사람 재승인이 필요합니다.',fg:datesOK?'#1e6b3a':'#b42318'};v.dueBd=datesOK?'#cfd5dd':'#b42318';
  setChecks(v,[check('발주 담당자',!!s.owner.trim()),check('발주일·희망 입고일',!!s.f.odate&&v.lines.every(l=>l.want>=s.f.odate)),check('승인 수량·MOQ 최소량',qtyOK),check('약정별 승인·연결 캠페인 승인',approvalOK),check('승인 지급일·금액 일치',datesOK&&ts.every(t=>{const l=v.lines.find(l=>l.id===t.sku_id);return t.payments[0].amount===Number(l.qty)*l._L.unit;})),check('전달 방식',!!s.f.ch),check('회신 기한',!!s.f.reply&&s.f.reply>=s.f.odate)],'Corevia에 발주서 전달 ('+v.lines.length+'건)');v.submit=submitOrder;if(!ts.length){v.notReady=true;v.submitLabel='승인된 신규 발주 대상이 없습니다';v.src.scope='신규 발주 0건';v.src.dec=x.targets.some(t=>t.kind==='캠페인집행'&&t.current&&t.decision.decision==='승인')?'캠페인 승인 · 추가 발주 없음':'추가 발주안 확인 필요';v.src.condNote='캠페인 집행 승인과 신규 발주 대상은 구분합니다.';}if(x.orders.length){v.notReady=true;v.submitLabel='이미 전달됨 · 회신 확인으로 진행';}
 }
 if(screen==='SCM_5_Receipt'){
  v.receiptHasOrders=x.orders.length>0;v.receiptNoOrders=!v.receiptHasOrders;
  if(!v.receiptHasOrders){
   v.supplyCheckComplete=!!x.supply_review&&x.stage===7&&x.finance_valid;v.supplyCheckPending=!v.supplyCheckComplete;
   v.supplyReviewRows=details.scm_calculation.items.map(i=>({id:i.sku_id,name:i.sku.sku_name,stock:won(i.inventory.on_hand_qty),demand:won(i.demand.total_quantity),po:i.existing_orders.map(p=>p.original.po_id).join(' · ')||'없음',reply:i.existing_orders.map(p=>p.receipt_current&&p.receipt?.status==='확인'?(p.receipt.available_date+' / '+p.receipt.qty+'EA'):'미확인').join(' · ')||'대상 없음'}));
   v.supplyCheckNote=x.supply_review?(x.supply_review.decision_maker+' · '+x.supply_review.reason):'신규 발주가 없어도 SCM이 입고예정 회신 대상을 확인한 뒤 일정 정리로 넘깁니다.';v.submit=submitSupplyCheck;v.notReady=!x.finance_valid||!x.targets.length||!x.targets.every(t=>t.current&&t.decision.decision==='승인');v.submitLabel=v.notReady?'유효한 승인 후 확인 가능':'확인 결과 기록·일정 정리';return v;
  }
  const orders=x.orders,ids=new Set(orders.map(o=>o.po_id));v.lines=v.lines.filter(l=>ids.has(l.po));v.impact=v.impact.filter(l=>orders.some(o=>o.sku_id===l.id));v.src.pos=orders.map(o=>o.po_id).join(' · ')||'발주 전달 기록 없음';v.src.camp=md(p.start)+' ~ '+md(p.end);v.submit=submitReceipt;
  // Source message is an editable proposal; do not claim analysis is a verified receipt.
  if(s.msg===null){v.msg='[규칙 기반 초안 · 담당자 검토 필요] '+planLabel()+'\n'+v.lines.map(l=>l.id+' 판매가능일 '+(l.date1||'미확인')+' '+(l.qty1||'미확인')+'EA').join('\n')+'\n지급일 '+s.f.pay+' · 캠페인 '+p.start+'~'+p.end+' 영향 확인 필요';}v.rec={...v.rec,label:'SCM 담당자 검토·판단 필요',why:[{t:'분할 수량·판매가능일·지급일을 대조한 후 회신하세요. 지급일/수량 변경 시 재무 재판정과 사람 재승인이 필요합니다.'}]};
  if(!orders.length){v.notReady=true;v.submitLabel='발주 전달 후 회신을 기록하세요';}
 }
 if(screen==='MKT_3_Hold')v.submit=submitHold;
 if(screen==='MKT_4_Close'){
  const budgetCheck=v.checks.find(q=>q.label.startsWith('확정 요청액'));if(budgetCheck){Object.assign(budgetCheck,check(budgetCheck.label,validCampaignBudget(s.f.req)&&Number(s.f.req)<=logic.PRE[s.pre].maxReq));setChecks(v,v.checks,'일정 확정·기록 완료');}
  const schedule=details.operational_schedule?.rows||[];
  v.mix=v.mix.map(i=>{const dates=schedule.filter(r=>r.sku_id===i.id).flatMap(r=>r.available.map(s=>s.available_date)).sort();return {...i,state:dates.length?'SCM 확인 입고예정 '+dates.join(' · '):c.execution?.supply_review?.mode==='stock_only'?'현재 재고로 진행 · 추가 발주 없음':'SCM 입고예정 회신 대기'};});
  const timeline=[{date:p.start,label:'캠페인 시작',owner:'마케팅',note:'신청·승인된 캠페인 기간'},{date:p.end,label:'캠페인 종료',owner:'마케팅',note:'신청·승인된 캠페인 기간'},...schedule.flatMap(r=>[{date:r.order_date,label:r.po_id+' 발주 기록',owner:'SCM',note:r.provenance||'SCM 기록'},{date:r.payment_date,label:r.po_id+' 발주 지급예정',owner:'SCM·재무',note:r.payment_basis},...r.available.map(s=>({date:s.available_date,label:r.name+' 입고예정',owner:'SCM',note:won(s.qty)+'EA · 확인 회신 기준'}))])];
  v.miles=timeline.filter(r=>r.date).sort((a,b)=>a.date.localeCompare(b.date)).map(r=>({...r,date:md(r.date),fg:'#1a1d23',noteFg:'#5b6270',dot:'#477bb8'}));
  if(p.submission_mode==='estimate_only'){v.tasks=v.tasks.map(t=>t.label.includes('계약 확정 통보')?{...t,label:'승인·공급 일정 공유',note:'SCM 기록으로 확인된 실행 일정을 관련 담당자에게 공유'}:t);v.checks=v.checks.map(q=>q.label.includes('계약 확정 통보')?{...q,label:'승인·공급 일정 공유'}:q);}
  if(!x.closed&&x.stage!==7){v.notReady=true;v.submitLabel='입고예정 확인 후 정리 가능';}v.resolve=()=>notify('재판정은 재무 검토·상신과 사람 재승인 후에 완료됩니다.');v.submit=submitClose;v.log=details.history.map(e=>({step:e.role,what:e.event,who:e.detail.decision_maker||e.role,when:e.at.slice(5,16),fg:'#374151'}));}
 if(screen.endsWith('Wait')||screen==='SCM_2_WaitApproval'||screen==='SCM_4_WaitReply')bindWait(v);
 return v;
}
function scmOrderRows(calc,state){
 state.scmOrders||={};return calc.items.map(i=>{const q=i.procurement,old=details.case.scm?.review?.items.find(x=>x.sku_id===i.sku_id);let row=state.scmOrders[i.sku_id];
  if(!row){const qty=q.effective_proposal_qty;row=state.scmOrders[i.sku_id]={on:old?old.procurement==='신규 발주 검토':Number(qty)>0,qty:qty==null||qty===0?'':String(qty),price:q.requested_unit_price==null?'':String(q.requested_unit_price),due:q.requested_payment_date||'',orderDate:q.planned_order_date||details.case.as_of,available:q.proposed_available_date||q.lead_time_arrival_assumption||''};}
  const qty=Number(row.qty),price=Number(row.price),valid=row.on&&row.qty!==''&&Number.isSafeInteger(qty)&&qty>=Number(i.sku.moq)&&row.price!==''&&Number.isSafeInteger(price)&&price>0&&Number.isSafeInteger(qty*price);
  return {id:i.sku_id,name:i.sku.sku_name,on:row.on,qty:row.qty,price:row.price,due:row.due,orderDate:row.orderDate,eta:row.available||null,moqRaw:Number(i.sku.moq),amount:valid?qty*price:null,_ok:!row.on||valid};});
}
function bindWait(v){const c=details.case,p=c.marketing,x=details.execution;v.today='기준일 '+p.as_of;v.hero={...v.hero,title:planLabel()+' · '+c.title,chip:x.status,sub:'현재 단계: '+x.status+' · v'+c.version};v.sent=[{t:p.author+' · '+c.title},{t:p.submission_mode==='estimate_only'?'캠페인 집행 예산 '+won(p.budget)+'원 · 상품 조달 예상비 '+won(c.ax_plan?.schedule?.procurement_budget)+'원':'요청 '+won(p.budget)+'원 · 정산 '+(p.settlement_date||'미확인')+' · 확정기한 '+(p.contract_deadline||'미확인')},{t:c.marketing_stage+' · v'+c.version}];const stepMap={'②':2,'③':3,'④':4,'⑤':5,'⑥':6,'⑦':7};v.stages=v.stages.map(s=>{const n=stepMap[s.name[0]]||1,done=x.stage>n,cur=x.stage===n;return {...s,state:done?'기록 있음':cur?'진행 중':'대기',note:cur?x.status:done?'서버 사건 기록 확인':'앞 단계가 끝나면 시작',who:({'②':'SCM','③':'재무','④':'승인권자','⑤':'SCM','⑥':'SCM','⑦':'마케팅'})[s.name[0]]||s.who,chipBg:cur?'#e6eefc':done?OK[0]:'#eef0f3',chipFg:cur?'#1d4ed8':done?OK[1]:'#374151'};});v.log=details.history.slice(-10).map(e=>({t:e.at.slice(5,16)+' · '+e.role+' · '+e.event}));v.hasLog=v.log.length>0;v.acts=v.acts.map(a=>({...a,off:false,run:()=>recordInquiry(a.label)}));v.nexts=v.nexts.map(n=>{const id=n.href.replace('.dc.html',''),ready=id==='MKT_3_Hold'?x.status==='보류·재검토':id==='SCM_3_PO'?x.stage===5:id==='SCM_5_Receipt'?x.stage===6:id==='MKT_4_Close'?x.stage===7:role==='재무';return {...n,ready,notReady:!ready,when:ready?'서버 기록상 담당 업무 확인 가능':'앞 단계 검토·승인을 기다리는 중'};});v.alerts=details.tasks.filter(t=>t.status==='대기').map(t=>({when:t.due||t.role,what:t.title,dot:'#9a3412'}));v.clocks=v.clocks.filter(k=>!k.label.includes('전속')&&(p.submission_mode!=='estimate_only'||!(/기한|정산/.test(k.label)))).map(k=>({...k,note:k.label.includes('전속')?'INF-001 · 별도 통보 확인':'기한 '+(p.contract_deadline||'미확인'),value:k.label.includes('전속')?'7/17':p.contract_deadline?md(p.contract_deadline):'미확인'}));}
async function submitMarketing(){
 const s=logic.state,f=s.f;const gate=marketingCashGate();if(gate.errors.length){notify(gate.errors.join(' / ')+' · 현금 전망 '+gate.start+' ~ '+gate.end);return;}if(values.notReady)return;
 const selected=values.sel.filter(i=>String(s.dem[i.id]??'').trim()!=='');const old=details?.case.marketing;let axInputs;try{axInputs=window.W01AX?.package();}catch(e){notify(e.message);return;}
 const marketingCost=window.W01AX?.status().result?.marketing_cost;const costScope=marketingCost?.enabled&&marketingCost.scope_requires_confirmation&&marketingCost.adopted_budget===Number(f.req);
 const body=(costScope?input('마케팅 예산 적용 범위·근거','budget_basis',old?.budget_basis||marketingCost.method+' · 본 기안의 기간/선택 매체에 적용한 참가자 가정','textarea'):input('마케팅 예산 근거 (직접 입력 시)','budget_basis',old?.budget_basis||'담당자 직접 입력한 마케팅 집행 예산','textarea'))+`<p>원본 기안 화면의 입력을 서버에 저장하고 SCM에 공유합니다. 추가 수요는 참가자 가정이며 승인이나 발주가 아닙니다.</p>${metaFields(f.author,old?.purpose||(axInputs?f.name+' 캠페인 사전검토 근거 확인':''),true,axInputs?selected.map(i=>window.W01AX.basis(i.id)).join('\n'):'')}${input('예상 GMV 산정 범위·근거 (미입력 가능)','gmv_basis',old?.gmv_basis||'','textarea',false)}${choose('성과 자료 상태','performance_status',[['미확인','미확인'],['검토 자료 있음','검토 자료 있음']],old?.performance_status||'미확인')}${input('성과 근거 또는 미확인 사유','performance_basis',old?.performance_unknown_reason||old?.performance_evidence||(axInputs?'성과는 미확인 · 수요·공급·현금의 사전검토와 성과 보장을 구분':''),'textarea')}${selected.map(i=>input(i.id+' 증가 수요 근거 · 순증/중복 확인 포함','basis-'+i.id,window.W01AX?.basis(i.id)||old?.items.find(x=>x.sku_id===i.id)?.basis||'','textarea')).join('')}`;
 await dialog('기안 상신 · 근거 확인',body,async fd=>{
  const r=workspace.marketing_reference.plans.rows.find(p=>p.campaign_id===s.ref),m=meta(fd);
  const p={...(old||{}),title:f.title,campaign_name:f.name,author:f.author,department:old?.department||'마케팅본부',position:old?.position||'',purpose:m.reason,target:f.pl,method:f.media.join(' · '),country:f.country,sales_channel:f.sales,sns_channel:f.sns,sns_format:f.fmt,influencer_id:f.inf,media:f.media,as_of:old?.as_of||'2026-07-01',written_date:old?.written_date||'2026-07-01',start:f.start,end:f.end,budget:f.req,budget_basis:fd.get('budget_basis'),expected_gmv:f.gmv,gmv_basis:fd.get('gmv_basis'),submission_mode:'estimate_only',settlement_date:null,settlement_draft:f.settle?{date:f.settle,basis:f.settleBasis||'마케팅 담당자 입력 · 재무 확인 필요'}:null,contract_deadline:null,reference_plan_id:r?.plan_id||'',performance_status:fd.get('performance_status'),performance_unknown_reason:fd.get('performance_status')==='미확인'?fd.get('performance_basis'):'',performance_evidence:fd.get('performance_status')==='검토 자료 있음'?fd.get('performance_basis'):'',scope_skus:values.sel.map(i=>i.id),scope_basis:m.reason,items:selected.map(i=>({sku_id:i.id,demand:s.dem[i.id],unit:'EA/주',start:f.start,end:f.end,basis:fd.get('basis-'+i.id),confidence:old?.items.find(x=>x.sku_id===i.id)?.confidence||'미확인',overlap:axInputs?'기존 판매 제외한 순증':old?.items.find(x=>x.sku_id===i.id)?.overlap||'중복 여부 미확인'}))};
  const result=await api('/api/marketing',{role:'마케팅',operation:'submit',plan:p,...(axInputs?{ax_inputs:axInputs}:{}),...(caseId?{id:caseId,version:details.case.version}:{submission_key:submissionKey})});dirty=false;go('MKT_2_Wait',result.id);return result;
 },'기안 저장·SCM 검토 요청');
}
async function refreshFinanceScenario(id){
 const currentCase=caseId,serial=adapter.financeScenarioSerial=(adapter.financeScenarioSerial||0)+1;
 adapter.financeLoading=true;adapter.financeError='';logic.setState({scen:id,winOk:false,routeOk:false,done:false});
 try{const map={nn:'exclude_pay',yy:'collect_pay',yn:'collect_exclude',nm:'exclude_exclude',union:'union'},preview=await api('/api/finance-preview?id='+encodeURIComponent(currentCase)+'&scenario='+map[id]);
  if(screen!=='FIN_1_Review'||currentCase!==caseId||serial!==adapter.financeScenarioSerial)return;
  details.finance_review_view=preview;
 }catch(e){if(currentCase===caseId&&serial===adapter.financeScenarioSerial)adapter.financeError=e.message;}
 finally{if(screen==='FIN_1_Review'&&currentCase===caseId&&serial===adapter.financeScenarioSerial){adapter.financeLoading=false;render();}}
}
function orderFormDraft(detail,cat){
 const p=detail.case.marketing,review=detail.case.scm?.review,orders=detail.execution.orders||[],targets=detail.execution.targets.filter(t=>t.kind==='재고발주'&&t.change==='추가발주'),notes=[],qty={},want={};
 const one=xs=>{const values=[...new Set(xs.filter(Boolean))];return values.length===1?values[0]:'';};

 const selected=targets.map(t=>({t,i:review?.items.find(i=>i.sku_id===t.sku_id),o:orders.find(o=>o.target_id===t.id)}));
 let odate=one(selected.map(x=>x.o?.order_date||x.i?.planned_order_date));
 if(!odate&&!selected.some(x=>x.o?.order_date||x.i?.planned_order_date)){odate=p.as_of;notes.push('발주일: 기안 기준일 제안 · 수정 가능');}
 if(!odate)notes.push('발주 예정일이 서로 다름 · 공통 발주일 확인 필요');
 let due=one(selected.map(x=>x.o?.payment_due_date||(x.t.payments.length===1?x.t.payments[0].date:'')));
 if(selected.some(x=>x.t.payments.length!==1||!x.t.payments[0]?.date)||!due){due='';notes.push('지급일이 미확인·상이하거나 분할 지급 · 승인 일정 확인 필요');}
 for(const {t,i,o} of selected){
  const k=cat.find(k=>k.id===t.sku_id);qty[t.sku_id]=o?.order_qty??i?.requested_qty??'';want[t.sku_id]=o?.wanted_date||i?.proposed_available_date||detail.scm_calculation?.planning?.items.find(x=>x.sku_id===t.sku_id)?.order_draft_arrival||'';
  if(!o?.wanted_date&&!i?.proposed_available_date)notes.push(t.sku_id+' 희망 입고일: 발주일+리드타임 가정 · 공급처 확정 아님');
 }
 const existing=orders[0],channel=existing?.channel||'mail',reply=existing?.reply_deadline||one(selected.map(({t})=>detail.scm_calculation?.planning?.items.find(x=>x.sku_id===t.sku_id)?.reply_deadline_hint));
 if(!existing){notes.push('전달 방식: 메일 모의 전달 초안 · 수정 가능');notes.push('회신 기한: 발주일+3영업일 제안 · 공휴일 미반영');}
 const memo=['캠페인: '+(p.campaign_name||detail.case.title)+' ('+p.start+' ~ '+p.end+')',...selected.map(({t,i})=>t.sku_id+' '+(i?.requested_qty??'수량 미확인')+'EA · 승인 지급일 '+(t.payments[0]?.date||'미확인')),'요청 수량·판매가능일·지급일을 확인해 회신해 주세요. 승인 범위 변경은 재검토 후 반영합니다.'].join(' / ').slice(0,3500);
 const evidence=['기안 '+detail.case.id+' · v'+detail.case.version,'SCM 검토: '+(review?.evidence||'미확인'),...selected.map(({t})=>'승인 '+t.id+' · '+(t.decision?.authority||t.authority)+' · '+(t.current?'현재 유효':'재확인 필요')+' · '+(t.decision?.evidence||'근거 미확인'))].join('\n').slice(0,3600);
 return {owner:existing?.decision_maker||review?.decision_maker||'',f:{odate,due,ch:channel,reply,note:existing?.reason||memo},qty,want,notes,evidence};
}
function approvalContext(){
 const authority=logic.MODE==='ceo'?'CEO/이사회':adapter.authorityKeys[logic.state.pre];
 return {authority,targets:details.execution.targets.filter(t=>['캠페인집행','재고발주'].includes(t.kind)&&t.authority===authority)};
}
function bindCampaignApproval(v){
 const state=logic.state,c=details.case,p=c.marketing,x=details.execution,fv=details.finance_review_view,{authority,targets}=approvalContext();
 if(adapter.campaignAuthority!==authority){
  adapter.campaignAuthority=authority;const same=targets.length&&targets.every(t=>t.current&&t.decision.decision===targets[0].decision?.decision);
  state.campaignDecision=same?targets[0].decision.decision:'';state.campaignCondition=same?targets[0].decision.condition||'':'';state.campaignMemo=same?targets[0].decision.reason||'':'';
 }
 v.presets=logic.MODE==='ceo'?[{label:'CEO/이사회',on:'true',bg:'#fff',fg:'#1a1d23',pick:()=>workspaceDialog()}]:Object.entries(adapter.authorityKeys).map(([k,a])=>({label:a||'결재 대상 없음',on:String(state.pre===k),bg:state.pre===k?'#fff':'transparent',fg:'#1a1d23',pick:()=>logic.setState({pre:k})}));
 const reviews=c.scm?.review,finance=c.finance_review;
 v.departmentReviews=[{role:'마케팅',who:p.author||'미확인',status:'기안 요청 · 참가자 가정',comment:p.purpose||'기안 의견 없음',evidence:'캠페인 '+p.start+' ~ '+p.end+' · 요청액 '+won(p.budget)+'원 · '+p.items.map(i=>i.sku_id+' '+i.total_quantity+'EA/기간').join(' / '),alternatives:p.performance_unknown_reason||p.performance_evidence||'추가 의견 없음'},
 {role:'SCM',who:reviews?.decision_maker||'미확인',status:reviews?.direction||'검토 전',comment:reviews?.reason||'검토 사유 미작성 (선택)',evidence:reviews?.evidence||'검토 근거 없음',alternatives:reviews?.alternatives||'조정 의견 없음'},
 {role:'재무',who:finance?.decision_maker||'미확인',status:finance?.opinion?('재무 의견 · '+finance.opinion):'상신 전',comment:finance?.reason||'재무 검토 의견 없음',evidence:finance?.evidence||'재무 근거 없음',alternatives:finance?.alternatives||'재무 대안 없음'}];
 v.approvalReasons=[...(fv.recommendation?.why||[]).filter(t=>t.startsWith('기준:')||t.startsWith('적용:')||t.startsWith('최저')||t.startsWith('30억')),...targets.flatMap(t=>t.routes.map(r=>(r.payment.date||'지급일 미확인')+' · '+won(r.payment.amount)+'원 · '+r.route.reason.join(' / ')))];
 v.campaignDecisionTitle=authority==='SCM 전결'?'발주 승인 여부':'이번 캠페인 승인 여부';v.approvalScope=targets.some(t=>t.kind==='재고발주')?'이번 캠페인에 연결된 발주의 승인 여부를 결정합니다.':'이번 캠페인의 집행 승인 여부를 결정합니다.';
 v.campaignOptions=['승인','조건부 승인','보류','반려'].map(d=>({label:d,on:state.campaignDecision===d,border:state.campaignDecision===d?'#1f5fbf':'#dde2e8',background:state.campaignDecision===d?'#eef4ff':'#fff',pick:()=>logic.setState({campaignDecision:d})}));
 v.campaignShowCondition=state.campaignDecision==='조건부 승인';v.campaignCondition=state.campaignCondition||'';v.onCampaignCondition=e=>logic.setState({campaignCondition:e.target.value});v.campaignMemo=state.campaignMemo||'';v.onCampaignMemo=e=>logic.setState({campaignMemo:e.target.value});v.campaignMemoLabel=['반려','보류'].includes(state.campaignDecision)?'결정 사유 (필수)':'결정 메모 (선택)';
 v.w5=reportRows();v.stamps=[['기안 · 마케팅',p.author],['대조 · SCM',reviews?.decision_maker||'미확인'],['검토 · 재무',finance?.decision_maker||'미확인'],['현재 결재',state.owner||'결재자']].map(([r,who])=>({role:r,who,state:r==='현재 결재'?x.status:'저장된 검토 기록',bg:'#eef0f3',fg:'#374151',bd:'#dde2e8'}));
 const checks=[check('결재자',!!state.owner.trim()),check('유효한 재무 상신',x.finance_valid&&finance?.operation==='submit'),check('캠페인 결정',!!state.campaignDecision),check('승인 조건',!v.campaignShowCondition||!!state.campaignCondition?.trim()),check('보류·반려 사유',!['반려','보류'].includes(state.campaignDecision)||!!state.campaignMemo?.trim())];
 if(authority==='마케팅팀 전결')checks.push(check('기안자와 결재자 분리',state.owner.trim()!==p.author));
 const campaignTargets=targets.filter(t=>t.kind==='캠페인집행'),poTargets=targets.filter(t=>t.kind==='재고발주');
 const money=ts=>ts.some(t=>t.payments.some(p=>p.amount==null))?'금액 확인 필요':won(ts.reduce((n,t)=>n+t.payments.reduce((s,p)=>s+Number(p.amount),0),0))+'원';
 v.approvalRequestType=campaignTargets.length&&poTargets.length?'캠페인·발주 승인 요청':poTargets.length?'재고 발주 승인 요청':campaignTargets.length?'캠페인 집행 승인 요청':'승인 요청 확인 필요';
 v.approvalCampaignName=p.campaign_name||c.title;
 v.approvalRequestIntent=campaignTargets.length&&poTargets.length?'이번 캠페인 집행과 연결된 발주를 함께 승인해 주세요.':poTargets.length?'이번 캠페인에 필요한 재고 발주를 승인해 주세요.':campaignTargets.length?'아래 금액과 일정으로 캠페인을 진행할지 결정해 주세요.':'현재 선택한 결재자에게 요청된 승인 대상이 없습니다.';
 const dates=[...new Set(targets.flatMap(t=>t.payments.map(p=>p.date||'미확인')))].sort();
 v.approvalRequestFacts=[...(campaignTargets.length?[{label:'캠페인 요청액',value:money(campaignTargets),note:[...new Set(campaignTargets.map(t=>t.cash_scope))].join(' · ')}]:[]),...(poTargets.length?[{label:'발주 요청액',value:money(poTargets),note:'이번 캠페인 연결 발주'}]:[]),{label:'캠페인 기간',value:p.start+' ~ '+p.end,note:''},{label:'지급 예정일',value:dates.length>2?dates[0]+' 외 '+(dates.length-1)+'개 일정':dates.join(' · ')||'미확인',note:''}];
 setChecks(v,checks,'캠페인 '+(state.campaignDecision||'결정')+' 기록');if(!targets.length){v.notReady=true;v.submitLabel='승인 요청 확인 필요';}const shortages=(details.portfolio?.items||[]).filter(i=>i.campaign_min==null||i.campaign_min<0);v.approvalReadiness=!x.finance_valid?'재무 검토 변경·미상신 상태입니다. 재무 재검토가 필요합니다.':shortages.length?'참고: 확인된 재고 기준 부족 예상 '+shortages.map(i=>i.sku_id).join(', ')+'. SCM 검토 의견과 현금·결재 흐름을 확인한 뒤 승인 여부를 결정하세요. 공급 예상과 실제 입고는 다릅니다.':'부서 검토와 현재 결재 흐름을 확인한 뒤 결정하세요.';v.items=[];v.submit=submitApproval;return v;
}
function scmHandoffDraft(detail,screenValues,state){
 const lines=[],seen=new Set(),p=detail.case.marketing,items=detail.scm_calculation.items;
 const add=text=>{if(text&&!seen.has(text)){seen.add(text);lines.push(text);}};
 if(p.budget_basis)add('[마케팅 집행 예산 근거] '+p.budget_basis);
 add('기안: '+detail.case.id+' · v'+detail.case.version+' · '+p.start+' ~ '+p.end);
 for(const item of items){
  for(const kind of ['sku','inventory','sales','purchase']){const src=item.sources?.[kind];if(src)add('['+(src.provenance||'출처 구분 미확인')+'] '+src.source+' · v'+src.version);}
  add('[참가자 가정] '+item.sku_id+' 순증 수요 '+item.demand.total_quantity+' EA/기간 · '+(item.demand.basis||'상세 근거는 기안 SKU 수요 가정 참조'));
  add('[계산 결과] '+item.sku_id+' · '+item.model_status+' · 기간 중 첫 부족 '+(item.first_short_in_campaign||'없음')+' · 완료 판매 주차 '+item.weeks.join(', '));
  for(const po of item.existing_orders){
   const r=po.receipt;
   add('기존 발주 '+po.original.po_id+' · '+(po.receipt_current&&r?r.provenance+' / '+r.status+' / '+(r.qty??'수량 미확인')+' EA / 판매가능일 '+(r.available_date||'미확인')+' / '+(r.evidence||'회신 근거 미입력'):'유효한 공급 확인 회신 없음 · 확정 입고로 합산하지 않음'));
  }
 }
 for(const doc of detail.documents||[])add('[첨부 기록 · '+doc.provenance+'] '+doc.name+' · '+doc.role+' · 내용 자동 검증 아님');
 const related=[...new Set((detail.portfolio?.items||[]).flatMap(x=>x.other_case_ids||[]))];
 if(related.length)add('[부서 주장 / 계산 결과] 공유 재고 대조: 승인 수요 약속 기안 '+related.join(', '));
 const labels={time:'캠페인 시기 조정 검토',qty:'판매량 조정 검토',mix:'상품 구성 조정 검토',prod:'생산계획 확인 요청 · 생산능력 자료 미확인'};
 const alternatives=(detail.scm_calculation.recommendation?.actions||[]).map(a=>'[검산한 제안 · 미확정] '+a.text).concat(Object.keys(state.adj||{}).filter(k=>state.adj[k]).map(k=>(labels[k]||k)+' (미확정)'));
 for(const row of screenValues.poRows||[])if(row.on)alternatives.push('[미승인 발주안] '+row.id+' '+row.qty+' EA · 발주 예정 '+(state.odate||'미확인')+' · 지급일 '+(state.due||'미확인')+' · 판매가능일 '+(row.eta||'미확인')+' (추정 · 재무/공급처 확인 필요)');
 if(!alternatives.length){
  const previous=detail.case.scm?.review?.alternatives;
  alternatives.push(previous?'[이전 검토 기록 · 현재 조건 재확인 필요] '+previous:state.decision==='ok'?'추가 공급 조정안 없음 · 현재 재고·확인 입고·입력 수요 가정 기준의 진행 검토':'[검토 후보 · 미확정] 캠페인 시기·판매량·상품 구성 조정 또는 확인 입고 일정 재협의. 담당자 검토 후 확정.');
 }
 const compact=(rows,limit)=>{const text=rows.join('\n');if(text.length<=limit)return text;const note='\n[자동 요약 · 일부 상세 생략] 전체 SKU·공급 회신·첨부 근거는 현재 기안의 검토 자료에서 확인하세요.';return text.slice(0,limit-note.length)+note;};
 return {evidence:compact(lines,3600),alternatives:compact(alternatives,3600)};
}
async function submitScm(){
 const demand=details?.demand_validation;
 if(!demand?.items.length||demand.items.some(i=>i.missing)){
  await window.W01ScmContext?.editDemand();return;
 }
 if(values.notReady)return;const s=logic.state,p=details.case.marketing,draft=scmHandoffDraft(details,values,s);
 await dialog('SCM 대조 결과 · 인계 근거','<p>현재 기안·자료 버전·계산 결과·유효 회신과 선택한 조정안을 자동으로 불러왔습니다. 미확인·미승인 항목을 확인하고 필요한 내용을 수정한 뒤 전달하세요.</p>'+(window.W01ScmContext?.confirmationHtml()||'')+metaFields(s.owner,s.reason,values.scmReasonRequired,draft.evidence)+input('공급 조정·대안 · 자동 초안, 수정 가능','alternatives',draft.alternatives,'textarea',s.decision==='hard'),async fd=>{
  const m=meta(fd);const review={...m,direction:({ok:'재고로 가능',regular:'정기 보충 확인 필요',po:'추가 발주 필요',hard:'공급 불가'})[s.decision],alternatives:fd.get('alternatives')||'',requests:details.case.scm?.review?.requests||[],items:p.items.map(i=>{const x=details.scm_calculation.items.find(x=>x.sku_id===i.sku_id),q=x.procurement,row=values.poRows.find(r=>r.id===i.sku_id),chosen=s.decision==='po'&&row?.on;return {sku_id:i.sku_id,supply_result:s.decision==='ok'?'가능':x.first_short_in_campaign?'조정 필요':'가능',procurement:chosen?'신규 발주 검토':'추가 조달 없음',target_qty:q.target_qty,target_basis:q.target_basis||'',requested_qty:chosen?Number(row.qty):0,requested_unit_price:chosen?Number(row.price):null,requested_payment_date:chosen?(row.due||null):null,planned_order_date:chosen?row.orderDate:null,proposed_available_date:chosen?row.eta:null,reference_po:details.case.scm?.review?.items.find(r=>r.sku_id===i.sku_id)?.reference_po||null,note:m.reason};})};
  await api('/api/scm',{role:'SCM',id:caseId,version:details.case.version,operation:'handoff',mutation_id:crypto.randomUUID(),review,demand_confirmation:demand.ready?undefined:{checked:true,basis:demand.basis,override_reason:String(fd.get('demand_override')||'').trim()},replenishment_checked:details.scm_calculation.recommendation.kind==='procurement'});dirty=false;go('SCM_2_WaitApproval');return true;
 },'검토 결과 저장·재무 인계');}
function financeHandoffDraft(detail,workspace,state,review){
 const plan=detail.case.marketing,view=detail.finance_review_view,advice=view.recommendation,scm=detail.case.scm?.review;
 const compact=lines=>{const text=lines.filter(Boolean).join('\n');return text.length<=3600?text:text.slice(0,3500)+'\n[자동 요약 · 상세 검토 자료 참조]';};
 const source=[];source.push('기안 '+detail.case.id+' · v'+detail.case.version+' · '+plan.start+' ~ '+plan.end);
 for(const kind of ['cash','ar','ap','purchase','forecast']){const d=workspace.datasets[kind];if(d)source.push('['+d.provenance+'] '+d.source+' · v'+d.version);}
 if(scm)source.push('[SCM 검토] '+scm.decision_maker+' · '+scm.direction+' · '+(scm.evidence||'근거 미확인'));
 source.push('[규정] approval_authority_policy.md · covenant_terms_ms.md · calculation_definitions.md §1.2');
 if(advice)source.push('[계산 결과] '+advice.why.join(' / '));
 for(const d of detail.documents||[])source.push('[첨부 기록 · '+d.provenance+'] '+d.name+' · 내용 자동 검증 아님');
 const reason=state.reason?.trim()||review.reason||((state.op===advice?.opinion)?compact(['[시스템 기초판단 초안]',...(advice?.why||[])]):'');
 const alternatives=[];
 if(scm?.alternatives)alternatives.push('[SCM 의견] '+scm.alternatives);
 if(advice?.action==='CEO 승인 요청')alternatives.push('[검토 후보 · 미확정] CEO 승인 요청. 지급일 분할·연기 또는 발주 감량은 담당 부서 협의 후 재계산. 승인 자체가 자금 부족을 해소하지 않음.');
 else if(advice?.action==='공급 조정 우선')alternatives.push('[검토 후보 · 미확정] SCM·마케팅이 수량·시기·구성을 조정한 뒤 재무 재검토.');
 else if(advice?.blockers?.length)alternatives.push('[보완 필요] '+advice.blockers.join(' / '));
 else alternatives.push('[기초판단] 현금·결재 기준상 추가 조정안 없음. '+(advice?.action||'입력 조건 확인 후 승인 요청')+'.');
 const performance=view.performance,sample=performance.sample;let performanceBasis=review.performance_basis||plan.performance_evidence;
 if(!performanceBasis){
  if(sample)performanceBasis=compact(['[계산 결과 · 원본 표본] '+sample.campaign_id+' · 기준일 '+performance.as_of,'실질 ROAS '+sample.real_roas+' · 공헌이익 '+sample.contribution+'원 · 반품률 '+(sample.refund_rate*100).toFixed(1)+'%',...performance.sources.map(s=>'출처 '+s.file),...performance.assumptions]);
  else performanceBasis=compact(['[미확인] '+(plan.performance_unknown_reason||'현재 기안에 연결된 원본 성과 자료 없음'),'미래 캠페인의 실제 성과 미발생. 표본 주문을 전사 수요·현금으로 환산하지 않음.']);
 }
 const targetBasis=review.targets.map(t=>t.basis||compact(['['+(t.kind==='캠페인집행'?'기안 요청값':'SCM 발주안')+'] '+t.id,...t.payments.map(p=>'지급일 '+(p.date||'미확인')+' · 금액 '+(p.amount??'미확인')+'원'),'현금 반영: '+t.cash_scope+' · 재무 확인 전']));
 return {owner:state.owner||review.decision_maker||'',reason,evidence:review.evidence||compact(source),alternatives:review.alternatives||compact(alternatives),performanceBasis,targetBasis};
}
async function submitFinance(){const s=logic.state,r=adapter.review;if(!details)return workspaceDialog();const scenarioMap={nn:'exclude_pay',yy:'collect_pay',yn:'collect_exclude',nm:'exclude_exclude'};const chosen=scenarioMap[s.scen]|| (workspace.finance.confirmed?workspace.finance.selected:''),draft=financeHandoffDraft(details,workspace,s,r);
 const body=`<p>화면·기안·SCM 자료로 자동 초안을 채웠습니다. 기존 입력은 유지하며 미확인 날짜·범위는 추정하지 않습니다. 수정·확인 후 전달하세요. 새 시나리오 선택은 전달 시 재무 확정에 반영됩니다. 결재는 승인권자가 별도로 수행합니다.</p>${metaFields(draft.owner,draft.reason,true,draft.evidence)}${choose('공식 재전망 시나리오','scenario',[['','시나리오를 선택하세요'],...Object.values(workspace.finance.scenarios).map(x=>[x.id,x.ar_policy+' / '+x.ap_policy])],chosen)}${input('의견·조정 대안','alternatives',draft.alternatives,'textarea')}${input('성과·비용표의 출처·집계범위 또는 미확인 사유','performance_basis',draft.performanceBasis,'textarea')}${r.targets.map((t,i)=>`<fieldset><legend>${escapeHTML(t.kind+' · '+t.id)}</legend>${choose('현금 반영 범위','scope-'+i,['전사 현금 반영 확인','표본·현금 합산 제외','미확인'].map(v=>[v,v]),t.cash_scope)}${input('대상별 근거','basis-'+i,draft.targetBasis[i],'textarea')}${t.payments.map((p,j)=>input(t.kind==='캠페인집행'&&details.case.marketing.settlement_draft?'유출일 · 마케팅 참고 초안, 확인 후 수정':'유출일','date-'+i+'-'+j,p.date||((t.kind==='캠페인집행'&&details.case.marketing.settlement_draft?.date)||''),'date')+input('금액 원','amount-'+i+'-'+j,p.amount??'','number')).join('')}</fieldset>`).join('')}`;
 await dialog('재무 검토·상신 확인',body,async fd=>{
  const m=meta(fd),sid=fd.get('scenario');if(!sid)throw Error('공식 시나리오를 선택하세요. 미확정을 평시 결재로 넘기지 않습니다.');
  if(!workspace.finance.confirmed||workspace.finance.selected!==sid){await api('/api/finance',{role:'재무',operation:'confirm',version:workspace.finance_version,selected:sid,weekend_shift:workspace.finance.config.weekend_shift,review_date:workspace.finance.config.review_date,next_review_date:workspace.finance.config.next_review_date,...m});workspace=await api('/api/state');details=await api('/api/cases/'+caseId);window.W01Calculations?.observe(workspace.calculation_context);}
  const review={...r,...m,opinion:({ok:'승인',cond:'조건부 승인',no:'반려'})[s.op]||'검토 의견 미선택',alternatives:fd.get('alternatives'),performance_basis:fd.get('performance_basis'),targets:r.targets.map((t,i)=>({...t,basis:fd.get('basis-'+i),cash_scope:fd.get('scope-'+i),payments:t.payments.map((p,j)=>({date:fd.get('date-'+i+'-'+j),amount:fd.get('amount-'+i+'-'+j)}))}))};
  if(!s.op||!s.winOk||!s.routeOk)throw Error('화면에서 하회구간 확인·결재선 확인·재무 의견을 선택하세요.');
  await api('/api/finance-review',{role:'재무',operation:'submit',id:caseId,version:details.case.version,finance_version:workspace.finance_version,review});dirty=false;go('FIN_2_Wait');return true;
 },'시나리오·검토 근거 확인 후 상신');}
async function submitApproval(){
 if(values.notReady)return;const state=logic.state,{authority,targets}=approvalContext(),caseData=details.case;
 const evidence=['기안 '+caseData.id+' · v'+caseData.version,'SCM 검토: '+(caseData.scm?.review?.evidence||'미확인'),'재무 검토: '+(caseData.finance_review?.evidence||'미확인')].join('\n').slice(0,3600);
 const reason=state.campaignMemo||('이번 캠페인 '+state.campaignDecision+' · '+authority+' · 부서 의견과 결재 흐름 확인');
 await dialog('캠페인 결정 확인','<p>이번 캠페인의 현재 결재권한 범위에 한 번의 결정을 적용합니다. 다른 승인권자의 범위를 대신 승인하지 않습니다.</p>'+metaFields(state.owner,reason,true,evidence)+input('이전 조건부 승인 이행 증빙 (해당 시 필수)','condition_evidence','','textarea',false),async fd=>{
  await api('/api/execution',{role:'승인권자',operation:'campaign_decide',id:caseId,version:details.case.version,mutation_id:crypto.randomUUID(),authority,...meta(fd),decision:state.campaignDecision,condition:state.campaignCondition||'',condition_evidence:fd.get('condition_evidence')||''});dirty=false;const updated=await api('/api/cases/'+encodeURIComponent(caseId));const stage=updated.execution.stage;if(stage>=5)go(stage===5?'SCM_3_PO':stage===6?'SCM_5_Receipt':'MKT_4_Close');else{notify(updated.execution.status);go(screen);}return true;
 },'이번 캠페인 결정 기록');
}
async function submitOrder(){if(values.notReady)return;const s=logic.state;
 await dialog('발주 전달 · 승인 범위 확인',`<p>실제 외부 전송 없이 모의 발주 전달을 기록합니다. 조건부 승인 또는 승인 범위와 다른 금액·수량·지급일은 차단됩니다.</p>${metaFields(s.owner,s.f.note,true,adapter.orderDraft?.evidence||'')}`,async fd=>{
  const lines=adapter.orderTargets.map(t=>{const l=values.lines.find(l=>l.id===t.sku_id);return {target_id:t.id,qty:l.qty,order_date:s.f.odate,payment_date:s.f.due,wanted_date:l.want,reply_deadline:s.f.reply,channel:s.f.ch};});
  await api('/api/execution',{role:'SCM',operation:'order',id:caseId,version:details.case.version,mutation_id:crypto.randomUUID(),...meta(fd),lines});dirty=false;go('SCM_5_Receipt');return true;
 },'모의 발주 전달 기록');}
async function submitSupplyCheck(){
 if(values.notReady)return;const c=details.case,review=c.scm?.review;
 await dialog('입고예정 회신 대상 확인','<p>현재 재고만으로 진행하는지, 등록된 공급 회신을 사용하는지 확인합니다. 외부 회신이나 실제 입고 완료를 새로 만들지 않습니다.</p>'+metaFields(logic.state.owner||review?.decision_maker||'','캠페인 기간 공급과 추가 입고 회신 대상을 확인',true,'기안 '+c.id+' · v'+c.version+'\nSCM 근거: '+(review?.evidence||'미확인'))+choose('확인 기준','mode',[['stock_only','현재 재고로 진행 · 추가 입고 불필요'],['confirmed_po','등록된 공급 회신 확인']],'stock_only'),async fd=>{await api('/api/execution',{role:'SCM',operation:'confirm_supply',id:caseId,version:details.case.version,mutation_id:crypto.randomUUID(),...meta(fd),mode:fd.get('mode')});dirty=false;go('MKT_4_Close');return true;},'확인 기록 후 일정 정리');
}
async function submitReceipt(){if(values.notReady)return;const s=logic.state;
 if(details.execution.receipt?.lines.some(l=>l.shipments.length>2)){notify('이 회신에는 3회 이상 분할 일정이 있습니다. 자료 관리 화면에서 기존 분할 내용을 모두 확인·수정하세요.');return;}
 await dialog('공급처 회신·마케팅 전달 기록',metaFields(s.owner,s.f.chg||s.dec)+`<p>회신은 모의 입력입니다. 지급일·수량 변경 시 재판정되며 실제 입고·지급은 실행하지 않습니다.</p>`,async fd=>{
  const lines=details.execution.orders.map(o=>{const r=s.r[o.po_id];return {po_id:o.po_id,payment_date:s.f.pay,shipments:[{available_date:r.d1,qty:r.q1},...(r.d2?[{available_date:r.d2,qty:r.q2}]:[])]};});
  await api('/api/execution',{role:'SCM',operation:'receipt',id:caseId,version:details.case.version,mutation_id:crypto.randomUUID(),...meta(fd),lines,judgment:({ok:'일정대로 진행',adjust:'캠페인 일정 조정 요청',change:'공급처 변경 요청'})[s.dec]||'',message:s.msg??values.msg});const latest=await api('/api/cases/'+caseId);dirty=false;go(latest.execution.stage===7?'MKT_4_Close':'FIN_1_Review');return true;
 },'회신·전달 이력 저장');}
async function submitHold(){if(values.notReady)return;const s=logic.state;
 await dialog('보류·재검토 · 통보 근거 확인',metaFields(s.owner,s.memo),async fd=>{const m=meta(fd);
  await api('/api/execution',{role:'마케팅',operation:s.dec==='re'?'rework':'withdraw',id:caseId,version:details.case.version,mutation_id:crypto.randomUUID(),notified:!!s.task.notice,...m});dirty=false;go(s.dec==='re'?'MKT_1_Proposal':'MKT_2_Wait');return true;},'통보·재검토 결정 기록');}
async function submitClose(){if(values.notReady)return;const s=logic.state;
 await dialog('일정 확정·검토 회차 종료',metaFields(s.owner,'')+'<p>실제 판매·입고·지급의 완료가 아닌 검토 회차 종료입니다. 승인 조건·회신·재판정·기간 재고를 다시 검증합니다.</p>',async fd=>{
  const m=meta(fd);
  await api('/api/execution',{role:'마케팅',operation:'close',id:caseId,version:details.case.version,mutation_id:crypto.randomUUID(),...m,notified:!!s.task.contract,start:s.f.start,end:s.f.end,budget:s.f.req,sku_ids:Object.keys(s.mix).filter(id=>s.mix[id])});dirty=false;go('MKT_2_Wait');return true;
 },'일정표·통보 기록 확정');}
async function recordInquiry(type){await dialog(type+' · 담당 부서 확인',metaFields('',type)+choose('요청 담당 부서','to_role',Object.keys(screenEntries).map(r=>[r,r]),role==='마케팅'?'SCM':role),async fd=>{await api('/api/execution',{role,operation:'note',id:caseId,version:details.case.version,mutation_id:crypto.randomUUID(),type,to_role:fd.get('to_role'),...meta(fd)});dirty=false;go(screen);return true;},'확인 요청 기록');}
function bindStaticEvidence(){if(!details)return;const c=details.case,p=c.marketing,x=details.execution;const ds=x.targets.filter(t=>t.current).map(t=>t.decision),rejected=ds.filter(d=>['반려','보류'].includes(d.decision));
 const walker=document.createTreeWalker(app,NodeFilter.SHOW_TEXT);for(let n=walker.nextNode();n;n=walker.nextNode()){
  if(n.parentElement.closest('input,textarea,script,style'))continue;
  let text=n.textContent;text=text.replace(/PLAN-02[678]/g,planLabel()).replace(/혜인 기초 캠페인 하반기 확대 집행|토모카 기초 캠페인 일본 확대 집행|초혜핏 선케어 캠페인 가을 확대 집행/g,c.title).replace(/김마케/g,p.author).replace(/이SCM/g,c.scm?.review?.decision_maker||'SCM 미확인').replace(/박재무/g,c.finance_review?.decision_maker||'재무 미확인');
  if(text.includes('기존 발주 입고 예상일은 원본에 칸이 없어'))text='기존 발주의 판매가능일이 확인된 회신만 기준 공급에 반영합니다. 발주일 + 리드타임은 별도 가정이며 확정 회신이 아닙니다.';
  if(text.includes('공식 전망에는 이 두 가지가 반영돼 있지 않습니다.'))text='공식 전망과 차이: 7/21 기존 발주 지급 37.5억원 누락 가능성은 추정입니다. LC-0001의 45→90일 변경과 원본 AR 만기는 확인 사실이며 8/24 입금은 다음 영업일 조정 가정입니다. 공식 전망 내부 마감 정의는 미확인입니다.';
  text=text.replace('→ MOQ 배수로 올림','→ MOQ 최소량 반영').replace('발주 수량이 MOQ 배수','발주 수량이 MOQ 최소량 이상');
  if(screen==='APR_1_CEO'){
   if(text.trim()==='7/21 ~ 8/29')text=cashWindow();if(text.trim()==='4개 시나리오 합집합 · 재전망 v2')text=workspace.finance.confirmed?'재무 확정 · '+workspace.finance.selected:'4개 시나리오 합집합 · 재무 확정 대기';
   if(text.includes('정산 7/27 · 발주 지급 8/21'))text='정산 '+(p.settlement_date||'미확인')+' · 발주 유출일 '+x.targets.filter(t=>t.kind==='재고발주').flatMap(t=>t.payments.map(p=>p.date||'미확인')).join(' · ');
   if(text.includes('세 건 모두 7/17 전에'))text='각 약정의 승인·계약 통보 의무를 별도로 확인합니다. 결정 기록은 실제 지급·외부 통보를 실행하지 않습니다.';
  }
  if(screen==='MKT_3_Hold'){
   if(text.includes('· 참조 캠페인 CMP-0003의 실질'))text='· '+(rejected.map(d=>d.reason+' · '+d.evidence).join(' / ')||'유효한 반려·보류 결정이 없습니다. 실제 결재 기록을 확인하세요.');
   if(text.includes('반려 사유가 수익성이라 같은'))text='실제 반려 사유·재무 의견·공급 검토 근거를 확인한 뒤 변경할 항목을 선택하세요. 다른 인플루언서·상품을 선택하면 원본 성과와 공급 조건을 다시 검토합니다.';
   if(text.trim()==='CEO/이사회 · 7/1 · 사유 코드 수익성')text=rejected.map(d=>d.authority+' · '+d.at.slice(0,10)).join(' / ')||'결정 미확인';
   if(text.includes('캠페인과 무관하게 진행 · 지급일 8/30'))text='캠페인·발주 약정은 별도 결정이며 실제 승인 범위를 확인합니다.';
   if(text.trim()==='7/17 · D-16')text=p.contract_deadline||'확정기한 미확인';
   if(text.includes('통보 기한 7/17 · 마케팅본부 처리'))text=false?'통보 기한 7/17 · 별도 증빙 확인':'연결 전속계약 해당 여부 확인';
  }
  n.textContent=text;
 }
}
