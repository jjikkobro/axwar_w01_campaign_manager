/* Cost decomposition only; source sample references never become actual cash. */
(()=>{
 const h=v=>escapeHTML(v),n=v=>v==null?'미확인':won(v);
 function html(cost){
  if(!cost?.enabled)return '';
  return `<details class="scm-context marketing-cost-evidence"><summary>마케팅 예산 산식·근거</summary><p>상품 조달비와 마케팅 집행비는 별도입니다. 인플루언서비는 광고비에 포함된 금액을 분리 표시하며 다시 더하지 않습니다.</p><p>제작비·쿠폰·추가 행사비는 예산 명세의 별도 마케팅비에 입력하세요. 미입력은 실제 비용이 없다는 확정 사실이 아닙니다.</p><div class="scm-context-scroll"><table><thead><tr><th>매체</th><th>고정비</th><th>일별 참고비</th><th>기간비</th><th>비교 캠페인</th></tr></thead><tbody>${cost.items.map(i=>'<tr>'+[i.media,i.available?n(i.fixed_budget)+'원':'자료 없음',i.available?n(i.reference_daily)+'원/일':'직접 입력',i.available?n(i.variable_budget)+'원':'견적 필요',i.campaign_count||0].map(v=>'<td>'+h(v)+'</td>').join('')+'</tr>').join('')}</tbody></table></div><p>${h(cost.method)}</p>${cost.missing.map(x=>'<p>'+h(x)+'</p>').join('')}${cost.limitations.map(x=>'<p>'+h(x)+'</p>').join('')}${cost.items.filter(i=>i.available).map(i=>'<details><summary>'+h(i.media)+' 원본 관측</summary>'+i.observations.map(o=>'<p>'+h(o.campaign_id)+' · '+h(o.start)+'~'+h(o.end)+' · 광고비 '+n(o.cost)+'원 (포함 수수료 '+n(o.included_fee)+'원) · '+h(o.spend_ids.join(', '))+'</p>').join('')+'</details>').join('')}${cost.sources.map(s=>'<p>'+h(s.file)+'</p>').join('')}</details>`;
 }
 function bind(root){const input=root.querySelector('#marketing-other-cost');if(!input)return;input.onchange=()=>{const value=input.value.replaceAll(',','');if(!/^\d*$/.test(value)||!Number.isSafeInteger(Number(value))){notify('별도 마케팅비는 0 이상의 정수로 입력하세요.');return;}W01AX.setOtherCost(value||'0');};}
 window.W01MarketingCostUI={html,bind};
})();
