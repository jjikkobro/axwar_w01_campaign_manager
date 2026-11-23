// Restricted template binder: identifiers only, no eval, no arbitrary code expressions.
class DCLogic {
 constructor(props){this.props=props;this.state={};}
 setState(patch){Object.assign(this.state,patch);this.refresh?.();}
}
function designValue(expr,scope){
 expr=expr.trim();if(expr==='false')return false;if(expr==='true')return true;
 if(!/^[a-zA-Z_$][\w$]*(\.[\w$]+)*$/.test(expr))return '';
 return expr.split('.').reduce((v,k)=>v==null?undefined:v[k],scope);
}
function designBind(template,values,handlersAllowed){
 const parsed=document.createElement('template');parsed.innerHTML=template.replace(/<(\/?)(table|thead|tbody|tfoot|tr|th|td|caption|select|optgroup|option)(?=[\s>])/gi,'<$1sc-raw-$2');
 const get=(value,scope)=>{const m=value.match(/^{{\s*(.*?)\s*}}$/);return m?designValue(m[1],scope):value.replace(/{{(.*?)}}/g,(_,e)=>String(designValue(e,scope)??''));};
 function build(node,scope){
  if(node.nodeType===Node.TEXT_NODE)return document.createTextNode(get(node.textContent,scope)??'');
  if(node.nodeType!==Node.ELEMENT_NODE)return document.createDocumentFragment();
  if(node.localName==='sc-for'){
   const f=document.createDocumentFragment(),list=get(node.getAttribute('list'),scope)||[];
   for(const item of list)for(const child of node.childNodes)f.append(build(child,{...scope,[node.getAttribute('as')]:item}));return f;
  }
  if(node.localName==='sc-if'){
   const f=document.createDocumentFragment();if(get(node.getAttribute('value'),scope)||(window.W01Operations&&node.querySelector('section')))for(const child of node.childNodes)f.append(build(child,scope));return f;
  }
  const tag=node.localName.replace(/^sc-raw-/,'');
  if(['script','iframe','object','embed'].includes(tag))return document.createDocumentFragment();
  const el=tag==='svg'||node.namespaceURI==='http://www.w3.org/2000/svg'?document.createElementNS('http://www.w3.org/2000/svg',tag):document.createElement(tag);
  let value;
  for(const a of node.attributes){
   if(a.name.startsWith('sc-camel-on-')||['onclick','onchange'].includes(a.name)){
    const fn=get(a.value,scope),event=a.name.endsWith('change')?'input':'click';
    if(typeof fn==='function'&&handlersAllowed(a.value))el.addEventListener(event,e=>{e.preventDefault();fn(e);});
    else if(tag==='button'){el.disabled=true;el.title='실제 처리는 담당자가 검토 후 실행합니다.';}
    continue;
   }
   if(a.name.startsWith('on')||a.name.startsWith('hint-'))continue;
   const v=get(a.value,scope);if(a.name==='value'){value=v;continue;}
   if(['disabled','checked','selected'].includes(a.name)){if(v)el[a.name]=true;continue;}
   const name=a.name==='sc-camel-view-box'?'viewBox':a.name;
   if(name==='href'&&/^(javascript|data):/i.test(String(v)))continue;
   el.setAttribute(name,String(v??''));
  }
  for(const child of node.childNodes)el.append(build(child,scope));
  if(value!==undefined){if('value'in el)el.value=value??'';else el.setAttribute('value',String(value??''));}
  return el;
 }
 const result=document.createDocumentFragment();for(const n of parsed.content.childNodes)result.append(build(n,values));return result;
}
