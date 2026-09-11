(function(){
'use strict';
const VERSION='3.5-prize-coverage-15-scalable';
const STORE='ORACLE_PLATO_V35_PRIZE_COVERAGE_V1';
const MODES={astra:'Astra baseline',experimental:'PLATO + Anti-overlap'};
const MODE_DEFAULTS={
  astra:{poolExtra:0,rankedShare:.30,layerWeight:0,possibilityWeight:0,pairNovelWeight:.26,tripleNovelWeight:.10,overlapPenaltyWeight:.12},
  experimental:{poolExtra:8,rankedShare:.24,layerWeight:1.10,possibilityWeight:.75,pairNovelWeight:.50,tripleNovelWeight:.24,overlapPenaltyWeight:.65}
};
const pairKey=(a,b)=>a<b?`${a}-${b}`:`${b}-${a}`;
const tripleKey=(a,b,c)=>[a,b,c].sort((x,y)=>x-y).join('-');
function clamp(x,a,b){return Math.max(a,Math.min(b,x))}
function coveragePoolK(game,count){
  const cfg=GAME_CFG[game];let base=15;
  try{if(window.PLATO_V35&&PLATO_V35.chooseK)base=PLATO_V35.chooseK(game)||15}catch(_){}
  const floor=count<=20?15:(count<=50?16:18);
  let required=cfg.r;while(required<cfg.n&&PLATO_V35_SPACE.choose(required,cfg.r)<count)required++;
  return clamp(Math.max(base,floor,required),cfg.r+4,cfg.n);
}
function modePool(ranked,cfg,baseK,mode,options={}){
  const d=MODE_DEFAULTS[mode],extra=Number.isFinite(options.poolExtra)?Math.max(0,Math.floor(options.poolExtra)):d.poolExtra;
  const k=clamp(baseK+extra,cfg.r+4,cfg.n);
  let ordered=ranked.out;
  if(mode==='experimental'){
    const specialists=ranked.layers.filter(layer=>layer.id!=='ensemble').map(layer=>new Map(layer.out.map(item=>[item.number,item.score])));
    ordered=ranked.out.map(item=>{const values=specialists.map(map=>map.get(item.number)||0);return {...item,specialistPoolScore:Math.max(...values)+values.reduce((a,b)=>a+b,0)/values.length};})
      .sort((a,b)=>b.specialistPoolScore-a.specialistPoolScore||b.score-a.score||a.number-b.number);
  }
  const pool=ordered.filter(item=>Number.isFinite(item.score)&&item.score>0).slice(0,k);
  if(pool.length<cfg.r)throw new Error("Not enough numbers with numeric evidence. No filler generated.");
  return {k:pool.length,pool};
}
function updateCounts(ticket,pairs,triples,usage){
  ticket.forEach(x=>usage[x]=(usage[x]||0)+1);
  for(let i=0;i<ticket.length;i++)for(let j=i+1;j<ticket.length;j++){
    const pk=pairKey(ticket[i],ticket[j]);pairs.set(pk,(pairs.get(pk)||0)+1);
    for(let k=j+1;k<ticket.length;k++){const tk=tripleKey(ticket[i],ticket[j],ticket[k]);triples.set(tk,(triples.get(tk)||0)+1)}
  }
}
// Bounded, deterministic numeric search. Equal scores use ascending numbers.
// Every candidate is scored by the same formula; no seeds, rotation or jitter.
function compareNumbers(a,b){
 for(let i=0;i<Math.min(a.length,b.length);i++)if(a[i]!==b[i])return a[i]-b[i];
 return a.length-b.length;
}
function ticketScore(cand,tickets,target,usage,pairs,triples,space,spaceState,weights,rankByNumber,layerByNumber,layer,profile,fullSize,details=false){
 // Exact identity: sum of squared overlaps equals used singles plus twice used pairs.
 // This keeps the same score without scanning every earlier ticket.
 let overlapPenalty=cand.reduce((sum,x)=>sum+(usage[x]||0),0),pairNovel=0,tripleNovel=0;
 for(let i=0;i<cand.length;i++)for(let j=i+1;j<cand.length;j++){
  overlapPenalty+=2*(pairs.get(pairKey(cand[i],cand[j]))||0);
  pairNovel+=1/(1+(pairs.get(pairKey(cand[i],cand[j]))||0));
  for(let m=j+1;m<cand.length;m++)tripleNovel+=1/(1+(triples.get(tripleKey(cand[i],cand[j],cand[m]))||0));
 }
 const deficit=cand.reduce((sum,x)=>sum+target[x]-(usage[x]||0),0);
 const ranking=cand.reduce((sum,x)=>sum+rankByNumber.get(x).score,0);
 const layerRanking=cand.reduce((sum,x)=>sum+(layerByNumber.get(x)?.score||0),0);
 const complete=cand.length===fullSize;
 const patternEvidence=complete?PLATO_V35.numericSetEvidence(cand,profile):null;
 const possibilityScore=complete&&space?PLATO_V35_SPACE.scoreTicket(cand,space,spaceState):0;
 const components={ranking:.50*ranking,proposalLayer:weights.layerWeight*layerRanking,allocation:1.1*deficit,
  pairCoverage:weights.pairNovelWeight*pairNovel,tripleCoverage:weights.tripleNovelWeight*tripleNovel,
  overlap:-weights.overlapPenaltyWeight*overlapPenalty,
  numericPatterns:patternEvidence?patternEvidence.score:0,possibility:weights.possibilityWeight*possibilityScore};
 const value=Object.values(components).reduce((sum,x)=>sum+x,0);
 return details?{score:value,components,patternEvidence,layer:{id:layer.id,label:layer.label},
  numbers:cand.map(number=>({...rankByNumber.get(number),proposal:layerByNumber.get(number),target:target[number],usedBefore:usage[number]||0}))}:value;
}
function candidateBeam(pool,size,seen,evaluate,width){
 const ordered=pool.map(item=>item.number).sort((a,b)=>a-b);
 let beam=[{numbers:[],score:0}];
 for(let depth=0;depth<size;depth++){
  const candidates=new Map();
  for(const entry of beam)for(const number of ordered){
   if(entry.numbers.includes(number))continue;
   const numbers=[...entry.numbers,number].sort((a,b)=>a-b),key=numbers.join('-');
   if(candidates.has(key)||(depth===size-1&&seen.has(key)))continue;
   const score=evaluate(numbers);
   if(!Number.isFinite(score))throw new Error('Invalid numeric selection score.');
   candidates.set(key,{numbers,score});
  }
  beam=[...candidates.values()].sort((a,b)=>b.score-a.score||compareNumbers(a.numbers,b.numbers)).slice(0,width);
  if(!beam.length)return null;
 }
 return beam[0]?.numbers||null;
}
// Large portfolios use a bounded queue of combinations ordered by each layer's
// number evidence. Every queued set receives the complete live selection score.
function combinationCursor(pool,layer,size){
 const allowed=new Set(pool.map(x=>x.number)),numbers=layer.out.filter(x=>allowed.has(x.number)).map(x=>x.number),indices=Array.from({length:size},(_,i)=>i);let done=numbers.length<size;
 return {next(){
  if(done)return null;const value=indices.map(i=>numbers[i]).sort((a,b)=>a-b);let i=size-1;
  while(i>=0&&indices[i]===numbers.length-size+i)i--;
  if(i<0)done=true;else{indices[i]++;for(let j=i+1;j<size;j++)indices[j]=indices[j-1]+1;}
  return value;
 }};
}
function refillFrontier(state,seen,amount){
 let added=0;
 while(added<amount){const candidate=state.cursor.next();if(!candidate)break;const key=candidate.join('-');if(seen.has(key)||state.pending.has(key))continue;state.pending.set(key,candidate);added++;}
 return added;
}
function frontierBest(state,seen,evaluate){
 for(const key of [...state.pending.keys()])if(seen.has(key))state.pending.delete(key);
 refillFrontier(state,seen,1);let best=null,bestScore=-Infinity;
 for(const candidate of state.pending.values()){const score=evaluate(candidate);if(score>bestScore+1e-12||(Math.abs(score-bestScore)<=1e-12&&compareNumbers(candidate,best)<0)){best=candidate;bestScore=score;}}
 return best;
}
function validatePortfolio(game,count,tickets){
  const cfg=GAME_CFG[game];if(!cfg||tickets.length!==count)return {pass:false,reason:'ticket-count'};const seen=new Set();
  for(const ticket of tickets){
    if(ticket.length!==cfg.r||new Set(ticket).size!==cfg.r)return {pass:false,reason:'ticket-shape'};
    if(ticket.some(x=>!Number.isInteger(x)||x<1||x>cfg.n))return {pass:false,reason:'number-range'};
    const key=[...ticket].sort((a,b)=>a-b).join('-');if(seen.has(key))return {pass:false,reason:'duplicate-ticket'};seen.add(key);
  }
  return {pass:true,reason:'ok'};
}
function portfolio(game,count,mode='experimental',options={}){
  if(!GAME_CFG[game]||!Number.isSafeInteger(count)||count<1)throw new Error('Choose a positive whole ticket count.');
  if(!MODES[mode])throw new Error('Choose Astra baseline or PLATO + Anti-overlap.');
  if(!window.PLATO_V35||!PLATO_V35.rank)throw new Error('v3.5 engine is not ready. Reload once.');
  const experimental=mode!=='astra',d=MODE_DEFAULTS[mode],cfg=GAME_CFG[game];
  if(count>PLATO_V35_SPACE.choose(cfg.n,cfg.r))throw new Error('Ticket count exceeds all unique number combinations.');
  const ranked=options.rankedResult||PLATO_V35.rank(game,options),baseK=coveragePoolK(game,count),picked=modePool(ranked,cfg,baseK,mode,options),k=picked.k,pool=picked.pool;
  const crossSystemReference=experimental&&options.crossSystemReference!==false?portfolio(game,count,'astra',{...options,rankedResult:ranked,crossSystemReference:false}).tickets:[];
  const scores=pool.map(x=>x.score),z=scores.reduce((a,b)=>a+b,0),totalSlots=count*cfg.r,target={},usage={};
  const rankedMix=clamp(options.rankedShare==null?d.rankedShare:Number(options.rankedShare),0,1);
  pool.forEach((item,i)=>{const uniform=1/pool.length,rankedShare=scores[i]/z;target[item.number]=totalSlots*((1-rankedMix)*uniform+rankedMix*rankedShare);usage[item.number]=0});
  const pairs=new Map(),triples=new Map(),seen=new Set(crossSystemReference.map(ticket=>ticket.join('-'))),tickets=[],selectionDetails=[],rankByNumber=new Map(pool.map(x=>[x.number,x]));
  const space=experimental&&window.PLATO_V35_SPACE?PLATO_V35_SPACE.createTargets(cfg,count):null,spaceState=space?PLATO_V35_SPACE.createState(space):null;
  const weights={
    layerWeight:experimental?(Number.isFinite(options.layerWeight)?options.layerWeight:d.layerWeight):0,
    pairNovelWeight:Number.isFinite(options.pairNovelWeight)?options.pairNovelWeight:d.pairNovelWeight,
    tripleNovelWeight:Number.isFinite(options.tripleNovelWeight)?options.tripleNovelWeight:d.tripleNovelWeight,
    overlapPenaltyWeight:Number.isFinite(options.overlapPenaltyWeight)?options.overlapPenaltyWeight:d.overlapPenaltyWeight,
    possibilityWeight:experimental?(Number.isFinite(options.possibilityWeight)?options.possibilityWeight:d.possibilityWeight):0
  };
  const profile=ranked.numericProfile||PLATO_V35.numericProfile(ranked.compatibleRows);
  const layers=(experimental?ranked.layers.filter(layer=>layer.id!=='ensemble'):ranked.layers.filter(layer=>layer.id==='ensemble'));
  const frontiers=count>200?new Map(layers.map(layer=>{const state={cursor:combinationCursor(pool,layer,cfg.r),pending:new Map()};refillFrontier(state,seen,64);return [layer.id,state];})):null;
  for(let t=0;t<count;t++){
    let best=null,bestDetail=null;
    for(const layer of layers){
      const layerByNumber=new Map(layer.out.map(item=>[item.number,item]));
      const evaluate=(numbers,details=false)=>ticketScore(numbers,tickets,target,usage,pairs,triples,space,spaceState,weights,rankByNumber,layerByNumber,layer,profile,cfg.r,details);
      let candidate=frontiers?frontierBest(frontiers.get(layer.id),seen,evaluate):candidateBeam(pool,cfg.r,seen,evaluate,24);
      if(!candidate&&!frontiers)candidate=candidateBeam(pool,cfg.r,seen,evaluate,128);
      if(!candidate&&!frontiers)candidate=candidateBeam(pool,cfg.r,seen,evaluate,Math.min(4096,Math.max(256,count)));if(!candidate)continue;
      const detail=evaluate(candidate,true);
      if(!bestDetail||detail.score>bestDetail.score+1e-12||(Math.abs(detail.score-bestDetail.score)<=1e-12&&(compareNumbers(candidate,best)<0||(compareNumbers(candidate,best)===0&&layer.id<bestDetail.layer.id)))){best=candidate;bestDetail=detail;}
    }
    if(!best)throw new Error('Numeric search found no further unique set. No filler generated.');
    selectionDetails.push(bestDetail);
    seen.add(best.join('-'));tickets.push(best);updateCounts(best,pairs,triples,usage);
    if(space)PLATO_V35_SPACE.recordTicket(best,space,spaceState);
  }
  const possibility=space?PLATO_V35_SPACE.audit(space,spaceState):null;
  const validation=validatePortfolio(game,count,tickets);
  const coverageTheorem=validation.pass&&window.PLATO_V35_SPACE?{...PLATO_V35_SPACE.coverageTheorem(cfg,tickets),uniquePairs:pairs.size,uniqueTriples:triples.size}:null;
  const layerUsage={};for(const detail of selectionDetails)layerUsage[detail.layer.label]=(layerUsage[detail.layer.label]||0)+1;
  const generationAudit={
    deterministic:true,blindRandom:false,quickPick:false,numericOnly:true,calendarScoring:false,
    tieBreak:"Ascending numeric order for exactly equal scores",search:count>200?"Evidence-ordered combination frontier, 64 fully scored candidates per layer":"Deterministic beam widths 24, 128, then ticket-count recovery up to 4096",
    policy:{rankingWeight:.50,allocationWeight:1.1,numericPatternWeight:1,numberDrootWeight:.10,...weights},
    layers:layers.map(layer=>({id:layer.id,label:layer.label})),selectedLayerCounts:layerUsage,crossSystemExactDuplicatesAllowed:false,crossSystemReferenceTickets:crossSystemReference.length,
    basis:['era-aware numeric ranking','individual and set DRoot','TSUM and Q','DRoot transitions','candidate-pool allocation','pair/triple coverage','overlap control',...(experimental?['count-based population proportions','possibility-space coverage']:[])],
    historyDraws:ranked.history.total,currentEraDraws:ranked.history.raw,candidatePool:k
  };
  return {mode,modeLabel:MODES[mode],cfg,ranked,k,baseK,pool:pool.map(x=>x.number),tickets,usage,pairs,triples,possibility,
    quantumAudit:null,randomnessAudit:null,validation,generationAudit,coverageTheorem,selectionDetails,layerUsage,
    options:{poolExtra:k-baseK,rankedShare:rankedMix,...weights}};
}
function proportionFit(actual,size,members,total){const expected=size*members/total;return 1-Math.abs(actual-expected)/Math.max(1,expected,size-expected);}
function systemSetScore(numbers,rankByNumber,layerByNumber,layer,cfg,details=false){
  const ensemble=numbers.reduce((sum,x)=>sum+rankByNumber.get(x).score,0)/numbers.length;
  const proposal=numbers.reduce((sum,x)=>sum+(layerByNumber.get(x)?.score||0),0)/numbers.length;
  const roots=new Set(numbers.map(PLATO_V35.digitalRoot)).size/Math.min(9,numbers.length);
  const oddFit=proportionFit(numbers.filter(x=>x%2).length,numbers.length,Math.ceil(cfg.n/2),cfg.n);
  const lowerFit=proportionFit(numbers.filter(x=>x<=Math.floor(cfg.n/2)).length,numbers.length,Math.floor(cfg.n/2),cfg.n);
  const components={combinedRanking:.50*ensemble,proposalLayer:.35*proposal,drootCoverage:.05*roots,oddProportion:.05*oddFit,rangeProportion:.05*lowerFit};
  const score=Object.values(components).reduce((sum,x)=>sum+x,0);
  return details?{score,components,layer:{id:layer.id,label:layer.label},numbers:numbers.map(number=>({...rankByNumber.get(number),proposal:layerByNumber.get(number)}))}:score;
}
function systemEntry(game,size,mode='experimental',options={}){
  if(!GAME_CFG[game]||!MODES[mode])throw new Error('Choose a supported game and method.');
  const cfg=GAME_CFG[game];if(!Number.isSafeInteger(size)||size<cfg.r||size>cfg.n)throw new Error(`Choose ${cfg.r}–${cfg.n} system numbers.`);
  const ranked=options.rankedResult||PLATO_V35.rank(game,options),experimental=mode==='experimental',pool=ranked.out.filter(item=>Number.isFinite(item.score)&&item.score>0);
  if(pool.length<size)throw new Error('Not enough numbers with numeric evidence. No filler generated.');
  const layers=experimental?ranked.layers.filter(layer=>layer.id!=='ensemble'):ranked.layers.filter(layer=>layer.id==='ensemble'),rankByNumber=new Map(ranked.out.map(item=>[item.number,item]));
  const reference=experimental&&options.crossSystemReference!==false?systemEntry(game,size,'astra',{...options,rankedResult:ranked,crossSystemReference:false}).numbers:null,blocked=new Set(reference?[reference.join('-')]:[]);let best=null,bestDetail=null;
  for(const layer of layers){
    const layerByNumber=new Map(layer.out.map(item=>[item.number,item])),evaluate=(numbers,details=false)=>systemSetScore(numbers,rankByNumber,layerByNumber,layer,cfg,details);
    const candidate=candidateBeam(pool,size,blocked,evaluate,32);if(!candidate)continue;const detail=evaluate(candidate,true);
    if(!bestDetail||detail.score>bestDetail.score+1e-12||(Math.abs(detail.score-bestDetail.score)<=1e-12&&(compareNumbers(candidate,best)<0||(compareNumbers(candidate,best)===0&&layer.id<bestDetail.layer.id)))){best=candidate;bestDetail=detail;}
  }
  if(!best)throw new Error('Numeric system search produced no supported entry.');
  const summary=PLATO_V35_SPACE.systemSummary(cfg,best,ranked.numericProfile.previous?.tsum),powerball=game==='pb'?powerballChoice(0,ranked):null;
  return {entryType:'system',game,mode,modeLabel:MODES[mode],cfg,ranked,numbers:best,size,summary,powerball,selectionDetail:bestDetail,
    generationAudit:{deterministic:true,blindRandom:false,quickPick:false,numericOnly:true,calendarScoring:false,layers:layers.map(x=>({id:x.id,label:x.label})),selectedLayer:bestDetail.layer,crossSystemExactDuplicatesAllowed:false,tieBreak:'Ascending numeric order for exactly equal scores'}};
}
function compare(game,count){
  const astra=portfolio(game,count,'astra'),experimental=portfolio(game,count,'experimental');
  return {game,count,astra,experimental,pass:astra.validation.pass&&experimental.validation.pass};
}
function powerballChoice(i,ranked){
 if(!Number.isInteger(i)||i<0)throw new Error('Invalid Powerball ticket index.');
 return powerballChoices(i+1,ranked).at(-1);
}
function powerballChoices(count,ranked){
 if(!Number.isSafeInteger(count)||count<1)throw new Error('Invalid Powerball ticket count.');
 const candidates=ranked.bonusRanking||PLATO_V35.bonusRanking(ranked.compatibleRows||[],GAME_CFG.pb.bonusN);
 if(!candidates.length)throw new Error('No compatible Powerball evidence. No bonus filler generated.');
 const usage={},out=[];
 for(let ticket=0;ticket<count;ticket++){
  let selected=null;
  for(const item of candidates){
   const usedBefore=usage[item.number]||0,allocationScore=item.score/(1+usedBefore);
   if(!selected||allocationScore>selected.allocationScore||(allocationScore===selected.allocationScore&&item.number<selected.number))
    selected={...item,usedBefore,allocationScore};
  }
  usage[selected.number]=(usage[selected.number]||0)+1;out.push(selected);
 }
 return out;
}
function powerballFor(i,ranked){return powerballChoice(i,ranked).number;}
function formatTicket(game,ticket,i,ranked,powerballNumber){
  const main=ticket.map(x=>String(x).padStart(2,'0')).join(' ');
  return game==='pb'?`${main}   PB ${String(powerballNumber??powerballFor(i,ranked)).padStart(2,'0')}`:main;
}
function selectionEvidence(decision){
  const evidence=document.createElement('details'),heading=document.createElement('summary'),body=document.createElement('span');
  heading.textContent='Number selection scores';body.style.display='block';body.style.fontSize='12px';
  body.textContent=`Selected layer: ${decision.layer.label}\n`+decision.numbers.map(x=>{
    const source=x.proposal||x,strongest=[...source.contributions].sort((a,b)=>b.contribution-a.contribution).slice(0,3);
    return x.number+' → combined '+x.score.toFixed(4)+' · layer '+source.score.toFixed(4)+' | '+strongest.map(term=>term.method.replace(/^m[12]_\d+_/,'').replaceAll('_',' ')+': '+term.contribution.toFixed(4)).join(', ');
  }).join('\n');
  if(decision.patternEvidence)body.textContent+='\nSet pattern support: '+decision.patternEvidence.terms.map(term=>term.pattern+' '+term.value+' → '+term.count+'/'+term.maximum).join(' · ');
  body.textContent+='\nSelection score: '+decision.score.toFixed(4)+' | '+Object.entries(decision.components).map(([key,value])=>key+': '+value.toFixed(4)).join(', ');
  evidence.appendChild(heading);evidence.appendChild(body);return evidence;
}
function renderPatterns(analysis,theorem,possibility){
  let panel=document.getElementById('v35Patterns');
  if(!panel){panel=document.createElement('details');panel.id='v35Patterns';document.getElementById('v35CopyTools').after(panel)}
  panel.replaceChildren();panel.hidden=false;
  const toggle=document.createElement('summary');toggle.textContent='Show pattern descriptions';panel.appendChild(toggle);
  const title=document.createElement('h2');title.textContent='Common and uncommon patterns';panel.appendChild(title);
  const note=document.createElement('p');note.className='note';
  note.textContent=`${analysis.totalDraws} stored draws analysed. Counts use the ${analysis.current.drawCount} draws under current rules. These are descriptive historical patterns only; they do not claim predictive power.`;panel.appendChild(note);
  if(theorem){
    const info=document.createElement('p');info.className='note';
    info.textContent=`Coverage theorem: ${theorem.uniqueTickets} unique sets; exact ${theorem.r}/${theorem.r} main-number match chance ${(theorem.exactMainMatchProbability*100).toPrecision(3)}% under a uniform draw. ${theorem.uniquePairs} unique pairs and ${theorem.uniqueTriples} unique triples covered. Main numbers only; this is a chance baseline, not a predictive edge.`;panel.appendChild(info);
  }
  if(possibility){
    const core=possibility.families.filter(x=>x.id==='odd'||x.id==='lowerHalf'),info=document.createElement('p');info.className='note';
    info.textContent='Count proportions used by PLATO: '+core.map(x=>`${x.label} ${x.members}/${x.singleDraw.total} = ${x.singleDraw.percent.toFixed(2)}%`).join(' · ')+'.';panel.appendChild(info);
  }
  for(const group of Object.values(analysis.current.groups)){
    const row=document.createElement('p'),label=document.createElement('strong');label.textContent=group.label;row.appendChild(label);
    const text=group.tied?'All observed patterns have equal counts.':!group.common.length?'Not enough observations.':`Common: ${group.common.map(x=>`${x.pattern} (${x.count})`).join(', ')}\nUncommon: ${group.uncommon.map(x=>`${x.pattern} (${x.count})`).join(', ')}`;
    const body=document.createElement('span');body.style.display='block';body.style.whiteSpace='pre-line';body.textContent=text;row.appendChild(body);panel.appendChild(row);
  }
}
async function run(event){
  if(event)event.preventDefault();const form=document.getElementById('v35Form');if(!form.reportValidity())return;
  const game=document.getElementById('v35Game').value,mode=document.getElementById('v35Method').value,entryType=document.getElementById('v35EntryType').value,count=Number(document.getElementById('v35Count').value),btn=document.getElementById('v35Generate'),summary=document.getElementById('v35Summary'),output=document.getElementById('v35Tickets');
  if(btn.disabled)return;btn.disabled=true;btn.textContent='Generating…';summary.textContent='';output.replaceChildren();document.getElementById('v35CopyTools').hidden=true;document.getElementById('v35CopyText').value='';
  const oldPatterns=document.getElementById('v35Patterns');if(oldPatterns)oldPatterns.hidden=true;
  await new Promise(resolve=>setTimeout(resolve,0));
  try{
    if(entryType==='system'){
      const res=systemEntry(game,Number(document.getElementById('v35SystemSize').value),mode),item=document.createElement('li'),numbers=res.numbers.map(x=>String(x).padStart(2,'0')).join(' ');
      item.className='ticket';item.textContent=`SYSTEM ${res.size}: ${numbers}${res.powerball?`   PB ${String(res.powerball.number).padStart(2,'0')}`:''}`;
      const stats=document.createElement('span');stats.style.display='block';stats.style.fontSize='12px';stats.style.color='#b9c2ce';
      stats.textContent=`${res.summary.lineCount.toLocaleString()} exact ${res.cfg.r}-number standard combinations\nMean line TSUM: ${res.summary.meanLineTSUM.toFixed(2)} · Range: ${res.summary.minLineTSUM}–${res.summary.maxLineTSUM}\nExact main-set coverage: ${(100*res.summary.exactMainMatchProbability).toPrecision(4)}% · Layer: ${res.selectionDetail.layer.label}`;
      if(res.powerball)stats.textContent+=`\nPB numeric score: ${res.powerball.score.toFixed(4)} · DRoot ${res.powerball.droot}`;
      const description=document.createElement('details'),descriptionTitle=document.createElement('summary');descriptionTitle.textContent='Show details';description.appendChild(descriptionTitle);description.appendChild(stats);description.appendChild(selectionEvidence(res.selectionDetail));item.appendChild(description);output.appendChild(item);
      showCopyText(numbers+(res.powerball?`   PB ${String(res.powerball.number).padStart(2,'0')}`:''));
      summary.textContent=`${res.cfg.name} · ${res.modeLabel} · System ${res.size} · ${res.summary.lineCount.toLocaleString()} covered lines · deterministic numeric selection`;
      const payload={version:VERSION,createdAt:new Date().toISOString(),entryType:'system',game,mode,numbers:res.numbers,systemSummary:res.summary,powerball:res.powerball,selectionDetail:res.selectionDetail,generationAudit:res.generationAudit};
      try{localStorage.setItem(STORE,JSON.stringify(payload))}catch(_){}window.PLATO_LAST_GENERATION=payload;return;
    }
    const res=portfolio(game,count,mode);if(!res.validation.pass)throw new Error(`Portfolio validation failed: ${res.validation.reason}`);
    const bonusChoices=game==='pb'?powerballChoices(res.tickets.length,res.ranked):[];
    summary.textContent=`${GAME_CFG[game].name} · ${res.modeLabel} · ${res.tickets.length} tickets · ${res.pool.length} candidate numbers · layers: ${Object.entries(res.layerUsage).map(([name,value])=>`${name} ${value}`).join(', ')} · deterministic · PASS`;
    const patterns=PLATO_V35.analysePatterns(game,{rows:res.ranked.rows}),setDetails=res.tickets.map(ticket=>PLATO_V35.classifySet(ticket,patterns));
    const fragment=document.createDocumentFragment();
    res.tickets.forEach((ticket,i)=>{
      const item=document.createElement('li'),details=setDetails[i];item.className='ticket';item.textContent=formatTicket(game,ticket,i,res.ranked,bonusChoices[i]?.number);
      const stats=document.createElement('span');stats.style.display='block';stats.style.fontSize='12px';stats.style.color='#b9c2ce';
      stats.textContent=`Main TSUM: ${details.tsum} · Set DRoot: ${details.setDigitalRoot}\nNumber DRoots: ${details.individualDigitalRoots.map(x=>`${x.number}→${x.droot}`).join(' ')}`;
      if(details.comparison)stats.textContent+=`\nQ: ${details.comparison.q_t} vs draw ${details.comparison.referenceDraw} · Q DRoot: ${details.comparison.qDigitalRoot}`;
      for(const status of ['common','uncommon','not observed']){
        const labels=Object.entries(details.behaviour).filter(([,value])=>value.status===status).map(([key])=>patterns.current.groups[key].label);
        if(labels.length)stats.textContent+=`\n${status[0].toUpperCase()+status.slice(1)}: ${labels.join(', ')}`;
      }
      if(game==='pb'){const pb=bonusChoices[i];stats.textContent+=`\nPB numeric score: ${pb.score.toFixed(4)} · Allocation: ${pb.allocationScore.toFixed(4)} · DRoot ${pb.droot}`;}
      const description=document.createElement('details'),descriptionTitle=document.createElement('summary');descriptionTitle.textContent='Show details';description.appendChild(descriptionTitle);description.appendChild(stats);
      const decision=res.selectionDetails[i];
      description.appendChild(selectionEvidence(decision));item.appendChild(description);fragment.appendChild(item);
    });
    output.appendChild(fragment);showCopyText(res.tickets.map((ticket,i)=>formatTicket(game,ticket,i,res.ranked,bonusChoices[i]?.number)).join('\n'));renderPatterns(patterns,res.coverageTheorem,res.possibility);
    output.dataset.historyTotal=String(res.ranked.history.total);output.dataset.rawDraws=String(res.ranked.history.raw);output.dataset.structuralDraws=String(res.ranked.history.structural);
    output.dataset.eras=JSON.stringify(res.ranked.history.eras);output.dataset.mode=res.mode;output.dataset.validation='PASS';output.dataset.pool=res.pool.join(',');output.dataset.deterministic='true';
    const payload={version:VERSION,createdAt:new Date().toISOString(),game,mode,count,pool:res.pool,tickets:res.tickets,setDetails,
      selectionDetails:res.selectionDetails,numberEvidence:res.ranked.out,numberWeights:res.ranked.weights,
      bonusEvidence:bonusChoices,powerballs:bonusChoices.map(x=>x.number),history:res.ranked.history,possibility:res.possibility,generationAudit:res.generationAudit,coverageTheorem:res.coverageTheorem,validation:res.validation};
    try{localStorage.setItem(STORE,JSON.stringify(payload))}catch(_){}
    window.PLATO_LAST_GENERATION={...payload,patterns};
  }catch(error){summary.textContent=String(error.message||error)}finally{btn.disabled=false;btn.textContent='Generate v3.5'}
}
function showCopyText(value){const box=document.getElementById('v35CopyText'),tools=document.getElementById('v35CopyTools');box.value=value;tools.hidden=false;}
function selectAllNumbers(){const box=document.getElementById('v35CopyText');box.focus();box.select();box.setSelectionRange(0,box.value.length);document.getElementById('v35CopyStatus').textContent='All numbers selected.';}
async function copyAllNumbers(){
  const box=document.getElementById('v35CopyText'),status=document.getElementById('v35CopyStatus');selectAllNumbers();
  try{if(navigator.clipboard&&window.isSecureContext)await navigator.clipboard.writeText(box.value);else if(!document.execCommand('copy'))throw new Error('copy unavailable');status.textContent='All numbers copied.';}catch(_){status.textContent='Numbers selected. Choose Copy from the phone menu.';}
}
function install(){
  const select=document.getElementById('v35Game');for(const [key,cfg] of Object.entries(GAME_CFG)){const option=document.createElement('option');option.value=key;option.textContent=cfg.name;select.appendChild(option)}
  const entry=document.getElementById('v35EntryType'),ticketField=document.getElementById('v35TicketField'),systemField=document.getElementById('v35SystemField'),systemSize=document.getElementById('v35SystemSize');
  function controls(){const cfg=GAME_CFG[select.value],isSystem=entry.value==='system';ticketField.hidden=isSystem;systemField.hidden=!isSystem;systemSize.min=cfg.r;systemSize.max=cfg.n;if(Number(systemSize.value)<cfg.r||Number(systemSize.value)>cfg.n)systemSize.value=Math.min(cfg.n,cfg.r+2);}
  select.value='sat';const method=document.getElementById('v35Method');if(method)method.value='astra';entry.addEventListener('change',controls);select.addEventListener('change',controls);document.getElementById('v35SelectAll').addEventListener('click',selectAllNumbers);document.getElementById('v35CopyAll').addEventListener('click',copyAllNumbers);controls();document.getElementById('v35Form').addEventListener('submit',run);document.getElementById('v35Generate').disabled=false;
}
window.PLATO_V35_COVERAGE={VERSION,MODES,MODE_DEFAULTS,portfolio,systemEntry,compare,coveragePoolK,modePool,validatePortfolio,powerballChoice,powerballChoices,powerballFor,formatTicket,selectAllNumbers,copyAllNumbers,run};install();
})();
