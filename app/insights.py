"""Operational queues, measured dwell time and explicitly non-authoritative counterfactuals."""
from datetime import datetime,timezone,date,timedelta
from statistics import median
from app.finance_review import view
from app.portfolio import simulate

def forecast_comparison(case,data,config):
 v=view(case,data,config);official=sorted(data['forecast']['rows'],key=lambda r:r['week']);rows=[]
 targets={t['id']:t for t in case.get('finance_review',{}).get('targets',[])}
 for line in v['routes']:
  d=line['payment']['date'];point=next((r for r in official if d and r['week']<=d<=(date.fromisoformat(r['week'])+timedelta(days=6)).isoformat()),None)
  normal=line['route'].get('normal','판정 불가');value=int(point['projected_closing_krw']) if point else None
  extra=sum(p['amount'] or 0 for t in targets.values() if t['cash_scope']=='전사 현금 반영 확인' and t['change'] in ['신규 계약','추가발주'] for p in t['payments'] if d and p['date'] and p['date']<=d)
  assumed=value-extra if value is not None else None
  counter='판정 불가' if assumed is None or line['route']['status']=='판정 불가' else ('CEO/이사회' if line['route'].get('new_commitment') and assumed<3000000000 else normal)
  rows.append({'id':line['id'],'kind':line['kind'],'payment':line['payment'],'normal':normal,'official_week':point['week'] if point else None,'official_point':value,'official_assumed_after_new':assumed,'official_counterfactual_authority':counter,'reforecast_authority':line['route']['authority'],'reforecast_status':line['route']['status'],'changed':counter not in ['판정 불가',line['route']['authority']],'actual_route':line['route'],'official_actionable':False})
 return {'extension':'E1 · 일별 현금 재전망을 실제 약정 결재선과 후속 처리에 연결','source':'A01 §4 필수 확장 · W01 현금 약정 · approval_authority_policy','official_min':min((int(r['projected_closing_krw']) for r in official),default=None),'reforecast_baseline_min':v['scenarios'][v['selected']]['cash_min'],'reforecast_impact_min':v['scenarios'][v['selected']]['impact_min'],'selected':v['selected'],'confirmed':v['confirmed'],'rows':rows,'official_provenance':'부서 주장','counterfactual_provenance':'참가자 가정','reforecast_provenance':'계산 결과','limitation':'공식 자료는 주차 값이며 일별 마감 정의가 없다. 주차 잔액이 지급일 가용현금이라고 보는 반사실 비교만 제공한다. 공식 열은 실제 결재에 사용할 수 없고, 실제 판정은 같은 재전망 시나리오의 영업일 일말 기준이다.','formula':'원본 6/30 종가 + AR 미회수 − PO 미연결 AP − 기존 PO − 별도 확인된 신규 유출. 표본 캠페인 금액 현금 합산 제외.'}
def read_time(raw):
 if not raw:return None
 try:
  d=datetime.fromisoformat(str(raw).replace('Z','+00:00'));return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
 except (ValueError,TypeError):return None
def dwell(cases,events,now=None):
 now=now or datetime.now(timezone.utc);completed=[];current=[]
 for e in events:
  if e['event']!='업무 단계 전이':continue
  d=e['detail'];before=d.get('before')
  if before and d.get('duration_seconds') is not None:completed.append({'case_id':e['case_id'],'role':before.get('owner'),'stage':before.get('status'),'seconds':d['duration_seconds'],'ended_at':e['at'],'evidence':'저장된 단계 전이 사건'})
 for c in cases:
  f=c.get('workflow',{});entered=read_time(f.get('entered_at'))
  if entered:current.append({'case_id':c['id'],'role':f.get('owner'),'stage':f.get('status'),'seconds':max(0,(now-entered).total_seconds()),'entered_at':f['entered_at'],'evidence':'추적 시작 이후 현재 체류 · 이전 기간 추정 없음'})
 summary=[]
 for key in sorted({(x['role'] or '',x['stage'] or '') for x in completed+current}):
  values=[x['seconds'] for x in completed if (x['role'] or '',x['stage'] or '')==key];pending=[x['seconds'] for x in current if (x['role'] or '',x['stage'] or '')==key]
  summary.append({'role':key[0],'stage':key[1],'completed_count':len(values),'median_completed_seconds':median(values) if values else None,'total_completed_seconds':sum(values),'current_count':len(pending),'max_current_seconds':max(pending,default=0),'certainty':'관측된 체류시간. 병목 원인·개선 효과의 인과 추정 아님.'})
 summary.sort(key=lambda r:(r['max_current_seconds'],r['median_completed_seconds'] or 0),reverse=True)
 return {'completed':completed,'current':current,'summary':summary,'clock':'실제 UTC 사건 시각. 업무 기한의 가상기업 검토일과 구분.','untracked_legacy_events':sum(e['event']!='업무 단계 전이' for e in events)}
def queue(cases,tasks,data,config):
 byid={c['id']:c for c in cases};rows=[];financial={};stocks={};today=config['review_date']
 for t in tasks:
  if t['status']!='대기':continue
  c=byid.get(t['case_id']);p=c.get('marketing',{}) if c else {};due=t.get('due') or p.get('contract_deadline');fv=financial.setdefault(c['id'],view(c,data,config)) if c and c.get('finance_review') and c['id'] not in financial else financial.get(c['id']) if c else None
  cash=bool(fv and any(r['route']['authority']=='CEO/이사회' for r in fv['routes']))
  stock=stocks.setdefault(c['id'],simulate(data,c)) if c and c.get('marketing') and c['id'] not in stocks else stocks.get(c['id']) if c else None;short=bool(stock and any(i['campaign_min'] is not None and i['campaign_min']<0 for i in stock['items']))
  missing=bool(stock and any(i['unknown_demand'] for i in stock['items']))
  row={**t,'case_title':c.get('title') if c else '공통 재무 업무','deadline':due,'overdue':bool(due and due<today),'cash_risk':cash,'stock_risk':short,'unknown_demand':missing,'sort_basis':'확정/담당 기한 오름차순 → 현금 상위 승인 → 품절/미확인 → 생성 순','provenance':'계산 결과'}
  rows.append(row)
 rows.sort(key=lambda t:(t['deadline'] or '9999-12-31',not t['cash_risk'],not(t['stock_risk'] or t['unknown_demand']),t.get('created_at',''),t['id']))
 return {'review_date':today,'tasks':rows,'clock':'기한 우선순위는 가상기업 재무 검토일 사용. 체류시간은 실제 사건 시각 사용.'}
def overview(cases,tasks,events,data,config):
 return {'queue':queue(cases,tasks,data,config),'dwell':dwell(cases,events),'portfolio':simulate(data,asof='2026-07-01',end='2026-09-28'),'sources':{'workflow':'A01 §3·5; W01 미해결 지점/확장 질문','history':'PostgreSQL w01_events 전체 사건; 최근 150개 상태 조회와 별도'},'provenance':'계산 결과'}
