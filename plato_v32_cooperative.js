(function(){
'use strict';

const CFG = {
  windows: [100,150,200,250,0],
  coopMin: 0.20,
  coopMax: 0.80,
  coopStep: 0.05,
  headMin: 0.30,
  headMax: 0.70,
  headStep: 0.05,
  lambdaWeight: 0.18,
  lambdaBlend: 0.12,
  stabilityPenalty: 0.35,
  rollingRate: 0.05,
  rollingKey: 'ORACLE_PLATO_V32_RELIABILITY'
};

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const variance=a=>{if(!a.length)return 0;const m=avg(a);return avg(a.map(x=>(x-m)*(x-m)))};
const sd=a=>Math.sqrt(variance(a));
const median=a=>{if(!a.length)return 0;const b=a.slice().sort((x,y)=>x-y),m=Math.floor(b.length/2);return b.length%2?b[m]:(b[m-1]+b[m])/2};
const normalize=w=>{const s=w.reduce((a,b)=>a+b,0)||1;return w.map(x=>x/s)};
const sqDist=(a,b)=>a.reduce((s,x,i)=>s+(x-b[i])**2,0);

function rollingState(){
  try{return JSON.parse(localStorage.getItem(CFG.rollingKey)||'{}')}catch(_){return {}}
}
function saveRollingState(s){localStorage.setItem(CFG.rollingKey,JSON.stringify(s))}
function gameRolling(key){
  const s=rollingState(),g=s[key]||{};
  return {classic:Number.isFinite(g.classic)?g.classic:1,adaptive:Number.isFinite(g.adaptive)?g.adaptive:1,combined:Number.isFinite(g.combined)?g.combined:1,lastDraw:g.lastDraw??null};
}
function rollingPriorShare(key){
  const g=gameRolling(key),den=g.classic+g.adaptive;
  return clamp(den>0?g.classic/den:.5,CFG.coopMin,CFG.coopMax);
}

function frameRanks(frame,w,k){
  return frame.features.map(x=>({...x,score:x.features.reduce((q,v,i)=>q+v*w[i],0)}))
    .sort((a,b)=>b.score-a.score).slice(0,k);
}
function avgFor(frames,w,k){return avg(frames.map(fr=>hitCount(frameRanks(fr,w,k).map(x=>x.number),fr.draw)))}
function horizonFrames(key,rows,folds){
  const out=[];
  for(const h of CFG.windows){
    const f=buildValidationFrames(key,rows,folds,h);
    if(f.length>=10)out.push({window:h,frames:f});
  }
  return out;
}
function horizonScore(groups,w,k,prior,lambda){
  const avgs=groups.map(g=>avgFor(g.frames,w,k));
  if(!avgs.length)return {score:-Infinity,mean:0,sd:0,avgs:[]};
  const m=avg(avgs),s=sd(avgs);
  return {score:m-CFG.stabilityPenalty*s-lambda*sqDist(w,prior),mean:m,sd:s,avgs};
}

function tuneHeadStable(groups,k,kind){
  const classic=V3_WEIGHTS.slice();
  const rawPrior=kind===1?[classic[0],classic[1]]:[classic[2],classic[3]];
  const p2=normalize(rawPrior),prior=kind===1?[p2[0],p2[1],0,0]:[0,0,p2[0],p2[1]];
  let best=null;
  for(let a=CFG.headMin;a<=CFG.headMax+1e-9;a+=CFG.headStep){
    const aa=+a.toFixed(8),w=kind===1?[aa,1-aa,0,0]:[0,0,aa,1-aa];
    const stat=horizonScore(groups,w,k,prior,CFG.lambdaWeight);
    if(!best||stat.score>best.stat.score+1e-12||(Math.abs(stat.score-best.stat.score)<1e-12&&sqDist(w,prior)<sqDist(best.w,prior)))best={w,stat};
  }
  return best;
}

function learnDualStable(key,rows,k,trainWindow=0){
  const c=GAME_CFG[key],folds=Math.min(80,Math.max(20,Math.floor(rows.length*.28)));
  const groups=horizonFrames(key,rows,folds);
  if(!groups.length){
    return {weights:V3_WEIGHTS.slice(),m1:[.60,.40,0,0],m2:[0,0,.57,.43],alpha:.5,frames:0,m1Avg:0,m2Avg:0,fusionAvg:0,expected:c.r*k/c.n,stability:0};
  }
  const m1=tuneHeadStable(groups,k,1),m2=tuneHeadStable(groups,k,2);
  const priorAlpha=.5; let best=null;
  for(let a=CFG.coopMin;a<=CFG.coopMax+1e-9;a+=CFG.coopStep){
    const aa=+a.toFixed(8),w=m1.w.map((v,j)=>aa*v+(1-aa)*m2.w[j]);
    const stat=horizonScore(groups,w,k,V3_WEIGHTS,CFG.lambdaWeight*.5) ;
    const score=stat.score-CFG.lambdaBlend*(aa-priorAlpha)**2;
    if(!best||score>best.score+1e-12||(Math.abs(score-best.score)<1e-12&&Math.abs(aa-.5)<Math.abs(best.a-.5)))best={a:aa,w,stat,score};
  }
  return {weights:best.w,m1:m1.w,m2:m2.w,alpha:best.a,frames:groups.reduce((s,g)=>s+g.frames.length,0),m1Avg:m1.stat.mean,m2Avg:m2.stat.mean,fusionAvg:best.stat.mean,expected:c.r*k/c.n,stability:best.stat.sd,horizonAvgs:best.stat.avgs};
}

function featureStability(key,rows,k,expected){
  const folds=Math.min(80,Math.max(20,Math.floor(rows.length*.28))),groups=horizonFrames(key,rows,folds);
  const names=['Frequency','Recency','Gaps','Pairs'];
  return names.map((name,i)=>{
    const w=[0,0,0,0];w[i]=1;
    const vals=groups.map(g=>avgFor(g.frames,w,k)-expected);
    const positives=vals.filter(x=>x>0).length;
    const persistence=vals.length?positives/vals.length:0;
    const rel=persistence>=.8&&sd(vals)<=.10?'High':persistence>=.5?'Medium':'Low';
    const marks=vals.map(v=>v>=.10?'++':v>0?'+':Math.abs(v)<1e-12?'0':'−');
    return {name,vals,marks,reliability:rel,persistence,stability:sd(vals)};
  });
}

function learnCooperativeStable(key,rows,k,trainWindow=0){
  const c=GAME_CFG[key];
  if(rows.length<80){
    const dual=learnDualStable(key,rows,k,trainWindow),a=.5,w=V3_WEIGHTS.map((v,j)=>a*v+(1-a)*dual.weights[j]);
    return {...dual,coopWeights:w,classicShare:a,classicAvg:0,coopAvg:0,featureStability:[]};
  }
  const split=Math.max(60,Math.floor(rows.length*.70));
  const baseRows=rows.slice(0,split),dual=learnDualStable(key,baseRows,k,trainWindow);
  const metaFolds=Math.min(80,Math.max(20,rows.length-split)),groups=horizonFrames(key,rows,metaFolds);
  const expected=c.r*k/c.n,priorShare=rollingPriorShare(key),classicStat=horizonScore(groups,V3_WEIGHTS,k,V3_WEIGHTS,0);
  let best=null;
  for(let a=CFG.coopMin;a<=CFG.coopMax+1e-9;a+=CFG.coopStep){
    const aa=+a.toFixed(8),w=V3_WEIGHTS.map((v,j)=>aa*v+(1-aa)*dual.weights[j]);
    const stat=horizonScore(groups,w,k,V3_WEIGHTS,0),score=stat.mean-CFG.stabilityPenalty*stat.sd-CFG.lambdaBlend*(aa-priorShare)**2;
    if(!best||score>best.score+1e-12||(Math.abs(score-best.score)<1e-12&&Math.abs(aa-priorShare)<Math.abs(best.a-priorShare)))best={a:aa,w,stat,score};
  }
  return {...dual,coopWeights:best.w,classicShare:best.a,classicAvg:classicStat.mean,coopAvg:best.stat.mean,coopStability:best.stat.sd,metaFrames:groups.reduce((s,g)=>s+g.frames.length,0),rollingPrior:priorShare,featureStability:featureStability(key,rows,k,expected)};
}

function engineMetrics(hits,rc,r){
  const n=hits.length,m=avg(hits),v=variance(hits),s=Math.sqrt(v),se=n?s/Math.sqrt(n):0;
  const rate=t=>n?hits.filter(x=>x>=t).length/n:0;
  return {mean:m,median:median(hits),variance:v,ci:[Math.max(0,m-1.96*se),Math.min(r,m+1.96*se)],p:rc.p(m),cap3:rate(3),cap4:rate(4),cap5:rate(5),cap6:rate(6),best:n?Math.max(...hits):0};
}
function fmtMetric(name,m,expected){
  const pct=x=>(100*x).toFixed(2)+'%';
  return `${name}: ${m.mean.toFixed(4)}  Δ ${(m.mean-expected).toFixed(4)}  p=${m.p.toFixed(4)}\n`+
    `  median ${m.median.toFixed(2)} | variance ${m.variance.toFixed(4)} | 95% CI ${m.ci[0].toFixed(4)}–${m.ci[1].toFixed(4)}\n`+
    `  3+ ${pct(m.cap3)} | 4+ ${pct(m.cap4)} | 5+ ${pct(m.cap5)} | 6/6 ${pct(m.cap6)}`;
}

function zoneBlend(classicRank,adaptiveRank,k,classicShare=.5){
  const C=classicRank.slice(0,k).map(x=>x.number),A=adaptiveRank.slice(0,k).map(x=>x.number),cs=new Set(C),as=new Set(A);
  const consensus=C.filter(x=>as.has(x));
  const cSpec=C.filter(x=>!as.has(x)),aSpec=A.filter(x=>!cs.has(x));
  const consensusSlots=Math.min(consensus.length,Math.round(k*.47));
  let rem=k-consensusSlots,cSlots=Math.round(rem*classicShare),aSlots=rem-cSlots;
  const picked=[...consensus.slice(0,consensusSlots),...cSpec.slice(0,cSlots),...aSpec.slice(0,aSlots)];
  for(const n of [...consensus,...cSpec,...aSpec])if(picked.length<k&&!picked.includes(n))picked.push(n);
  return {numbers:picked.slice(0,k),consensus,cSpec,aSpec,allocation:{consensus:Math.min(consensusSlots,picked.length),classic:Math.min(cSlots,cSpec.length),adaptive:Math.min(aSlots,aSpec.length)}};
}

function updateRollingFromLatest(key,k){
  const rows=currentRows(key).slice().sort((a,b)=>a[0]-b[0]); if(rows.length<81)return;
  const latest=rows[rows.length-1],drawId=latest[0],state=rollingState(),old=gameRolling(key); if(old.lastDraw===drawId)return;
  const hist=rows.slice(0,-1),c=GAME_CFG[key],expected=c.r*k/c.n,model=learnCooperativeStable(key,hist,k,0);
  const classic=rankNumbers(key,hist,V3_WEIGHTS).slice(0,k).map(x=>x.number),adaptive=rankNumbers(key,hist,model.weights).slice(0,k).map(x=>x.number),combined=rankNumbers(key,hist,model.coopWeights).slice(0,k).map(x=>x.number);
  const perf={classic:hitCount(classic,latest[2])/expected,adaptive:hitCount(adaptive,latest[2])/expected,combined:hitCount(combined,latest[2])/expected};
  const g={classic:(1-CFG.rollingRate)*old.classic+CFG.rollingRate*perf.classic,adaptive:(1-CFG.rollingRate)*old.adaptive+CFG.rollingRate*perf.adaptive,combined:(1-CFG.rollingRate)*old.combined+CFG.rollingRate*perf.combined,lastDraw:drawId};
  state[key]=g;saveRollingState(state);
}

window.PLATO_V32={CFG,learnDualStable,learnCooperativeStable,engineMetrics,featureStability,zoneBlend,updateRollingFromLatest,gameRolling};
window.learnDualHead=learnDualStable;
window.learnCooperativeModel=learnCooperativeStable;

const originalAdd=window.addDrawLocal;
if(typeof originalAdd==='function')window.addDrawLocal=function(){
  const key=document.getElementById('addGame')?.value;
  const out=originalAdd.apply(this,arguments);
  try{const k=Math.max(GAME_CFG[key].r,Math.min(15,GAME_CFG[key].n));updateRollingFromLatest(key,k)}catch(_){ }
  return out;
};

window.runBacktest=function(){
 const out=document.getElementById('btOut');
 try{
  const key=document.getElementById('btGame').value,c=GAME_CFG[key],requested=Math.max(20,+document.getElementById('btFolds').value||100),k=Math.min(Math.max(c.r,+document.getElementById('btK').value||15),c.n),tw=Math.max(0,+document.getElementById('btWindow').value||0);
  const rows=currentRows(key).slice().sort((a,b)=>a[0]-b[0]),minTrain=80,maxFolds=Math.max(0,rows.length-minTrain);if(maxFolds<20)throw new Error(`Only ${rows.length} current-format draws; need at least ${minTrain+20}.`);
  const folds=Math.min(requested,maxFolds),start=rows.length-folds,prefix=rows.slice(0,start),model=learnCooperativeStable(key,prefix,k,tw);
  const classic=methodBacktest(key,rows,start,k,tw,V3_WEIGHTS),m1=methodBacktest(key,rows,start,k,tw,model.m1),m2=methodBacktest(key,rows,start,k,tw,model.m2),adaptive=methodBacktest(key,rows,start,k,tw,model.weights),combined=methodBacktest(key,rows,start,k,tw,model.coopWeights),expected=c.r*k/c.n,rc=randomControl(c.n,c.r,k,folds,10000);
  const metrics={classic:engineMetrics(classic.hits,rc,c.r),m1:engineMetrics(m1.hits,rc,c.r),m2:engineMetrics(m2.hits,rc,c.r),adaptive:engineMetrics(adaptive.hits,rc,c.r),combined:engineMetrics(combined.hits,rc,c.r)};
  const delta=metrics.combined.mean-expected,status=delta>0&&metrics.combined.p<.05?'EVIDENCE ABOVE RANDOM IN THIS WINDOW — REPLICATE':'NO VERIFIED EDGE';
  const stab=model.featureStability.map(x=>`${x.name.padEnd(9)} ${x.marks.map((m,i)=>`${CFG.windows[i]===0?'all':CFG.windows[i]}:${m}`).join('  ')}  ${x.reliability}`).join('\n');
  out.textContent=`${c.name} — PLATO v3.2 stability-constrained cooperative backtest\nRequested folds: ${requested}\nUsed folds: ${folds}${folds<requested?` (auto-limited; ${rows.length} current-format draws)`:''}\nShortlist: ${k}\n\nTRAINING — prefix only (${prefix.length} draws)\nClassic v3 F/R/G/P: ${weightLabel(V3_WEIGHTS)}\nMachine 1 regularized: ${weightLabel(model.m1)}\nMachine 2 regularized: ${weightLabel(model.m2)}\nv3.1 stable dual: ${weightLabel(model.weights)}\nCooperative: ${(100*model.classicShare).toFixed(0)}% v3 / ${(100*(1-model.classicShare)).toFixed(0)}% v3.1 (bounds 20–80%)\nCombined: ${weightLabel(model.coopWeights)}\nRolling prior: ${(100*(model.rollingPrior??.5)).toFixed(1)}% v3\n\nMULTI-WINDOW FEATURE STABILITY\n${stab||'Insufficient history'}\n\nOUTER TEST — untouched later draws\nRandom exact expectation: ${expected.toFixed(4)} hits/draw\nRandom simulation 95% range: ${rc.lo.toFixed(4)}–${rc.hi.toFixed(4)} (10,000 controls)\n\n${fmtMetric('PLATO v3',metrics.classic,expected)}\n${fmtMetric('Machine 1',metrics.m1,expected)}\n${fmtMetric('Machine 2',metrics.m2,expected)}\n${fmtMetric('v3.1 Dual',metrics.adaptive,expected)}\n${fmtMetric('v3.2 Combined',metrics.combined,expected)}\n\nSTATUS: ${status}`;
 }catch(e){out.textContent='ERROR: '+e.message}
};

window.makeTickets=function(){
 const list=document.getElementById('ticketList'),sum=document.getElementById('ticketSummary');list.innerHTML='';
 try{
  const key=document.getElementById('ticketGame').value,c=GAME_CFG[key],w=+document.getElementById('ticketWindow').value,k=Math.max(c.r,Math.min(+document.getElementById('ticketK').value,c.n)),tc=Math.min(100,+document.getElementById('ticketCount').value);
  let rows=currentRows(key).slice().sort((a,b)=>a[0]-b[0]);if(w>0&&rows.length>w)rows=rows.slice(-w);
  const model=learnCooperativeStable(key,rows,k,0),classic=rankNumbers(key,rows,V3_WEIGHTS),adaptive=rankNumbers(key,rows,model.weights),z=zoneBlend(classic,adaptive,k,model.classicShare),pool=z.numbers;
  const combined=rankNumbers(key,rows,model.coopWeights),combinedMap=Object.fromEntries(combined.map(x=>[x.number,x.score])),weights=pool.map(x=>Math.max(.02,combinedMap[x]??.02)),scoreMap=Object.fromEntries(pool.map((x,i)=>[x,weights[i]])),dist=oddEvenDist(c.n,c.r),cand=[],seen=new Set();let guard=0,target=Math.min(1200,Math.max(tc*25,150));
  while(cand.length<target&&guard<target*80){guard++;const p=choosePattern(dist),odds=pool.filter(x=>x%2),evens=pool.filter(x=>x%2===0);if(odds.length<p.o||evens.length<p.e)continue;const a=weightedSample(odds,odds.map(x=>weights[pool.indexOf(x)]),p.o).concat(weightedSample(evens,evens.map(x=>weights[pool.indexOf(x)]),p.e)).sort((a,b)=>a-b),ss=a.join('-');if(!seen.has(ss)){seen.add(ss);cand.push(a)}}
  const tickets=diversifyTickets(cand,tc,scoreMap),bonusRank=c.bonusN?rankBonus(key,rows):null,comp=nCr(c.n,c.r)/nCr(k,c.r);let ovs=[];for(let i=0;i<tickets.length;i++)for(let j=i+1;j<tickets.length;j++)ovs.push(tickets[i].filter(x=>tickets[j].includes(x)).length/c.r);
  sum.innerHTML=`v3.2 shortlist <b>${pool.join(', ')}</b><br>${nCr(c.n,c.r).toLocaleString()} → ${nCr(k,c.r).toLocaleString()} combinations (${fmt(comp,1)}× compression).<br><span class="tiny">Diversity zones: ${z.allocation.consensus} consensus + ${z.allocation.classic} v3 specialists + ${z.allocation.adaptive} v3.1 specialists · cooperative ${(100*model.classicShare).toFixed(0)}% v3 / ${(100*(1-model.classicShare)).toFixed(0)}% v3.1 · ${tickets.length} unique tickets · mean overlap ${fmt(100*mean(ovs),1)}%.</span>`;
  list.innerHTML=tickets.map((t,i)=>{let b='';if(c.bonusN){const pb=weightedSample(bonusRank.map(x=>x.n),bonusRank.map(x=>x.w),1)[0];b=` + PB ${pb}`};return `<div class="ticket">${String(i+1).padStart(2,'0')}. ${t.map(x=>String(x).padStart(2,'0')).join('  ')}${b}</div>`}).join('');
 }catch(e){list.innerHTML='<pre>ERROR: '+e.message+'</pre>'}
};

try{
  document.title='ORACLE / PLATO Phone v3.2 Cooperative';
  const h=document.querySelector('header h1');if(h)h.textContent='ORACLE / PLATO — v3 + v3.2 Cooperative';
  const sub=document.querySelector('header .sub');if(sub)sub.textContent='classic v3 frozen • regularized adaptive v3.1 • stability-constrained v3.2 cooperative head';
}catch(_){ }
})();
