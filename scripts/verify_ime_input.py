import asyncio,json,os,urllib.request
from urllib.parse import urlparse
from playwright.async_api import async_playwright
B=os.environ.get('W01_IME_TEST_BASE_URL','').rstrip('/');u=urlparse(B)
if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost'):raise RuntimeError('로컬 테스트 서버만 허용합니다.')
state=json.load(urllib.request.urlopen(B+'/api/state'));cid=state['cases'][0]['id'];before=[(c['id'],c['version']) for c in state['cases']]
async def main():
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/home/jung/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args=['--no-sandbox']);result=[]
  for screen,sel in [('MKT_1_Proposal','#p-title'),('SCM_1_Check','#s-reason'),('FIN_1_Review','#f-reason'),('APR_2_Normal','#campaign-memo')]:
   p=await b.new_page();errors=[];p.on('pageerror',lambda e:errors.append(e.stack));await p.goto(B+'/campaign#screen='+screen+('' if screen.startswith('MKT') else '&case='+cid));await p.locator('html[data-ready=true]').wait_for();await p.locator(sel).wait_for()
   observation=await p.evaluate('''async selector=>{const el=document.querySelector(selector);el.focus();el.value='';el.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:''}));el.value='재ㄱ';el.dispatchEvent(new InputEvent('input',{bubbles:true,data:'ㄱ',isComposing:true,inputType:'insertCompositionText'}));await new Promise(r=>setTimeout(r,10));const same=el.isConnected&&document.activeElement===el;render();const asyncRenderDeferred=el.isConnected;el.value='재고 부족으로 재주문 필요';el.dispatchEvent(new InputEvent('input',{bubbles:true,data:'요',isComposing:true,inputType:'insertCompositionText'}));el.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'요'}));el.dispatchEvent(new InputEvent('input',{bubbles:true,data:'요',isComposing:false,inputType:'insertText'}));await new Promise(r=>setTimeout(r,30));const n=document.querySelector(selector);return {same,asyncRenderDeferred,value:n?.value,focus:document.activeElement===n};}''',sel)
   assert observation=={'same':True,'asyncRenderDeferred':True,'value':'재고 부족으로 재주문 필요','focus':True},(screen,observation);assert not errors,(screen,errors);result.append(screen);await p.close()
  after=[(c['id'],c['version']) for c in json.load(urllib.request.urlopen(B+'/api/state'))['cases']];assert after==before
  print(json.dumps({'screens':result,'composing_node_preserved':True,'committed_text_and_focus':True,'case_versions_unchanged':True},ensure_ascii=False));await b.close()
asyncio.run(main())
