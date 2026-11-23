"""Deterministic next-step advice from authoritative routes, never approval."""
MINIMUM=3000000000
NORMAL={'SCM 전결':'SCM 발주 승인 요청','마케팅팀 전결':'마케팅 승인 요청','Masil 대표 승인 + 그룹 보고':'대표 승인·그룹 보고','Masil 대표 승인':'대표 승인 요청'}
def advise(case,review,routes,scenarios,selected,confirmed,errors):
 active=[scenarios[selected]] if confirmed else list(scenarios.values())
 days=sorted({d['date'] for s in active for d in s['impact_daily'] if d['closing']<MINIMUM})
 minimum=min(d['closing'] for s in active for d in s['impact_daily']);targets={t['id']:t for t in review.get('targets',[])};items=[]
 for line in routes:
  if line['kind'] not in ['캠페인집행','재고발주']:continue
  t=targets[line['id']];route=line['route'];p=line['payment'];missing=[]
  if not p['date']:missing.append('지급일 미확인')
  if p['amount'] is None:missing.append('금액 미확인')
  if t['cash_scope']=='미확인':missing.append('현금 반영 범위 확인')
  invalid=route['status']=='판정 불가';authority=route['authority'];ceo=not invalid and authority=='CEO/이사회'
  if invalid:action='지급정보 보완';authority='판정 불가'
  elif ceo:action='CEO 승인 요청'
  elif t['change']=='기존 약정':action='기존 약정 유지'
  elif t['change'] in ['감량','지급일 연기','취소']:action='SCM 변경 검토'
  else:action=NORMAL.get(authority,'승인 경로 확인')
  effective=route.get('adjusted_payment_date') or p['date'];inside=effective in days if effective else None
  items.append({'id':line['id'],'kind':line['kind'],'payment':p,'effective_payment_date':effective,'new_commitment':route.get('new_commitment'),'in_breach':inside,'authority':authority,'action':action,'missing':missing,'reasons':route['reason'],'ceo_required':ceo,'ready':not (invalid or missing or route.get('blocked'))})
 outside={t['id'] for t in review.get('targets',[]) if t['kind'] not in ['캠페인집행','재고발주']}
 blockers=[e for e in errors if not any(e.startswith(i+' ') for i in outside)]
 if not confirmed:blockers.append('재무 시나리오 확정 필요')
 for item in items:blockers.extend(item['id']+' '+x for x in item['missing'])
 if not items:blockers.append('검토 대상 미확인')
 supply=case.get('scm',{}).get('review',{}).get('direction')=='공급 불가'
 if supply:action='공급 조정 우선';opinion='no';tone='bad'
 elif any(i['authority']=='판정 불가' for i in items) or not items:action='지급정보 보완';opinion='cond';tone='warn'
 elif any(i['ceo_required'] for i in items):action='CEO 승인 요청';opinion='cond' if blockers else 'ok';tone='warn'
 elif blockers:action='보완 후 평시 상신';opinion='cond';tone='warn'
 elif any(i['kind']=='재고발주' and i['action']=='SCM 발주 승인 요청' for i in items):action='SCM 발주 승인 요청';opinion='ok';tone='ok'
 elif all(i['action']=='기존 약정 유지' for i in items):action='기존 약정 유지';opinion='ok';tone='ok'
 else:action='캠페인 승인 요청';opinion='ok';tone='ok'
 why=['기준: 영업일 일말 30억원 미만','적용: '+({'exclude_pay':'회수 제외·7/1 지급','collect_pay':'7/1 회수·7/1 지급','collect_exclude':'7/1 회수·지급 제외','exclude_exclude':'회수·지급 모두 제외'}[selected] if confirmed else '재무 미확정 · 4개 가정 합집합'),'최저 예상 잔액 '+format(minimum,',')+'원',('30억 미만 기간 '+days[0]+' ~ '+days[-1]) if days else '검토기간 내 30억 미만 없음']
 for i in items:
  why.append(i['kind']+' · '+i['id']+': '+(i['effective_payment_date'] or '지급일 미확인')+' / '+('금액 미확인' if i['payment']['amount'] is None else format(i['payment']['amount'],',')+'원')+' → '+i['action'])
 if supply:why.append('SCM 공급 불가 의견: 공급 조정·재검토가 먼저 필요')
 if blockers:why.append('상신 전 보완: '+' / '.join(dict.fromkeys(blockers)))
 if not any(i['kind']=='재고발주' for i in items):why.append('추가 발주 대상 없음 · 캠페인 승인만 검토')
 scm=case.get('scm',{}).get('review',{})
 if scm.get('direction')=='추가 발주 필요' and not any(i['kind']=='재고발주' for i in items):why.append('SCM 종합 의견은 추가 발주 필요이나 캠페인 추가 발주 대상은 0건입니다. 정기 보충 계획과 캠페인 추가 발주를 구분해 SCM 의견을 확인하세요.')
 horizon=max(d['date'] for s in active for d in s['impact_daily'])
 start=(case.get('marketing') or {}).get('start')
 if start and start>horizon:why.append('캠페인 시작일 '+start+'은 현재 현금 전망 종료일 '+horizon+' 이후입니다. 해당 기간 전망을 갱신하기 전에는 현금 기준을 판정할 수 없습니다.')
 label=action
 if action=='지급정보 보완':
  blocked=[i for i in items if i['authority']=='판정 불가']
  if blocked and all(i['kind']=='캠페인집행' and not i['payment']['date'] for i in blocked):label='캠페인 집행비 지급일 확인'
  elif blocked and all(i['kind']=='재고발주' and not i['payment']['date'] for i in blocked):label='발주대금 지급일 확인'
  elif blocked and all(any('전망 범위 밖' in reason for reason in i['reasons']) for i in blocked):label='해당 기간 현금 전망 필요'
 return {'action':action,'label':label,'opinion':opinion,'tone':tone,'ready_to_request':not blockers and not supply and all(i['ready'] for i in items),'items':items,'why':why,'basis':{'minimum_cash':MINIMUM,'forecast_min':minimum,'breach_dates':days,'selected':selected if confirmed else 'union','confirmed':confirmed,'comparison':'영업일 일말 < 3,000,000,000','forecast_end':horizon},'blockers':list(dict.fromkeys(blockers)),'provenance':'계산 결과 · 규칙 기반 기초판단','auto_approved':False,'boundary':'기초판단은 승인 요청 방향입니다. 실제 상신·승인·발주를 자동 실행하지 않습니다.'}
