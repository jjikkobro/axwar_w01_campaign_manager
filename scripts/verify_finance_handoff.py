import uuid,json
from pathlib import Path
from scripts.verify_finance_review import call
from tests.test_marketing import MarketingTests
x=MarketingTests();x.setUp();plan=x.plan
plan['items']=[{**plan['items'][0],'sku_id':'SKU-2002','demand':100,'end':'2026-07-19'}];plan['end']='2026-07-19'
plan.update(settlement_date='2026-07-27',contract_deadline='2026-07-17',group_total=180803272,group_basis='원본 25건 묶음 비교',group_id='review-test')
cid=call('/api/marketing',{'role':'마케팅','operation':'submit','submission_key':str(uuid.uuid4()),'plan':plan})['id']
d=call('/api/cases/'+cid)
r={'direction':'재고로 가능','decision_maker':'SCM 시연','reason':'기간 공급 확인','evidence':'완료 4주·재고 대조','alternatives':'별도 발주 없음','items':[{'sku_id':i['sku_id'],'supply_result':'가능','procurement':'추가 조달 없음'} for i in plan['items']],'requests':[]}
call('/api/scm',{'role':'SCM','id':cid,'version':d['case']['version'],'mutation_id':str(uuid.uuid4()),'operation':'handoff','review':r})
d=call('/api/cases/'+cid);assert d['case']['marketing_stage']=='재무 검토 요청'
assert d['finance_review_view']['performance']['sample']['rank']==24
from tests.test_finance_review import ReviewTests
f=ReviewTests();f.setUp();r=f.raw;r['targets']=[{'id':'campaign','kind':'캠페인집행','change':'신규 계약','cash_scope':'표본·현금 합산 제외','basis':'원본'+' PLAN-001·표본 규모','proposal_total':180803272,'payments':[{'date':'2026-07-27','amount':18962703}]}]
state=call('/api/state');call('/api/finance-review',{'role':'재무','id':cid,'version':d['case']['version'],'finance_version':state['finance_version'],'operation':'submit','review':r})
d=call('/api/cases/'+cid);assert d['finance_review_view']['valid'];assert d['case']['approval'] is None
packet=d['case']['finance_review']['packet'];assert packet['performance']['sample']['rank']==24
assert packet['cash_impact']['exclude_pay']['impact_min']==1467664440
Path('docs/verification/screen-reviews/03-finance-handoff.json').write_text(json.dumps({'passed':True,'case_id':cid,'checks':['marketing submit','SCM handoff','finance source-performance lookup','finance submission with separate cash scope','packet contains calculations and sources','no approval or order']},ensure_ascii=False,indent=2)+'\n');print('handoff passed',cid)
