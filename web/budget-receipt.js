/* One itemised draft: marketing and procurement stay separate in the workflow. */
(()=>{
 const esc=v=>escapeHTML(v),fmt=v=>v==null||v===''?'':Number(v).toLocaleString('ko-KR');
 const value=(v)=>v===''||v==null?null:Number(v);
 function input(label,id,val,attrs=''){return `<label>${esc(label)}<input id="${esc(id)}" inputmode="numeric" type="text" value="${esc(fmt(val))}" ${attrs}></label>`;}
 function bindMoney(el,save){
  el.dataset.last=el.value;
  el.addEventListener('input',()=>{const raw=el.value.replaceAll(',','');if(!/^\d*$/.test(raw)||raw&&!Number.isSafeInteger(Number(raw))){el.value=el.dataset.last||'';notify('0 이상의 정수를 입력하세요.');return;}el.value=raw?Number(raw).toLocaleString('ko-KR'):'';el.dataset.last=el.value;});
  el.addEventListener('change',()=>save(el.value.replaceAll(',','')));
 }
 function paint(){
  if(screen!=='MKT_1_Proposal')return;
  const original=document.getElementById('f-req');if(!original)return;
  original.readOnly=true;original.title='마케팅 비용 항목의 자동 합계';
  const parent=original.parentElement,box=document.createElement('section');box.id='budget-receipt';box.className='budget-receipt';box.tabIndex=-1;box.setAttribute('aria-label','캠페인 예산 명세');
  const status=W01AX.status(),r=status.result,cost=r?.marketing_cost,mode=W01AX.budgetMode(),manual=W01AX.manualCosts(),direct=mode==='direct'||!cost?.enabled;
  const rows=cost?.items||[],dateReady=W01AX.datesReady(),selected=new Set((values.sel||[]).map(i=>i.id)),proc=dateReady?(r?.items||[]).filter(i=>selected.has(i.sku_id)):[];
  const chosen=(row,field)=>{const current=status.inputs.items.find(x=>x.sku_id===row.sku_id);return current?.[field+'_mode']==='manual'?current[field]:!status.fresh?null:field==='qty'?row.chosen_qty:row.chosen_unit_price;};
  const formatTotal=v=>v==null?'확인 필요':fmt(v)+'원';
  const marketingTotal=direct?value(logic.state.f.req):cost?.adopted_budget;
  const rawSum=rows.every(x=>x.chosen_fixed!=null&&x.chosen_variable!=null)?rows.reduce((n,x)=>n+x.chosen_fixed+x.chosen_variable,0)+Number(W01AX.otherCost()||0):null;
  const adjustment=!direct&&rawSum!=null&&marketingTotal!=null?marketingTotal-rawSum:null;
  const procurement=r?.schedule?.procurement_budget,grand=direct?r?.schedule?.campaign_total_requirement:r?.schedule?.adopted_total_requirement;
  const grandAdjustment=grand!=null&&marketingTotal!=null&&procurement!=null?grand-marketingTotal-procurement:null;
  box.innerHTML=`<div class="receipt-head"><div><h3>캠페인 예산 명세</h3><p>예측값을 불러온 뒤 항목별로 수정할 수 있습니다.</p></div><div><button type="button" data-mode="items">항목별 계산</button><button type="button" data-mode="direct">마케팅비 직접 입력</button></div></div>
  <div class="receipt-group"><h4>마케팅 집행비</h4>${rows.some(row=>row.media==='인플루언서')?'<p class="receipt-note">인플루언서 비용은 고정비에 포함해 입력하고, 같은 비용을 기간비에 다시 넣지 마세요.</p>':''}${direct?input('마케팅 집행비 직접 입력 (원)','budget-direct',logic.state.f.req):rows.length?rows.map((row,i)=>`<div class="receipt-line"><b>${esc(row.media)}</b>${input('고정비 (원)','budget-fixed-'+i,manual[row.media]?.fixed??row.chosen_fixed,`data-medium="${esc(row.media)}" data-part="fixed"`)}${input('기간비 (원)','budget-variable-'+i,manual[row.media]?.variable??row.chosen_variable,`data-medium="${esc(row.media)}" data-part="variable"`)}<small>${row.fixed_manual||row.variable_manual?'직접 수정 · 참고 근거 유지':row.available?'표본 참고 · 수정 가능':'참고 자료 없음 · 직접 입력'}</small></div>`).join('')+input('별도 마케팅비 (원)','budget-other',W01AX.otherCost()):'<p>매체와 캠페인 기간을 정하고 예상 비용을 계산하세요.</p>'}${status.fresh&&adjustment?`<div class="receipt-total"><span>설정 산식 조정</span><b>${adjustment>0?'+':''}${fmt(adjustment)}원</b></div>`:''}<div class="receipt-total"><span>마케팅 집행 예산 소계</span><b>${status.fresh||direct?formatTotal(marketingTotal):'재계산 필요'}</b></div>${!direct&&status.fresh&&String(logic.state.f.req)!==String(marketingTotal)?'<small>계산 결과를 적용하면 기안 예산에 반영됩니다.</small>':''}</div>
  <div class="receipt-group"><h4>상품 조달 예상비용</h4>${proc.length?proc.map((row,i)=>`<div class="receipt-line"><b>${esc(row.name)}</b>${input('예상 발주량 (EA)','receipt-qty-'+i,chosen(row,'qty'),`data-sku="${esc(row.sku_id)}" data-field="qty"`)}${input('예상 단가 (원)','receipt-price-'+i,chosen(row,'unit_price'),`data-sku="${esc(row.sku_id)}" data-field="price"`)}<strong>${formatTotal(row.estimated_cost)}</strong></div>`).join(''):'<p>SKU 수요와 예상 발주량을 계산하면 표시됩니다.</p>'}<div class="receipt-total"><span>상품 조달비 소계</span><b>${formatTotal(r?.schedule?.procurement_budget)}</b></div></div>
  ${status.fresh&&grandAdjustment?`<div class="receipt-total"><span>전체 합계 산식 조정</span><b>${grandAdjustment>0?'+':''}${fmt(grandAdjustment)}원</b></div>`:''}<div class="receipt-grand"><span>전체 예상 비용 합계</span><b>${status.fresh?formatTotal(direct?r?.schedule?.campaign_total_requirement:r?.schedule?.adopted_total_requirement):'재계산 필요'}</b></div><p class="receipt-note">마케팅비는 캠페인 예산, 상품 조달비는 별도 발주 검토로 전달합니다. 합계는 표본 기반 가정이 포함된 참고치입니다.</p>${status.fresh?(window.W01MarketingCostUI?.html(cost)||''):''}`;
  parent.after(box);
  box.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>W01AX.setBudgetMode(b.dataset.mode));
  const d=box.querySelector('#budget-direct');if(d)bindMoney(d,v=>W01AX.setDirectBudget(v));
  box.querySelectorAll('[data-part]').forEach(el=>bindMoney(el,v=>W01AX.setCostLine(el.dataset.medium,el.dataset.part,v)));
  const other=box.querySelector('#budget-other');if(other)bindMoney(other,v=>W01AX.setReceiptOther(v));
  box.querySelectorAll('[data-sku]').forEach(el=>bindMoney(el,v=>el.dataset.field==='qty'?W01AX.setQty(el.dataset.sku,v):W01AX.setReceiptPrice(el.dataset.sku,v)));
  window.W01MarketingCostUI?.bind(box);
 }
 window.W01BudgetReceipt={paint};
})();
