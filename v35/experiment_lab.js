(function(){
'use strict';
const VERSION='3.5-experiment-lab-4-layered-systems';
const DEFAULT_FOLDS=10;
const VARIANTS=[
  {id:'astra',label:'Astra baseline',kind:'portfolio',mode:'astra',options:{}},
  {id:'experimental',label:'PLATO + Anti-overlap',kind:'portfolio',mode:'experimental',options:{}}
];
function hitCount(ticket,target){const set=new Set(target);let c=0;for(const x of ticket)if(set.has(x))c++;return c}
function bestHit(tickets,target){let best=0;for(const ticket of tickets)best=Math.max(best,hitCount(ticket,target));return best}
function targetRows(game,folds=DEFAULT_FOLDS){
  const latest=PLATO_HISTORY.ERAS[game].at(-1),rows=[...PLATO_DATA.SEED_DATA[game]].sort((a,b)=>a[0]-b[0]);
  const current=rows.filter(row=>{const era=PLATO_HISTORY.eraFor(game,row[0]);return era&&era.start===latest.start&&row[2].length===latest.r});
  const eligible=current.filter((row,i)=>i>=60);
  return eligible.slice(-Math.max(1,Math.min(folds,eligible.length)));
}
function buildTickets(game,count,targetId,variant,ranked,cache={}){
  const shared={beforeDraw:targetId,rankedResult:ranked,skipDiagnostics:true};
  const get=(key,mode,opts={})=>cache[key]||(cache[key]=PLATO_V35_COVERAGE.portfolio(game,count,mode,{...shared,...opts}).tickets);
  if(variant.kind==='portfolio')return get(variant.id,variant.mode,variant.options);
  throw new Error('Unknown lab variant.');
}
function emptyMetric(r){return {folds:0,exact:0,atLeast6:0,atLeast5:0,atLeast4:0,bestHitSum:0,bestHitCounts:Array(r+1).fill(0),valid:true}}
function finalizeMetric(m,r){return {...m,meanBest:m.folds?m.bestHitSum/m.folds:0,exactRate:m.folds?m.exact/m.folds:0,fivePlusRate:m.folds?m.atLeast5/m.folds:0,fourPlusRate:m.folds?m.atLeast4/m.folds:0,target:`${r}/${r}`}}
function compareMetric(a,b){return b.exact-a.exact||b.atLeast5-a.atLeast5||b.atLeast4-a.atLeast4||b.atLeast6-a.atLeast6||b.meanBest-a.meanBest||a.label.localeCompare(b.label)}
function benchmark(game,count,options={}){
  const cfg=GAME_CFG[game];if(!cfg)throw new Error('Unsupported game.');if(!Number.isSafeInteger(count)||count<1)throw new Error('Choose a positive whole ticket count.');if(count>PLATO_V35_SPACE.choose(cfg.n,cfg.r))throw new Error('Ticket count exceeds all unique number combinations.');
  const folds=Number.isInteger(options.folds)?options.folds:DEFAULT_FOLDS,targets=targetRows(game,folds);if(!targets.length)throw new Error('Not enough current-era draws for lab.');
  const variants=options.variants||VARIANTS,metrics=Object.fromEntries(variants.map(v=>[v.id,emptyMetric(cfg.r)]));
  for(const target of targets){
    const ranked=PLATO_V35.rank(game,{beforeDraw:target[0]}),cache={};
    if(ranked.rows.length&&ranked.rows.at(-1)[0]>=target[0])throw new Error(`Leakage detected at draw ${target[0]}.`);
    for(const variant of variants){
      const tickets=buildTickets(game,count,target[0],variant,ranked,cache),valid=PLATO_V35_COVERAGE.validatePortfolio(game,count,tickets);
      const m=metrics[variant.id];m.folds++;if(!valid.pass){m.valid=false;continue}
      const best=bestHit(tickets,target[2]);m.bestHitSum+=best;m.bestHitCounts[best]++;
      if(best===cfg.r)m.exact++;if(best>=6)m.atLeast6++;if(best>=5)m.atLeast5++;if(best>=4)m.atLeast4++;
    }
  }
  const results=variants.map(v=>({id:v.id,label:v.label,...finalizeMetric(metrics[v.id],cfg.r)})).sort(compareMetric);
  const exactSpace=PLATO_V35_SPACE?PLATO_V35_SPACE.choose(cfg.n,cfg.r):null;
  return {version:VERSION,game,count,folds:targets.length,targetRange:[targets[0][0],targets.at(-1)[0]],
    scoreOrder:cfg.r===7?['7/7','5+/7','4+/7','6+/7 diagnostic','mean best-hit']:[`${cfg.r}/${cfg.r}`,`5+/${cfg.r}`,`4+/${cfg.r}`],
    uniformChanceExactExpectation:exactSpace?targets.length*count/exactSpace:null,results,pass:results.every(x=>x.valid)};
}
function rowHtml(r,cfg){return `<tr><td>${r.label}</td><td>${r.valid?'PASS':'FAIL'}</td><td>${r.exact}/${r.folds}</td><td>${r.atLeast5}/${r.folds}</td><td>${r.atLeast4}/${r.folds}</td><td>${r.meanBest.toFixed(2)}</td></tr>`}
async function run(){
  const game=document.getElementById('v35Game').value,count=Number(document.getElementById('v35Count').value),btn=document.getElementById('v35RunLab'),summary=document.getElementById('v35LabSummary'),out=document.getElementById('v35LabResults');
  if(!btn||!summary||!out)return;btn.disabled=true;btn.textContent='Running lab…';summary.textContent='Chronological deterministic walk-forward test.';out.innerHTML='';
  await new Promise(r=>setTimeout(r,0));
  try{
    const res=benchmark(game,count,{folds:DEFAULT_FOLDS}),cfg=GAME_CFG[game],winner=res.results[0];
    summary.textContent=`${cfg.name} · ${res.folds} unseen historical targets · ${count} tickets/variant · ${res.pass?'PASS':'FAIL'} · top: ${winner.label}`;
    out.innerHTML=`<div class="labscroll"><table><thead><tr><th>Variant</th><th>Validity</th><th>${cfg.r}/${cfg.r}</th><th>5+</th><th>4+</th><th>Mean best</th></tr></thead><tbody>${res.results.map(r=>rowHtml(r,cfg)).join('')}</tbody></table></div><p class="labnote">Ranking priority: exact ${cfg.r}/${cfg.r}, then 5+, then 4+. Both variants use the same number-only selection code used for live entries. PASS is a leakage/validity software check, not evidence of predictive edge. Uniform-chance exact expectation: ${res.uniformChanceExactExpectation==null?'n/a':res.uniformChanceExactExpectation.toExponential(2)}.</p>`;
    window.PLATO_LAST_LAB=res;
  }catch(e){summary.textContent=String(e.message||e)}finally{btn.disabled=false;btn.textContent='Run Experiment Lab'}
}
function install(){const b=document.getElementById('v35RunLab');if(b)b.addEventListener('click',run)}
window.PLATO_V35_LAB={VERSION,DEFAULT_FOLDS,VARIANTS,hitCount,bestHit,targetRows,benchmark,run};install();
})();
