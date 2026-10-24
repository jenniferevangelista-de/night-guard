const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '..', 'web', 'index.html'), 'utf8');
function ui(lang = 'en') {
  const result = {innerHTML:'', querySelector:()=>({}), querySelectorAll:()=>[]};
  const ctx = {progress:{practiced:{},seen:{}}, lang, DEMO:false, VOICE:false,
    esc:s=>String(s), $:()=>result, store:{set(){}}, renderLazy(){},
    chatHTML:()=>'', linksHTML:()=>'', unknownCard:()=>'', renderQuotes(){}, show(){}};
  vm.createContext(ctx);
  vm.runInContext(source.match(/const T = \{[\s\S]*?\n\};/)[0] + '; this.T=T;', ctx);
  ctx.t = key=>ctx.T[lang][key];
  vm.runInContext(source.match(/function known\(sig\)\{[^\n]+/)[0], ctx);
  vm.runInContext(source.slice(source.indexOf('function familyNotice('), source.indexOf('/* ---------- 2. Practice')), ctx);
  return {ctx,result};
}
test('seeing warnings repeatedly does not certify learning or hide explanations', () => {
  const {ctx,result} = ui();
  ctx.progress.seen.secrecy=100;
  assert.equal(ctx.known('secrecy'),false);
  ctx.progress.practiced.secrecy=1;
  assert.equal(ctx.known('secrecy'),true);
  ctx.renderResult({answered:'yes',severity:'medium',messages:[],signals:[{id:'secrecy',label:'Secret',kid:'Notice',quote:'words',lesson:'Read me again'}]});
  assert.match(result.innerHTML,/<details/);
  assert.match(result.innerHTML,/Read me again/);
  assert.doesNotMatch(result.innerHTML,/already know/);
});
test('every notification state distinguishes a record from a read receipt in both languages', () => {
  for(const lang of ['en','pt']) {
    const {ctx} = ui(lang);
    for(const [state,key] of Object.entries({accepted:'notifyAccepted',failed:'notifyFailed',disabled:'notifyDisabled',demo_only:'notifyDemo'})) {
      const html=ctx.familyNotice({family_alert:{shared:true},notification_status:state});
      assert.ok(html.includes(ctx.T[lang][key]));
    }
    assert.equal(ctx.familyNotice({family_alert:null}), '');
  }
});
test('all available exercises reach the final rank without counting mere exposure', () => {
  const {ctx} = ui();
  vm.runInContext(source.match(/const RANKS = [^\n]+/)[0], ctx);
  vm.runInContext(source.match(/function heroRank\(n,total\)\{[^\n]+/)[0], ctx);
  const scenarios = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'guard', 'scenarios.json'), 'utf8'));
  const count = new Set(scenarios.map(s=>s.skill)).size;
  assert.equal(ctx.heroRank(0,count),0);
  assert.equal(ctx.heroRank(count,count),4);
  assert.equal(ctx.heroRank(0,0),0);
});
