"""Reproducible, read-only import of the 13 supplied Design Components."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parent.parent
ORDER=['MKT_1_Proposal','MKT_2_Wait','MKT_3_Hold','MKT_4_Close','SCM_1_Check','SCM_2_WaitApproval','SCM_3_PO','SCM_4_WaitReply','SCM_5_Receipt','FIN_1_Review','FIN_2_Wait','APR_1_CEO','APR_2_Normal']
def marketing_planning_labels(markup):
 markup=markup.replace('{{pidLabel}} SKU 수요 가정 (선택)','SKU·수요·공급 검토')
 markup=markup.replace('>보완 입력</span>','>예산·일정 산정에 필요</span>')
 markup=markup.replace('<b style="font-size: 14px">{{x.id}} {{x.name}}</b>','<span style="font-size: 11px; color: #5b6270">제품명</span><b class="marketing-product-name" style="font-size: 14px">{{x.name}}</b><span class="marketing-product-id" style="font-size: 12px; color: #5b6270">{{x.id}}</span>')
 markup=markup.replace('원본 기안에는 SKU별 수요가 없습니다. 넣으면 ② SCM이 재고·입고표와 바로 대조하고, 비워 두면 SCM이 제품라인 기준으로 확인합니다.','SKU와 수요는 발주비·공급 일정 산정에 필요합니다. 예측치를 가져오거나 직접 입력하세요. 미입력 값은 0으로 확정하지 않습니다.')
 markup=markup.replace('SKU 수요 가정 없음 — 제품라인 기준으로 ② SCM에 넘어갑니다.','제품을 추가해 수요·발주비·일정을 검토하세요.')
 markup=markup.replace('정산일은 ③ 재무가 현금 하회구간과 대조하는 날짜입니다. 계약 확정기한이 지나면 자동 확정되어 철회할 수 없습니다.','정산일·계약 확정기한은 기안 제안값입니다. 산정 가정과 실제 계약 조건을 담당자가 확인합니다.')
 markup=markup.replace('요청액 (원)','캠페인 집행 예산 (원)')
 return markup

def scm_remove_duplicate_order(markup):
 markup=markup.replace('품절 예상 · 현재 발주 기준','품절 예상 · 확인 공급 기준').replace('발주안 반영 후','{{r.planLabel}}')
 start=markup.find('<sc-if value="{{showPo}}"')
 if start>=0:
  end=markup.index('</sc-if>',start)+len('</sc-if>')
  markup=markup[:start]+markup[end:]
 return markup

def scm_results_layout(markup):
 """User-confirmed layout: move derived results above the inventory table."""
 start=markup.index('<section aria-label="재고 입고 대조표"')
 end=markup.index('</section>',start)
 card=markup[start:end]
 for label in ['품절 예상 (현재 발주 기준)','발주안 반영 후','판정']:
  card=re.sub(r'<th\b[^>]*>'+re.escape(label)+r'</th>\n?','',card)
 card=re.sub(r'<td\b[^>]*>(?:(?!</td>).)*{{r\.(?:so0|so1|v)}}(?:(?!</td>).)*</td>\n?','',card,flags=re.S)
 summary='''<div class="scm-results" role="group" aria-label="SKU별 판단 결과">
<div class="scm-results-title"><h3>판단 결과</h3><span>자동 계산 · 최종 판단은 SCM 담당자</span></div>
<sc-for list="{{rows}}" as="r" hint-placeholder-count="3">
<div class="scm-result-row">
<div class="scm-result-sku"><b>{{r.id}}</b><span>{{r.name}}</span></div>
<div><span class="scm-result-label">품절 예상 · 현재 발주 기준</span><b class="scm-result-value" style="background: {{r.so0Bg}}; color: {{r.so0Fg}}">{{r.so0}}</b></div>
<div><span class="scm-result-label">발주안 반영 후</span><b class="scm-result-value" style="background: {{r.so1Bg}}; color: {{r.so1Fg}}">{{r.so1}}</b></div>
<div><span class="scm-result-label">판정</span><b class="scm-result-value" style="background: {{r.vBg}}; color: {{r.vFg}}">{{r.v}}</b></div>
</div>
</sc-for>
</div>
'''
 marker='<div style="display: flex; flex-wrap: wrap; gap: 4px">'
 card=card.replace(marker,summary+marker,1).replace('min-width: 1040px','min-width: 900px')
 return markup[:start]+card+markup[end:]

def finance_results_layout(markup):
 """Confirmed concise copy, separate derived judgments from source inputs."""
 start=markup.index('<section aria-label="현금 재전망"');end=markup.index('</section>',start);card=markup[start:end]
 card=card.replace('하회 구간 (적용 시나리오)','30억 미만 기간').replace('하회 구간 확인 · 연체 채권·채무 처리 가정','현금 부족 확인').replace('>시나리오</th>','>연체금 처리 가정</th>').replace('>하회 구간</th>','>30억 미만 기간</th>')
 card=re.sub(r'<div\b[^>]*>(?:(?!</div>).)*{{fc.offMin}}(?:(?!</div>).)*</div>','',card,flags=re.S)
 marker='<div style="display: flex; flex-wrap: wrap; gap: 8px">'
 card=card.replace(marker,'<h3 class="finance-subtitle">판단 결과 · 계산</h3>\n'+marker,1)
 card=card.replace('막대 = 주간 최저 일말 잔액 (빨강: 30억 미만)','주간 최저 잔액').replace('검은 선 = 최소 가용현금 30억','기준선 30억원').replace('파란 테두리 = 재무팀 공식 전망 주말 잔액','공식 전망 주차값')
 card=re.sub(r'<div style="padding: 10px 12px; border-radius: 10px; background: #f6f7f9; font-size: 13px; line-height: 19px; color: #374151">공식 전망과 차이 나는 이유:.*?</div>','<div class="finance-hints"><span>발주 누락 가능성 · 추정</span><span>회수조건 45→90일</span><span>전망 차이 원인 미확인</span></div>',card,flags=re.S)
 facts='''<div class="finance-facts" role="group" aria-label="현금 근거 데이터"><h3 class="finance-subtitle">근거 데이터</h3><sc-for list="{{cashFacts}}" as="f"><div class="finance-fact"><b>{{f.label}}</b><strong>{{f.value}}</strong><span>{{f.kind}}</span><small>{{f.source}}</small></div></sc-for></div>
'''
 mark='<div style="display: flex; flex-direction: column; gap: 8px; padding-top: 12px; border-top: 1px solid #e3e7ec">'
 card=card.replace(mark,facts+mark,1)
 card=card.replace('<b style="font-size: 14px">현금 부족 확인</b>','<b style="font-size: 14px">현금 부족 확인</b><span class="finance-caption">연체금 = 기한 지난 돈</span>')
 card=card.replace('적용 시나리오의 하회 구간 <b>{{fc.window}}</b>을 확인했습니다','<span>30억 미만 기간</span> <b>{{fc.window}}</b> <span>확인 완료</span>')
 card=re.sub(r'<span style="font-size: 12px; color: #5b6270">구간을 좁히는 시나리오를 고르면.*?</span>','<div class="finance-hints"><span>회수 = 받을 돈</span><span>지급 = 줄 돈</span><span>제외 = 날짜 미확인</span><span>선택 후 근거 확인</span></div>',card,flags=re.S)
 markup=markup[:start]+card+markup[end:]
 start=markup.index('<section aria-label="결재선 판정"');end=markup.index('</section>',start);card=markup[start:end]
 card=card.replace('유출일 대조 · 결재선 판정','지급일·결재선 확인')
 card=re.sub(r'<span style="font-size: 13px; color: #374151">① 하회 구간 특정.*?</span>','<div class="finance-hints"><span>지급일·부족기간 비교</span><span>신규약정 상위승인 우선</span></div>',card,flags=re.S)
 summary='''<div class="finance-route-results" role="group" aria-label="결재 판단 결과"><h3 class="finance-subtitle">판단 결과</h3><sc-if value="{{financePreview}}"><span class="finance-caption">미저장 참고 판정</span></sc-if><sc-for list="{{commits}}" as="m"><div class="finance-route-row"><b>{{m.name}}</b><div><span class="finance-caption">구간 판정</span><strong style="color: {{m.inFg}}">{{m.inText}}</strong></div><div><span class="finance-caption">평시 결재선</span><span>{{m.normal}}</span></div><div><span class="finance-caption">적용 결재선</span><strong style="color: {{m.vFg}}">{{m.verdict}}</strong></div><small>{{m.rule}}</small></div></sc-for><sc-if value="{{noCommits}}"><p>검토 대상 미확인</p></sc-if><span class="finance-caption">사람의 승인 전 참고값</span></div><h3 class="finance-subtitle">근거 데이터 · 입력값</h3>
'''
 marker='<div style="border: 1px solid #e3e7ec; border-radius: 10px; overflow-x: auto">';card=card.replace(marker,summary+marker,1)
 for label in ['구간 안?','평시 결재선','판정']:card=re.sub(r'<th\b[^>]*>'+re.escape(label)+r'</th>','',card)
 for key in ['inText','normal','verdict']:card=re.sub(r'<td\b[^>]*>(?:(?!</td>).)*{{m\.'+key+r'}}(?:(?!</td>).)*</td>\n?','',card,flags=re.S)
 card=card.replace('min-width: 860px','min-width: 520px')
 return markup[:start]+card+markup[end:]

def approval_button_in_checklist(markup):
 pattern=r'<button\b[^>]*class="approval-submit"[^>]*>{{submitLabel}}</button>'
 button=re.search(pattern,markup).group(0)
 markup=re.sub(pattern,'',markup)
 start=markup.index('<section aria-label="확정 전 점검"');end=markup.index('</section>',start)
 return markup[:end]+button+'\n'+markup[end:]

def approval_campaign_layout(markup,ceo=False):
 start=markup.index('<section aria-label="'+('현금 영향' if ceo else '결재선 근거')+'"');end=markup.index('</section>',start)+len('</section>')
 reason='''<section aria-label="CEO 상신 사유" class="approval-review-card"><h2>CEO 상신 사유</h2><p class="approval-muted">현금 기준·지급일에 따른 상신</p><sc-for list="{{approvalReasons}}" as="r"><p>{{r}}</p></sc-for></section>''' if ceo else ''
 markup=markup[:start]+reason+markup[end:]
 start=markup.index('<section aria-label="결정"');end=markup.index('</section>',start)+len('</section>')
 replacement='''<section aria-label="부서 검토 의견" class="approval-review-card"><h2>부서 검토 의견</h2><sc-for list="{{departmentReviews}}" as="r"><article class="approval-department"><div class="approval-department-head"><b>{{r.role}}</b><span>{{r.who}}</span><span class="approval-status">{{r.status}}</span></div><p>{{r.comment}}</p><details><summary>근거·조정안</summary><p>{{r.evidence}}</p><p>{{r.alternatives}}</p></details></article></sc-for></section>
<section aria-label="캠페인 승인" class="approval-review-card approval-final"><h2>{{campaignDecisionTitle}}</h2><p class="approval-muted">{{approvalScope}}</p><div class="approval-options" role="radiogroup" aria-label="이번 캠페인 승인 여부"><sc-for list="{{campaignOptions}}" as="o"><label class="approval-option" style="border-color: {{o.border}}; background: {{o.background}}"><input type="radio" name="campaign-decision" checked="{{o.on}}" onChange="{{o.pick}}"><b>{{o.label}}</b></label></sc-for></div><sc-if value="{{campaignShowCondition}}"><label class="approval-field">승인 조건<input id="campaign-condition" value="{{campaignCondition}}" onChange="{{onCampaignCondition}}" placeholder="이행 후 재승인이 필요한 조건"></label></sc-if><label class="approval-field">{{campaignMemoLabel}}<textarea id="campaign-memo" value="{{campaignMemo}}" onChange="{{onCampaignMemo}}" placeholder="검토 의견을 기록하세요"></textarea></label><p class="approval-muted">{{approvalReadiness}}</p><button type="button" class="approval-submit" onClick="{{submit}}" disabled="{{notReady}}">{{submitLabel}}</button></section>'''
 return approval_button_in_checklist(re.sub(r'<button\b(?![^>]*class="approval-submit")[^>]*onClick="{{submit}}"[^>]*>{{submitLabel}}</button>\n?','',markup[:start]+replacement+markup[end:]))

def approval_request_summary(markup):
 start=markup.index('<section aria-label="결재 머리"');end=markup.index('</section>',start)
 head=markup[start:end]
 head=re.sub(r'<h1\b[^>]*>.*?</h1>','<span class="approval-request-type">{{approvalRequestType}}</span><h1 class="approval-request-name">{{approvalCampaignName}}</h1><p class="approval-request-intent">{{approvalRequestIntent}}</p>',head,count=1,flags=re.S)
 summary='''<div class="approval-request-summary" role="group" aria-label="승인 요청 요약"><sc-for list="{{approvalRequestFacts}}" as="f"><div><span>{{f.label}}</span><b>{{f.value}}</b><small>{{f.note}}</small></div></sc-for></div>
'''
 markup=markup[:start]+head+summary+markup[end:]
 markup=re.sub(r'<div\b[^>]*>(?:(?!</div>).)*{{finOp.label}}(?:(?!</div>).)*</div>\n?','',markup,flags=re.S)
 return markup

def order_prefill_layout(markup):
 start=markup.index('<section aria-label="발주서"');end=markup.index('</section>',start)
 card=markup[start:end];marker='<div style="display: flex; flex-wrap: wrap; gap: 14px 16px">'
 notice='''<div class="order-autofill-note"><b>승인 정보로 채운 발주 초안</b><span>승인 수량·단가·지급일과 기안·SCM 계획을 불러왔습니다. 담당자가 확인한 뒤 전달합니다.</span><sc-if value="{{orderHasTargets}}"><details><summary>자동 입력·가정 확인</summary><sc-for list="{{orderDraftNotes}}" as="n"><p>{{n}}</p></sc-for></details></sc-if><sc-if value="{{orderNoTargets}}"><p>현재 연결된 신규 발주안이 없습니다.</p><a href="{{orderNextHref}}">승인 현황·다음 단계 확인</a></sc-if></div>
'''
 card=card.replace(marker,notice+marker,1).replace('수량은 줄일 수 있지만 승인 수량을 넘길 수 없습니다. MOQ 배수만 가능합니다 (m_sku_ms). 단가 = 기존 발주 금액 ÷ 수량','승인 수량·단가·금액·지급일을 사용합니다. 변경은 재검토·재승인이 필요합니다. MOQ는 최소량 기준입니다.')
 return markup[:start]+card+markup[end:]

def order_empty_state_layout(markup):
 for label in ['발주서','발주서 미리보기']:
  start=markup.index('<section aria-label="'+label+'"');end=markup.index('</section>',start)+len('</section>')
  markup=markup[:start]+'<sc-if value="{{orderHasTargets}}">'+markup[start:end]+'</sc-if>'+markup[end:]
 marker='<sc-if value="{{orderHasTargets}}"><section aria-label="발주서"'
 empty='''<sc-if value="{{orderNoTargets}}"><section aria-label="캠페인 제품 확인" class="approval-review-card order-empty-state"><h2>{{noOrderTitle}}</h2><p>{{noOrderMessage}}</p><div class="order-products-scroll"><table class="order-products"><thead><tr><th>제품</th><th>캠페인 순증 수요</th><th>현재고</th><th>SCM 공급 판단</th><th>조달 검토</th></tr></thead><tbody><sc-for list="{{campaignProducts}}" as="r"><tr><td><b>{{r.id}}</b><br>{{r.name}}</td><td>{{r.demand}}</td><td>{{r.stock}}</td><td>{{r.judgment}}</td><td>{{r.procurement}}</td></tr></sc-for></tbody></table></div><p class="approval-muted">위 수량은 캠페인 수요이며 발주 수량이 아닙니다. 추가 발주가 필요하면 SCM 발주안을 검토·승인해야 합니다.</p><div class="w01-row"><a class="w01-button" href="{{orderNextHref}}">{{orderNextLabel}}</a><a class="w01-button" href="SCM_1_Check.dc.html">추가 발주 검토로 돌아가기</a></div></section></sc-if>
'''
 markup=markup.replace(marker,empty+marker,1)
 start=markup.index('<aside ');end=markup.index('</aside>',start)+len('</aside>');markup=markup[:start]+'<sc-if value="{{orderHasTargets}}">'+markup[start:end]+'</sc-if>'+markup[end:]
 markup=markup.replace('발주서 작성 · {{src.pid}}','{{orderPageTitle}} · {{src.pid}}').replace('발주서 작성·전달</h1>','{{orderPageTitle}}</h1>')
 markup=re.sub(r'(<div[^>]*><label for="p-owner".*?</div>)',r'<sc-if value="{{orderHasTargets}}">\1</sc-if>',markup,count=1,flags=re.S)
 return markup

def receipt_target_review_layout(markup):
 labels=['대상 발주','공급처 회신 입력','일정 영향','판단과 마케팅 회신','회신 전 점검']
 for label in labels:
  start=markup.index('<section aria-label="'+label+'"');end=markup.index('</section>',start)+len('</section>');markup=markup[:start]+'<sc-if value="{{receiptHasOrders}}">'+markup[start:end]+'</sc-if>'+markup[end:]
 marker='<sc-if value="{{receiptHasOrders}}"><section aria-label="대상 발주"'
 review='''<sc-if value="{{receiptNoOrders}}"><section aria-label="입고예정 대상 확인" class="approval-review-card"><h2>입고예정 회신 확인</h2><p>{{supplyCheckNote}}</p><div class="order-products-scroll"><table class="order-products"><thead><tr><th>제품</th><th>현재고 EA</th><th>캠페인 순증 EA</th><th>기존 발주</th><th>등록된 입고예정 회신</th></tr></thead><tbody><sc-for list="{{supplyReviewRows}}" as="r"><tr><td><b>{{r.id}}</b><br>{{r.name}}</td><td>{{r.stock}}</td><td>{{r.demand}}</td><td>{{r.po}}</td><td>{{r.reply}}</td></tr></sc-for></tbody></table></div><p class="approval-muted">추가 입고가 필요 없으면 현재 재고 기준으로 확인합니다. 입고에 의존하면 유효한 공급 회신을 먼저 등록해야 합니다.</p><sc-if value="{{supplyCheckPending}}"><button type="button" class="approval-submit" onClick="{{submit}}" disabled="{{notReady}}">{{submitLabel}}</button></sc-if><sc-if value="{{supplyCheckComplete}}"><a href="MKT_4_Close.dc.html">확인 완료 · ⑦ 일정 정리로 이동</a></sc-if><a href="SCM_1_Check.dc.html">기존 발주 회신·공급 검토 확인</a></section></sc-if>
'''
 return markup.replace(marker,review+marker,1)

def main():
 out=ROOT/'web/screens';out.mkdir(exist_ok=True)
 manifest={'source':'W01_screens','screens':[],'files':{},'presentation':'original-markup-and-component-logic','font':'IBM Plex Sans KR'}
 components=['// Generated verbatim component logic from user-supplied screens.','window.SourceScreens = {};']
 refs=ROOT/'web/references';refs.mkdir(exist_ok=True)
 for p in sorted((ROOT/'W01_screens').rglob('*')):
  if p.is_file():manifest['files'][str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
 for name in ORDER:
  p=ROOT/'W01_screens/screens'/f'{name}.dc.html';s=p.read_text()
  markup=s.split('<x-dc>',1)[1].split('</x-dc>',1)[0]
  markup=re.sub(r'<helmet>.*?</helmet>','',markup,flags=re.S)
  markup=re.sub(r'<script\b.*?</script>','',markup,flags=re.S)
  logic=re.search(r'<script type="text/x-dc"[^>]*>(.*?)</script>',s,re.S).group(1)
  components.append(logic.replace('class Component extends DCLogic',f'window.SourceScreens["{name}"] = class extends DCLogic',1)+';')
  (refs/f'{name}.dc.html').write_text(s)
  if name=='SCM_1_Check':markup=scm_remove_duplicate_order(scm_results_layout(markup))
  if name=='FIN_1_Review':markup=finance_results_layout(markup)
  if name=='SCM_3_PO':markup=order_empty_state_layout(order_prefill_layout(markup))
  if name=='SCM_5_Receipt':markup=receipt_target_review_layout(markup)
  if name=='MKT_1_Proposal':markup=marketing_planning_labels(markup)
  if name.startswith('APR_'):markup=approval_request_summary(approval_campaign_layout(markup,name=='APR_1_CEO'))
  (out/f'{name}.html').write_text(markup.strip()+'\n')
  manifest['screens'].append({'id':name,'role':{'MKT':'마케팅','SCM':'SCM','FIN':'재무','APR':'승인권자'}[name[:3]],'title':re.search(r'<title>(.*?)</title>',s).group(1),'sections':re.findall(r'<section[^>]*aria-label="([^"]*)"',markup)})
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 (ROOT/'web/source-components.js').write_text('\n'.join(components)+'\n')
 print('Imported original markup and component logic for 13 screens; source unchanged')
if __name__=='__main__':main()
