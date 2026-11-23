/* Live formula context. Keep human inputs and block stale writes; never approve. */
(()=>{
 let current=null,checking=false,stale=false,bannerText='';
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),number=v=>v==null?'미확인':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:2});
 function planHtml(plan){
  if(!plan)return '';
  const rows=plan.replenishment?.items||[];
  return `<details class="scm-context common-planning-evidence" data-computed><summary>공통 산식 · 정기 보충·예상 일정 근거</summary><p>마케팅·SCM·재무·승인 화면은 같은 서버 산식을 사용합니다. 예상 입고와 정기 보충은 계산 가정이며 실제 발주·회신 기록과 구분합니다.</p><div class="scm-context-scroll"><table><thead><tr><th>제품</th><th>정기 보충 EA</th><th>캠페인 추가 제안 EA</th><th>예상 입고</th><th>추가 발주 검토시한</th></tr></thead><tbody>${rows.map(r=>{const i=plan.items.find(i=>i.sku_id===r.sku_id);return '<tr>'+[r.name,number(r.regular_qty),number(i?.recommended_qty),i?.earliest_arrival_assumption,i?.order_by].map(v=>'<td>'+esc(v)+'</td>').join('')+'</tr>';}).join('')}</tbody></table></div><p>리드타임+1주 후 예상 재고가 안전재고 이하이면 이번 주 발주 검토. 기존 미입고 물량은 한 번만 반영합니다. 실제 발주량은 담당자의 채택값을 사용합니다.</p>${rows.map(r=>`<details><summary>${esc(r.name)} 보충 일정</summary>${r.regular_orders.length?r.regular_orders.map(o=>'<p>'+esc(o.order_date)+' 발주 검토 → '+esc(o.date)+' 예상 입고 · '+number(o.qty)+'EA</p>').join(''):'<p>기간 내 신규 정기 보충 계산안 없음 · 기존 발주 예상 입고는 별도 확인</p>'}${r.pre_campaign_gap?'<p>기존 수급 공백 '+esc(r.pre_campaign_gap)+'부터 확인 필요</p>':''}</details>`).join('')}<p>${esc(plan.replenishment?.policy.source||'')}</p></details>`;
 }
 function banner(){
  document.getElementById('calculation-update')?.remove();if(!bannerText)return;
  const box=document.createElement('aside');box.id='calculation-update';box.className='calculation-update';box.role='status';const text=document.createElement('span');text.textContent=bannerText;box.append(text);
  if(stale){const button=document.createElement('button');button.type='button';button.textContent='최신 기준 다시 열기';button.onclick=()=>{if(typeof dirty!=='undefined'&&dirty&&!confirm('입력 중인 내용을 다시 작성해야 합니다. 최신 기준을 열까요?'))return;stale=false;bannerText='';load();};box.append(button);}
  document.body.append(box);
 }
 function observe(context){if(!context)return;current=context;banner();}
 function prepare(path,body){
  if(!body||path==='/api/login'||path.startsWith('/api/formulas/'))return body;
  if(stale)throw Error('계산 기준 또는 기안이 변경되었습니다. 최신 기준을 다시 연 뒤 처리하세요.');
  return current?{...body,expected_calculation_revision:current.revision}:body;
 }
 async function check(){
  if(checking||!current||document.visibilityState==='hidden'||(typeof busy!=='undefined'&&busy))return;
  checking=true;
  try{
   const r=await fetch('/api/calculation-version',{cache:'no-store'});if(!r.ok)return;const next=await r.json();if(next.revision===current.revision)return;
   const inDialog=!!document.querySelector('[role=dialog],.design-overlay');
   if(inDialog){stale=true;bannerText='계산 기준이 변경됐습니다. 입력은 유지되며 최신 기준 확인 전에는 저장할 수 없습니다.';banner();return;}
   if(typeof dirty==='undefined'||!dirty){stale=false;bannerText='공통 계산 기준을 갱신했습니다.';await load();return;}
   // Preserve unsaved edits only when the case itself has not changed.
   const oldId=caseId,oldScreen=screen,newWorkspace=await api('/api/state'),newDetails=oldId?await api('/api/cases/'+encodeURIComponent(oldId)):null;
   if(caseId!==oldId||screen!==oldScreen)return;
   if(newDetails&&newDetails.case.version!==details.case.version){stale=true;bannerText='기안 또는 검토 기준이 변경됐습니다. 입력은 보존되며 최신 기안을 확인한 뒤 저장할 수 있습니다.';banner();return;}
   workspace=newWorkspace;details=newDetails;current=newWorkspace.calculation_context;logic.SKU=catalog();window.W01AX?.invalidate();stale=false;bannerText='새 산식을 반영했습니다. 직접 입력은 유지됐으며 예상안은 다시 계산하세요.';render();
  }catch(e){bannerText='계산 기준 갱신을 확인하지 못했습니다. 다시 확인하거나 새로고침하세요.';banner();}
  finally{checking=false;}
 }
 window.W01Calculations={observe,prepare,check,planHtml,revision:()=>current?.revision};
 setInterval(check,10000);window.addEventListener('focus',check);
})();
