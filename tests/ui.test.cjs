const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const script = readFileSync('app/web/index.html', 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
function page(fetch) {
  const nodes = new Map();
  function node() { return { value:'', textContent:'', innerHTML:'', hidden:false, disabled:false, style:{}, children:[], listeners:{}, appendChild(x){this.children.push(x)}, append(x){this.children.push(x)}, focus(){}, setAttribute(){}, removeAttribute(){}, addEventListener(k, fn){this.listeners[k]=fn} }; }
  const document = { getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id)}, createElement:node, querySelectorAll(){return document.getElementById('chips').children} };
  const context=vm.createContext({document,fetch,AbortSignal,TypeError,SyntaxError,setTimeout,clearTimeout,console});
  vm.runInContext(script,context);
  document.getElementById('q').value='Subject: A message';
  return {context, $:document.getElementById.bind(document), run:()=>vm.runInContext('go()',context)};
}
const verdict={label:'phishing',confidence:.95,reason:'Asks for a password',indicators:['password'],guardrails:[],usage:{},model:'test',latency_ms:100};
test('HTTP errors are errors, not verdicts',async()=>{
 const p=page(async()=>({ok:false,status:502,json:async()=>({detail:'upstream model error'})}));await p.run();
 assert.match(p.$('status').textContent,/unavailable|try again/i);assert.equal(p.$('result').hidden,true);
});
test('keyboard submissions cannot duplicate a pending request',async()=>{
 let calls=0, resolve;const p=page(()=>{calls++;return new Promise(r=>resolve=r)});
 const first=p.run();const second=p.run();assert.equal(calls,1);resolve({ok:true,json:async()=>verdict});await Promise.all([first,second]);
});
test('editing input invalidates a previous result',async()=>{
 const p=page(async()=>({ok:true,json:async()=>verdict}));await p.run();assert.equal(p.$('result').hidden,false);
 p.$('q').value='Different email';p.$('q').listeners.input();assert.equal(p.$('result').hidden,true);
});
test('malformed successful response does not become a verdict',async()=>{
 const p=page(async()=>({ok:true,json:async()=>({})}));await p.run();assert.match(p.$('status').textContent,/valid result|try again/i);assert.equal(p.$('result').hidden,true);
});
test('blank and oversized input never reach the API',async()=>{
 let calls=0;const p=page(async()=>{calls++});
 for(const value of ['   ','a'.repeat(40001)]){p.$('q').value=value;await p.run();assert.notEqual(p.$('status').textContent,'');}
 assert.equal(calls,0);
});
test('422 rejection is not presented as a suspicious verdict',async()=>{
 const p=page(async()=>({ok:false,status:422}));await p.run();assert.equal(p.$('result').hidden,true);assert.match(p.$('status').textContent,/accepted/);
});
test('network failure releases controls for retry',async()=>{
 const p=page(async()=>{throw new TypeError('Failed to fetch')});await p.run();assert.equal(p.$('go').disabled,false);assert.equal(p.$('q').disabled,false);assert.match(p.$('status').textContent,/connection/);
});
test('all verdicts render evidence as text',async()=>{
 for(const label of ['phishing','legit','suspicious']){
  const evidence='<img src=x onerror=alert(1)>';
  const p=page(async()=>({ok:true,json:async()=>({...verdict,label,indicators:[evidence]})}));await p.run();
  assert.equal(p.$('result').hidden,false);assert.equal(p.$('ind').children[0].textContent,'“'+evidence+'”');assert.equal(p.$('go').disabled,false);
 }
});
