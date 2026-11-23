/* Presentation scope only. Raw server records and cash/authority calculations stay intact. */
window.W01CampaignScope=(()=>{
 const outside=/(?:global:overdue:|finance:contract:|contract_notice|inf001_exclusive_contract_notice|연간전속계약|전속계약|전속 계약|연체\s*(?:회수|확인))/i;
 const hiddenTargets=new Map();
 const target=t=>t.kind==='캠페인집행'||t.kind==='재고발주';
 const task=t=>!outside.test([t.id,t.key,t.title,t.type].filter(Boolean).join(' '));
 const event=e=>!(e.event&&outside.test([e.event,e.detail?.task_id,e.detail?.title,e.detail?.type].filter(Boolean).join(' ')));
 function clean(value,key=''){
  if(Array.isArray(value))return value.filter(x=>!(x&&typeof x==='object'&&(!task(x)||!event(x)||(x.kind&&!target(x)&&x.kind==='연간전속계약')))).map(x=>clean(x)).filter(x=>x!==undefined);
  if(value&&typeof value==='object'){
   if(!task(value)||value.kind==='연간전속계약')return undefined;
   const result={};for(const [k,v] of Object.entries(value)){
    if(['related_contract','contract_notice'].includes(k)||k==='overdue'&&Array.isArray(v))continue;
    if(outside.test(k))continue;
    result[k]=clean(v,k);
   }return result;
  }
  if(typeof value==='string'&&['text','note','reason','limitation'].includes(key))return value.split(/\n/).filter(line=>!outside.test(line)).join('\n');
  return value;
 }
 function present(raw){
  if(raw?.case?.id&&raw.case.finance_review)hiddenTargets.set(raw.case.id,structuredClone(raw.case.finance_review.targets.filter(t=>!target(t))));
  const d=clean(raw);
  if(d?.queue?.tasks)d.queue.tasks=d.queue.tasks.filter(t=>t.case_id||t.id==='global:followup:weekly_cash');
  return d;
 }
 function request(path,body){
  body=window.W01Calculations?.prepare(path,body)||body;
  if(path==='/api/finance-review'&&body?.review?.targets){const saved=hiddenTargets.get(body.id)||[];return {...body,review:{...body.review,targets:[...body.review.targets.filter(target),...saved]}};}
  return body;
 }
 function values(v){
  if('linked' in v)v.linked=false;
  if('noLink' in v)v.noLink=false;
  if(v.inp){v.inp.linked=false;v.inp.noLink=false;}
  if(Array.isArray(v.checks)){const filtered=v.checks.filter(x=>!outside.test(x.label));if(filtered.length!==v.checks.length){v.checks=filtered;v.doneCount=filtered.filter(x=>x.ok).length;v.totalCount=filtered.length;v.notReady=v.doneCount!==v.totalCount;v.submitBg=v.notReady?'#9aa3af':'#1f5fbf';if(!v.notReady)v.submitLabel='검토 결정 기록';}}
  for(const k of ['tasks','clocks','alerts','nexts','log'])if(Array.isArray(v[k]))v[k]=v[k].filter(x=>!outside.test(JSON.stringify(x)));
  if(Array.isArray(v.items))v.items=v.items.filter(x=>x.kind!=='ctr'&&x.key!=='ctr');
  return v;
 }
 function prune(root){
  // Remove dedicated legacy cards and contract-only notices, keeping campaign forms/flow.
  root.querySelectorAll('span,b,strong,p,h2,h3,legend').forEach(el=>{
   if(!el.isConnected||el.children.length||!outside.test(el.textContent))return;
   const card=el.closest('fieldset')||el.closest('div');
   if(card&&card.textContent.length<800&&!card.querySelector('section,table')&&!/캠페인|기안/.test(card.textContent))card.remove();else el.remove();
  });
  root.querySelectorAll('[data-action="contract-notice"],[data-action="overdue"],[data-overdue],#fin-add-contract').forEach(el=>el.remove());
 }
 return {present,request,values,prune,target,task};
})();
