/* Shared form defaults only. Identity does not grant authority or submit actions. */
(()=>{
 let profile=null;
 const roles=['마케팅','SCM','재무','승인권자'];
 function currentRole(){
  const p=new URLSearchParams(location.hash.slice(1)),s=p.get('screen')||'';
  return roles.find(r=>r===p.get('role'))||document.documentElement.dataset.role||
   (s.startsWith('SCM_')?'SCM':s.startsWith('FIN_')?'재무':s.startsWith('APR_')?'승인권자':['/campaign','/settings','/operations','/'].includes(location.pathname)?'마케팅':'SCM');
 }
 function name(role=currentRole()){
  if(!profile?.authenticated)return '';
  return profile.user?.display_name||(roles.includes(role)?role:'SCM')+' 담당자 (시연)';
 }
 function fill(root=document){
  if(new URLSearchParams(location.search).has('reference')||new URLSearchParams(location.search).has('parity'))return;
  const inputs=[...(root.querySelectorAll?.('input[name="decision_maker"],input[name="author"],input[name="owner"],input[data-identity]')||[])];
  for(const input of inputs){
   if(input.value.trim()||input.disabled||input.readOnly||input.dataset.identityTouched)continue;
   const value=name();if(!value)continue;
   input.value=value;input.title=profile.user?.display_name?'접속 프로필에서 자동 입력':'개인 로그인 미연결 · 시연 담당자 자동 입력';
  }
 }
 async function refresh(){
  try{const response=await fetch('/api/session',{cache:'no-store'});if(!response.ok)throw Error();profile=await response.json();}
  catch{profile=null;}
  fill();return profile;
 }
 const observer=new MutationObserver(()=>fill());
 observer.observe(document.documentElement,{childList:true,subtree:true});
 document.addEventListener('input',e=>{if(e.target.matches('input[name="decision_maker"],input[name="author"],input[name="owner"],input[data-identity]'))e.target.dataset.identityTouched='true';});
 window.W01Identity={name,fill,refresh,ready:refresh()};
})();
