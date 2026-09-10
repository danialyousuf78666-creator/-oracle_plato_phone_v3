const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),plain=x=>JSON.parse(JSON.stringify(x));
const element=()=>({value:'sat',disabled:false,textContent:'',dataset:{},appendChild(){},addEventListener(){},reportValidity:()=>true});
const context=vm.createContext({console,Date,localStorage:{getItem:()=>null,setItem(){}},document:{getElementById:()=>element(),createElement:()=>element(),createDocumentFragment:()=>({appendChild(){}})}});
context.window=context;
for(const name of ['history.js','era_history.js','randomness_diagnostics.js','plato_v35_phone.js','possibility_space.js','prize_coverage.js'])vm.runInContext(fs.readFileSync(path.join(root,'v35',name),'utf8'),context,{filename:name});
const H=context.PLATO_HISTORY,E=context.PLATO_V35,C=context.PLATO_V35_COVERAGE,S=context.PLATO_V35_SPACE,D=context.PLATO_DATA;
test('all 9,771 valid supplied draws enter structural inference; identities stay in correct eras',()=>{
 const expected={pb:[1581,438],sat:[2079,2079],oz:[1699,226],sfl:[4051,2361],ww:[361,361]};
 let total=0;for(const [key,[all,raw]] of Object.entries(expected)){
  const rank=E.rank(key);assert.equal(rank.rows.length,all);assert.equal(rank.compatibleRows.length,raw);assert.equal(rank.history.structural,all);
  assert.ok(rank.out.every(x=>Number.isFinite(x.score)&&x.score>=0&&x.score<=1.000001));total+=all;
 }
 assert.equal(total,9771);
 assert.deepEqual(plain(H.eraFor('oz',609)),{start:609,n:45,r:7});assert.equal(H.eraFor('oz',1474).n,47);
 assert.deepEqual(plain(H.eraFor('sfl',1690)),{start:1,n:37,r:8});
});
test('existing distilled methods and checkpoint weights are unchanged',()=>{
 const checkpoint=JSON.parse(fs.readFileSync(path.join(root,'audit/v35_distilled_weights.json')));
 for(const [game,payload] of Object.entries(checkpoint.games)){assert.deepEqual(plain(E.weights[game]),payload.selected_methods);assert.equal(Object.keys(E.weights[game]).length,8);}
});
test('old incompatible eras affect normalized structure but cannot contaminate raw signals',()=>{
 const rows=plain(D.SEED_DATA.pb),changed=plain(rows);
 changed.forEach(row=>{if(row[0]<877)row[2]=row[2].map(x=>x%45+1);});
 const a=H.historyFor('pb',{rows}),b=H.historyFor('pb',{rows:changed});
 assert.deepEqual(plain(a.compatible),plain(b.compatible));
 assert.deepEqual(plain(E.featureSet(a.compatible,35)),plain(E.featureSet(b.compatible,35)));
 assert.notDeepEqual(plain(H.structuralFeatures(a.annotated,35,7)),plain(H.structuralFeatures(b.annotated,35,7)));
});
test('normalized structural transfer respects source n and r',()=>{
 const row=(id,nums,n,r)=>({row:[id,'2026-01-01',nums],era:{start:1,n,r}});
 const a=H.structuralFeatures([row(1,[2,6,10],10,3)],40,6);
 const b=H.structuralFeatures([row(1,[4,12,20],20,3)],40,6);
 for(const name of ['density','sum','range','pos','sig'])assert.deepEqual(plain(a[name]),plain(b[name]));
});
test('target and future rows cannot affect historical pre-target inference',()=>{
 const rows=plain(D.SEED_DATA.pb),changed=plain(rows);
 changed.forEach(row=>{if(row[0]>=1500)row[2]=row[2].map(x=>x%35+1);});
 assert.deepEqual(plain(E.rank('pb',{rows,beforeDraw:1500})),plain(E.rank('pb',{rows:changed,beforeDraw:1500})));
});
test('structural features use records before the former 180-draw truncation',()=>{
 const rows=plain(D.SEED_DATA.sat),a=H.historyFor('sat',{rows});
 const changed=plain(rows);changed.at(-1)[2]=[1,2,3,4,5,6];
 const b=H.historyFor('sat',{rows:changed});
 assert.notDeepEqual(plain(H.structuralFeatures(a.annotated,45,6).density),plain(H.structuralFeatures(b.annotated,45,6).density));
});
test('Astra baseline and PLATO experimental both generate valid unique portfolios',()=>{
 for(const mode of ['astra','experimental'])for(const game of Object.keys(D.GAME_CFG))for(const count of [1,20,50]){
  const result=C.portfolio(game,count,mode),cfg=D.GAME_CFG[game];assert.equal(result.mode,mode);assert.equal(result.validation.pass,true);assert.equal(result.tickets.length,count);
  assert.equal(new Set(result.tickets.map(x=>x.join('-'))).size,count);
  for(const ticket of result.tickets){assert.equal(ticket.length,cfg.r);assert.equal(new Set(ticket).size,cfg.r);assert.ok(ticket.every(x=>Number.isInteger(x)&&x>=1&&x<=cfg.n));}
 }
 assert.equal(C.portfolio('pb',100,'astra').tickets.length,100);assert.equal(C.portfolio('pb',100,'experimental').tickets.length,100);
 assert.throws(()=>C.portfolio('sat',2.5,'astra'),/whole tickets/);assert.throws(()=>C.portfolio('sat',0,'experimental'),/whole tickets/);assert.throws(()=>C.portfolio('sat',20,'bad'),/Astra baseline/);
});
test('Astra is isolated while experimental activates possibility and randomness audits',()=>{
 const a=C.portfolio('sat',20,'astra'),e=C.portfolio('sat',20,'experimental'),cmp=C.compare('sat',20);
 assert.equal(a.possibility,null);assert.equal(a.quantumAudit,null);assert.equal(a.randomnessAudit,null);
 assert.ok(e.possibility);assert.ok(e.quantumAudit);assert.ok(e.randomnessAudit);assert.equal(e.randomnessAudit.enabledWeight,0);
 assert.equal(cmp.pass,true);assert.equal(cmp.astra.validation.pass,true);assert.equal(cmp.experimental.validation.pass,true);
});
test('Possibility Space uses exact combination counts without banning any legal number',()=>{
 assert.equal(S.choose(14,6),3003);assert.equal(S.choose(45,6),8145060);assert.equal(S.choose(35,7),6724520);
 const cfg=D.GAME_CFG.sat,t=S.createTargets(cfg,20),m6=t.families.find(x=>x.id==='multiple6'),m7=t.families.find(x=>x.id==='multiple7');
 assert.equal(m6.members,7);assert.equal(m7.members,6);
 assert.equal(m6.distribution.counts.reduce((a,b)=>a+b,0),S.choose(cfg.n,cfg.r));
 assert.equal(m7.distribution.counts.reduce((a,b)=>a+b,0),S.choose(cfg.n,cfg.r));
 const result=C.portfolio('sat',20,'experimental');assert.ok(result.possibility);assert.equal(result.possibility.tickets,20);
 assert.ok(result.tickets.flat().some(x=>x%6!==0&&x%7!==0),'non-family numbers remain fully legal');
 assert.equal(result.quantumAudit.enabledWeight,0);
});
test('Powerball coverage includes all 20 bonus values across 20 tickets',()=>{
 const values=Array.from({length:20},(_,i)=>C.formatTicket('pb',[1,2,3,4,5,6,7],i,51).split('PB ')[1]);assert.equal(new Set(values).size,20);
});
test('root exposes two methods without iframe or legacy controls',()=>{
 const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
 assert.equal((html.match(/<(?:select|input|button)\b/g)||[]).length,5);
 assert.doesNotMatch(html,/<iframe|v3\.1|v3\.2|v3\.4|shortlist|backtest|folds|windowSelect/i);
 assert.doesNotMatch(fs.readFileSync(path.join(root,'v35/index.html'),'utf8'),/<iframe/i);
 assert.match(html,/Experiment Lab/);assert.match(html,/Run Experiment Lab/);assert.match(html,/Game<\/label>/);assert.match(html,/Method<\/label>/);assert.match(html,/Astra baseline/);assert.match(html,/PLATO experimental/);assert.match(html,/Ticket count<\/label>/);assert.match(html,/Generate v3\.5/);assert.match(html,/PASS means/);
 assert.doesNotMatch(fs.readFileSync(path.join(root,'v35/plato_v35_phone.js'),'utf8'),/compatibleRows\(game\)|PLATO_V34|install\(\)/);
});
test('legacy control remains byte-frozen and is not loaded by live scripts',()=>{
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'audit/frozen.json')));
 assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'audit/legacy-v3-controls.js'))).digest('hex'),manifest.legacy_control_sha256);
 assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'v35/history.js'))).digest('hex'),manifest.history_sha256);
 assert.doesNotMatch(fs.readFileSync(path.join(root,'index.html'),'utf8'),/audit\//);
});