/* Presentation only: original decision/evidence text and workflow commands remain intact. */
window.W01ReviewPresentation=(()=>{
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const number=v=>v==null?'미확인':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:2});
 const lines=v=>String(v??'').split(/\n+/).map(s=>s.trim()).filter(Boolean);
 const list=items=>'<ul class="review-lines">'+items.map(s=>'<li>'+esc(s.replace(/^[-•]\s*/,''))+'</li>').join('')+'</ul>';
 function full(text,label='전체 내용 확인'){return '<details class="review-detail"><summary>'+esc(label)+'</summary>'+list(lines(text))+'</details>';}
 function prose(text,label='전체 내용 확인'){
  const raw=String(text||'미기록'),parts=raw.split(/\n+|(?<=[.!?])\s+|\s+\/\s+(?=SKU-)/).map(s=>s.trim()).filter(Boolean),shown=parts.slice(0,3).map(s=>s.length>170?s.slice(0,170)+'…':s);
  if(!shown.length)shown.push('미기록');
  return '<div class="review-prose">'+list(shown)+((parts.length>3||parts.some(s=>s.length>170))?full(raw,label):'')+'</div>';
 }
 function saved(review){
  return '<dl class="review-meta"><div><dt>작성자</dt><dd>'+esc(review.decision_maker||'미기록')+'</dd></div><div><dt>담당자 판단</dt><dd>'+esc(review.direction||review.opinion||'미기록')+'</dd></div></dl><div class="review-block"><h3>검토 사유</h3>'+prose(review.reason,'사유 원문')+'</div><div class="review-folds">'+full(review.alternatives||'등록된 대안 없음','대안·후속 조치')+full(review.evidence||'등록된 근거 없음','출처·근거 원문')+'</div>';
 }
 function table(heads,rows){return '<div class="review-table-wrap" tabindex="0" role="region" aria-label="'+esc(heads.join(' · '))+'"><table class="review-table"><thead><tr>'+heads.map(h=>'<th scope="col">'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map((s,i)=>i===0?'<th scope="row">'+esc(s)+'</th>':'<td>'+esc(s)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
 function scmSummary(){
  const a=details.scm_calculation,r=a.recommendation,items=a.replenishment?.items||[],conditional=r.kind==='procurement';
  const intro=conditional?'<div class="review-condition"><strong>정기 보충 입고를 가정한 판단</strong><p>현재 확인된 공급만으로는 부족합니다. 보충 수량·공급능력·입고일·지급일 확인이 필요합니다.</p></div>':prose((r.why||[])[0]||'공급 조건 확인 필요');
  const rows=a.items.map(i=>{const p=items.find(p=>p.sku_id===i.sku_id);return [i.sku?.sku_name+'\n'+i.sku_id,number(i.campaign_min)+' EA',p?number(p.campaign_min_with_extra)+' EA':'미검산',p?number(p.regular_qty)+' EA':'—',p?number(p.incremental_qty)+' EA':'—'];});
  const actions=conditional?items.map(i=>'<article class="review-action"><h4>'+esc(i.name||i.sku_id)+' <small>'+esc(i.sku_id)+'</small></h4><dl><div><dt>발주 검토일</dt><dd>'+esc(i.latest_order_date||'미확인')+'</dd></div><div><dt>리드타임</dt><dd>'+number(i.lead_time_weeks)+'주</dd></div><div><dt>확인할 사항</dt><dd>수량·공급능력·입고일·지급일</dd></div></dl>'+(i.pre_campaign_gap?'<p class="review-risk">기초 수급 공백: '+esc(i.pre_campaign_gap)+'부터 · 캠페인 추가 수요와 구분</p>':'')+'</article>').join(''):(r.actions||[]).map(a=>'<article class="review-action">'+prose(a.text,'대안 근거 전체')+'</article>').join('');
  return intro+table(['제품','확인 공급 기준\n최소 재고','보충 가정 반영\n최소 재고','정기 보충안','캠페인 추가분'],rows)+'<p class="review-caption">기간 중 최소 예상 재고 · 음수는 부족량. 정기 보충안은 확정 입고가 아니며 캠페인 추가 발주와 구분합니다.</p>'+(actions?'<div class="review-block"><h3>SCM 후속 확인</h3><div class="review-actions">'+actions+'</div></div>':'')+full([...(r.why||[]),...(r.actions||[]).map(x=>x.text)].join('\n'),'계산 근거·대안 원문');
 }
 function financeSummary(){
  const r=details.finance_review_view?.recommendation;if(!r)return '';
  const basis=r.basis,dates=basis.breach_dates||[];
  return '<dl class="review-meta"><div><dt>최저 예상 현금</dt><dd>'+number(basis.forecast_min)+'원</dd></div><div><dt>30억 미만 기간</dt><dd>'+esc(dates.length?dates[0]+' ~ '+dates.at(-1):'없음')+'</dd></div></dl>'+table(['검토 대상','지급예정일','금액','판정·필요 조치'],r.items.map(i=>[i.kind==='캠페인집행'?'캠페인 집행비':'상품 조달 · '+i.id.replace(/^po-/,''),i.effective_payment_date||'미확인',number(i.payment.amount)+'원',i.action+(i.missing.length?'\n'+i.missing.join(' · '):'')]))+(r.blockers.length?'<div class="review-condition"><strong>상신 전 확인</strong>'+list(r.blockers)+'</div>':'')+full(r.why.join('\n'),'현금·결재선 판정 근거');
 }
 function ai(text){
  const groups=[];for(const line of lines(text)){const heading=line.match(/^\[([^\]]+)\]\s*(.*)$/);if(heading){groups.push({title:heading[1],rows:heading[2]?[heading[2]]:[]});}else{if(!groups.length)groups.push({title:'검토 내용',rows:[]});groups.at(-1).rows.push(line);}}
  return '<div class="review-ai-groups">'+groups.map(g=>'<section class="review-ai-group"><h4>'+esc(g.title)+'</h4>'+list(g.rows)+'</section>').join('')+'</div>';
 }
 function paint(){
  if(!details)return;
  if(screen==='SCM_1_Check'){
   const section=app.querySelector('section[aria-label="SCM 판단"]'),ul=section?.querySelector(':scope > div > ul');if(ul){const panel=document.createElement('div');panel.className='review-summary';panel.innerHTML=scmSummary();ul.replaceWith(panel);}
  }
  if(screen==='FIN_1_Review'){
   const section=app.querySelector('section[aria-label="상신 의견"]'),ul=section?.querySelector(':scope > div > ul');if(ul){const panel=document.createElement('div');panel.className='review-summary';panel.innerHTML=financeSummary();ul.replaceWith(panel);}
  }
  app.querySelectorAll('.approval-department').forEach(article=>{
   const comment=article.querySelector(':scope > p');if(comment){const content=document.createElement('div');content.innerHTML=prose(comment.textContent,'검토 의견 전체');comment.replaceWith(content);}
   article.querySelectorAll(':scope > details > p').forEach(p=>{const body=document.createElement('div');body.innerHTML=list(lines(p.textContent));p.replaceWith(body);});
  });
  app.querySelectorAll('.workflow-request-reason,.workflow-request-evidence p').forEach(p=>{p.classList.add('review-formatted');p.innerHTML=list(lines(p.textContent));});
  app.querySelectorAll('section p').forEach(p=>{
   if(p.closest('.review-prose,.review-detail,.review-meta,.review-condition,.review-action,.review-ai-groups,.review-table-wrap,.ai-review-panel,.review-summary,form')||p.children.length)return;
   const raw=p.textContent;if(raw.length<240&&lines(raw).length<3)return;
   const content=document.createElement('div');content.className='review-long-text';content.innerHTML=prose(raw,'상세 설명·원문');p.replaceWith(content);
  });
  const ceo=app.querySelector('[aria-label="CEO 상신 사유"]');if(ceo){const rows=[...ceo.querySelectorAll(':scope > p:not(.approval-muted)')];if(rows.length){const block=document.createElement('div');block.className='review-block';block.innerHTML=list(rows.map(p=>p.textContent));rows[0].before(block);rows.forEach(p=>p.remove());}}
 }
 return {saved,prose,full,ai,paint};
})();
