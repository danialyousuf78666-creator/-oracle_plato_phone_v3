(function(){
'use strict';
const VERSION='3.5-prize-coverage-12-numeric-only';
const STORE='ORACLE_PLATO_V35_PRIZE_COVERAGE_V1';
const MODES={astra:'Astra baseline',experimental:'PLATO + Anti-overlap'};
const MODE_DEFAULTS={
  astra:{poolExtra:0,rankedShare:.30,possibilityWeight:0,pairNovelWeight:.26,tripleNovelWeight:.10,overlapPenaltyWeight:.12},
  experimental:{poolExtra:8,rankedShare:.24,possibilityWeight:.65,pairNovelWeight:.46,tripleNovelWeight:.22,overlapPenaltyWeight:.42}
};
const pairKey=(a,b)=>a<b?`${a}-${b}`:`${b}-${a}`;
const tripleKey=(a,b,c)=>[a,b,c].sort((x,y)=>x-y).join('-');
function clamp(x,a,b){return Math.max(a,Math.min(b,x))}
function coveragePoolK(game,count){
  const cfg=GAME_CFG[game];let base=15;
  try{if(window.PLATO_V35&&PLATO_V35.chooseK)base=PLATO_V35.chooseK(game)||15}catch(_){}
  const floor=count<=20?15:(count<=50?16:18);
  return clamp(Math.max(base,floor),cfg.r+4,Math.min(cfg.n,20));
}
function modePool(ranked,cfg,baseK,mode,options={}){
  const d=MODE_DEFAULTS[mode],extra=Number.isFinite(options.poolExtra)?Math.max(0,Math.floor(options.poolExtra)):d.poolExtra;
  const k=clamp(baseK+extra,cfg.r+4,Math.min(cfg.n,28));
  const pool=ranked.out.filter(item=>Number.isFinite(item.score)&&item.score>0).slice(0,k);
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
function ticketScore(cand,tickets,target,usage,pairs,triples,space,spaceState,weights,rankByNumber,profile,fullSize,details=false){
 let overlapPenalty=0,pairNovel=0,tripleNovel=0;
 for(const old of tickets){let overlap=0;for(const x of cand)if(old.includes(x))overlap++;overlapPenalty+=overlap*overlap;}
 for(let i=0;i<cand.length;i++)for(let j=i+1;j<cand.length;j++){
  pairNovel+=1/(1+(pairs.get(pairKey(cand[i],cand[j]))||0));
  for(let m=j+1;m<cand.length;m++)tripleNovel+=1/(1+(triples.get(tripleKey(cand[i],cand[j],cand[m]))||0));
 }
 const deficit=cand.reduce((sum,x)=>sum+target[x]-(usage[x]||0),0);
 const ranking=cand.reduce((sum,x)=>sum+rankByNumber.get(x).score,0);
 const complete=cand.length===fullSize;
 const patternEvidence=complete?PLATO_V35.numericSetEvidence(cand,profile):null;
 const possibilityScore=complete&&space?PLATO_V35_SPACE.scoreTicket(cand,space,spaceState):0;
 const components={ranking:.50*ranking,allocation:1.1*deficit,
  pairCoverage:weights.pairNovelWeight*pairNovel,tripleCoverage:weights.tripleNovelWeight*tripleNovel,
  overlap:-weights.overlapPenaltyWeight*overlapPenalty,
  numericPatterns:patternEvidence?patternEvidence.score:0,possibility:weights.possibilityWeight*possibilityScore};
 const value=Object.values(components).reduce((sum,x)=>sum+x,0);
 return details?{score:value,components,patternEvidence,
  numbers:cand.map(number=>({...rankByNumber.get(number),target:target[number],usedBefore:usage[number]||0}))}:value;
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
  if(!GAME_CFG[game]||!Number.isInteger(count)||count<1||count>100)throw new Error('Choose 1–100 whole tickets.');
  if(!MODES[mode])throw new Error('Choose Astra baseline or PLATO + Anti-overlap.');
  if(!window.PLATO_V35||!PLATO_V35.rank)throw new Error('v3.5 engine is not ready. Reload once.');
  const experimental=mode!=='astra',d=MODE_DEFAULTS[mode],cfg=GAME_CFG[game];
  const ranked=options.rankedResult||PLATO_V35.rank(game,options),baseK=coveragePoolK(game,count),picked=modePool(ranked,cfg,baseK,mode,options),k=picked.k,pool=picked.pool;
  const scores=pool.map(x=>x.score),z=scores.reduce((a,b)=>a+b,0),totalSlots=count*cfg.r,target={},usage={};
  const rankedMix=clamp(options.rankedShare==null?d.rankedShare:Number(options.rankedShare),0,1);
  pool.forEach((item,i)=>{const uniform=1/pool.length,rankedShare=scores[i]/z;target[item.number]=totalSlots*((1-rankedMix)*uniform+rankedMix*rankedShare);usage[item.number]=0});
  const pairs=new Map(),triples=new Map(),seen=new Set(),tickets=[],selectionDetails=[],rankByNumber=new Map(pool.map(x=>[x.number,x]));
  const space=experimental&&window.PLATO_V35_SPACE?PLATO_V35_SPACE.createTargets(cfg,count):null,spaceState=space?PLATO_V35_SPACE.createState(space):null;
  const weights={
    pairNovelWeight:Number.isFinite(options.pairNovelWeight)?options.pairNovelWeight:d.pairNovelWeight,
    tripleNovelWeight:Number.isFinite(options.tripleNovelWeight)?options.tripleNovelWeight:d.tripleNovelWeight,
    overlapPenaltyWeight:Number.isFinite(options.overlapPenaltyWeight)?options.overlapPenaltyWeight:d.overlapPenaltyWeight,
    possibilityWeight:experimental?(Number.isFinite(options.possibilityWeight)?options.possibilityWeight:d.possibilityWeight):0
  };
  const profile=ranked.numericProfile||PLATO_V35.numericProfile(ranked.compatibleRows);
  for(let t=0;t<count;t++){
    const evaluate=(numbers,details=false)=>ticketScore(numbers,tickets,target,usage,pairs,triples,space,spaceState,weights,rankByNumber,profile,cfg.r,details);
    let best=candidateBeam(pool,cfg.r,seen,evaluate,24);
    if(!best)best=candidateBeam(pool,cfg.r,seen,evaluate,128);
    if(!best)throw new Error('Numeric search found no further unique set. No filler generated.');
    selectionDetails.push(evaluate(best,true));
    seen.add(best.join('-'));tickets.push(best);updateCounts(best,pairs,triples,usage);
    if(space)PLATO_V35_SPACE.recordTicket(best,space,spaceState);
  }
  const possibility=space?PLATO_V35_SPACE.audit(space,spaceState):null;
  const validation=validatePortfolio(game,count,tickets);
  const coverageTheorem=validation.pass&&window.PLATO_V35_SPACE?{...PLATO_V35_SPACE.coverageTheorem(cfg,tickets),uniquePairs:pairs.size,uniqueTriples:triples.size}:null;
  const generationAudit={
    deterministic:true,blindRandom:false,numericOnly:true,calendarScoring:false,
    tieBreak:"Ascending numeric order for exactly equal scores",search:"Deterministic beam, width 24; width 128 only if exhausted",
    policy:{rankingWeight:.50,allocationWeight:1.1,numericPatternWeight:1,numberDrootWeight:.10,...weights},
    basis:['era-aware numeric ranking','individual and set DRoot','TSUM and Q','DRoot transitions','candidate-pool allocation','pair/triple coverage','overlap control',...(experimental?['possibility-space coverage']:[])],
    historyDraws:ranked.history.total,currentEraDraws:ranked.history.raw,candidatePool:k
  };
  return {mode,modeLabel:MODES[mode],cfg,ranked,k,baseK,pool:pool.map(x=>x.number),tickets,usage,pairs,triples,possibility,
    quantumAudit:null,randomnessAudit:null,validation,generationAudit,coverageTheorem,selectionDetails,
    options:{poolExtra:k-baseK,rankedShare:rankedMix,...weights}};
}
function compare(game,count){
  const astra=portfolio(game,count,'astra'),experimental=portfolio(game,count,'experimental');
  return {game,count,astra,experimental,pass:astra.validation.pass&&experimental.validation.pass};
}
function powerballChoice(i,ranked){
 if(!Number.isInteger(i)||i<0)throw new Error('Invalid Powerball ticket index.');
 const candidates=ranked.bonusRanking||PLATO_V35.bonusRanking(ranked.compatibleRows||[],GAME_CFG.pb.bonusN);
 if(!candidates.length)throw new Error('No compatible Powerball evidence. No bonus filler generated.');
 const usage={};let selected;
 for(let ticket=0;ticket<=i;ticket++){
  selected=null;
  for(const item of candidates){
   const usedBefore=usage[item.number]||0,allocationScore=item.score/(1+usedBefore);
   if(!selected||allocationScore>selected.allocationScore||(allocationScore===selected.allocationScore&&item.number<selected.number))
    selected={...item,usedBefore,allocationScore};
  }
  usage[selected.number]=(usage[selected.number]||0)+1;
 }
 return selected;
}
function powerballFor(i,ranked){return powerballChoice(i,ranked).number;}
function formatTicket(game,ticket,i,ranked){
  const main=ticket.map(x=>String(x).padStart(2,'0')).join(' ');
  return game==='pb'?`${main}   PB ${String(powerballFor(i,ranked)).padStart(2,'0')}`:main;
}
function renderPatterns(analysis,theorem){
  let panel=document.getElementById('v35Patterns');
  if(!panel){panel=document.createElement('section');panel.id='v35Patterns';document.getElementById('v35Tickets').after(panel)}
  panel.replaceChildren();panel.hidden=false;
  const title=document.createElement('h2');title.textContent='Common and uncommon patterns';panel.appendChild(title);
  const note=document.createElement('p');note.className='note';
  note.textContent=`${analysis.totalDraws} stored draws analysed. Counts use the ${analysis.current.drawCount} draws under current rules. These are descriptive historical patterns only; they do not claim predictive power.`;panel.appendChild(note);
  if(theorem){
    const info=document.createElement('p');info.className='note';
    info.textContent=`Coverage theorem: ${theorem.uniqueTickets} unique sets; exact ${theorem.r}/${theorem.r} main-number match chance ${(theorem.exactMainMatchProbability*100).toPrecision(3)}% under a uniform draw. ${theorem.uniquePairs} unique pairs and ${theorem.uniqueTriples} unique triples covered. Main numbers only; this is a chance baseline, not a predictive edge.`;panel.appendChild(info);
  }
  for(const group of Object.values(analysis.current.groups)){
    const row=document.createElement('p'),label=document.createElement('strong');label.textContent=group.label;row.appendChild(label);
    const text=group.tied?'All observed patterns have equal counts.':!group.common.length?'Not enough observations.':`Common: ${group.common.map(x=>`${x.pattern} (${x.count})`).join(', ')}\nUncommon: ${group.uncommon.map(x=>`${x.pattern} (${x.count})`).join(', ')}`;
    const body=document.createElement('span');body.style.display='block';body.style.whiteSpace='pre-line';body.textContent=text;row.appendChild(body);panel.appendChild(row);
  }
}
async function run(event){
  if(event)event.preventDefault();const form=document.getElementById('v35Form');if(!form.reportValidity())return;
  const game=document.getElementById('v35Game').value,mode=document.getElementById('v35Method').value,count=Number(document.getElementById('v35Count').value),btn=document.getElementById('v35Generate'),summary=document.getElementById('v35Summary'),output=document.getElementById('v35Tickets');
  if(btn.disabled)return;btn.disabled=true;btn.textContent='Generating…';summary.textContent='';output.replaceChildren();
  const oldPatterns=document.getElementById('v35Patterns');if(oldPatterns)oldPatterns.hidden=true;
  await new Promise(resolve=>setTimeout(resolve,0));
  try{
    const res=portfolio(game,count,mode);if(!res.validation.pass)throw new Error(`Portfolio validation failed: ${res.validation.reason}`);
    summary.textContent=`${GAME_CFG[game].name} · ${res.modeLabel} · ${res.tickets.length} tickets · ${res.pool.length} candidate numbers · deterministic · PASS`;
    const patterns=PLATO_V35.analysePatterns(game,{rows:res.ranked.rows}),setDetails=res.tickets.map(ticket=>PLATO_V35.classifySet(ticket,patterns));
    const fragment=document.createDocumentFragment();
    res.tickets.forEach((ticket,i)=>{
      const item=document.createElement('li'),details=setDetails[i];item.className='ticket';item.textContent=formatTicket(game,ticket,i,res.ranked);
      const stats=document.createElement('span');stats.style.display='block';stats.style.fontSize='12px';stats.style.color='#b9c2ce';
      stats.textContent=`Main TSUM: ${details.tsum} · Set DRoot: ${details.setDigitalRoot}\nNumber DRoots: ${details.individualDigitalRoots.map(x=>`${x.number}→${x.droot}`).join(' ')}`;
      if(details.comparison)stats.textContent+=`\nQ: ${details.comparison.q_t} vs draw ${details.comparison.referenceDraw} · Q DRoot: ${details.comparison.qDigitalRoot}`;
      for(const status of ['common','uncommon','not observed']){
        const labels=Object.entries(details.behaviour).filter(([,value])=>value.status===status).map(([key])=>patterns.current.groups[key].label);
        if(labels.length)stats.textContent+=`\n${status[0].toUpperCase()+status.slice(1)}: ${labels.join(', ')}`;
      }
      if(game==='pb'){const pb=powerballChoice(i,res.ranked);stats.textContent+=`\nPB numeric score: ${pb.score.toFixed(4)} · Allocation: ${pb.allocationScore.toFixed(4)} · DRoot ${pb.droot}`;}
      item.appendChild(stats);
      const evidence=document.createElement('details'),heading=document.createElement('summary'),body=document.createElement('span');
      heading.textContent='Number selection scores';body.style.display='block';body.style.fontSize='12px';
      const decision=res.selectionDetails[i];
      body.textContent=decision.numbers.map(x=>{
        const strongest=[...x.contributions].sort((a,b)=>b.contribution-a.contribution).slice(0,3);
        return x.number+' → '+x.score.toFixed(4)+' | '+strongest.map(term=>term.method.replace(/^m[12]_\d+_/,'').replaceAll('_',' ')+': '+term.contribution.toFixed(4)).join(', ');
      }).join('\n');
      body.textContent+='\nSet pattern support: '+decision.patternEvidence.terms.map(term=>term.pattern+' '+term.value+' → '+term.count+'/'+term.maximum).join(' · ');
      body.textContent+='\nSelection score: '+decision.score.toFixed(4)+' | '+Object.entries(decision.components).map(([key,value])=>key+': '+value.toFixed(4)).join(', ');
      evidence.appendChild(heading);evidence.appendChild(body);item.appendChild(evidence);fragment.appendChild(item);
    });
    output.appendChild(fragment);renderPatterns(patterns,res.coverageTheorem);
    output.dataset.historyTotal=String(res.ranked.history.total);output.dataset.rawDraws=String(res.ranked.history.raw);output.dataset.structuralDraws=String(res.ranked.history.structural);
    output.dataset.eras=JSON.stringify(res.ranked.history.eras);output.dataset.mode=res.mode;output.dataset.validation='PASS';output.dataset.pool=res.pool.join(',');output.dataset.deterministic='true';
    const payload={version:VERSION,createdAt:new Date().toISOString(),game,mode,count,pool:res.pool,tickets:res.tickets,setDetails,
      selectionDetails:res.selectionDetails,numberEvidence:res.ranked.out,numberWeights:res.ranked.weights,
      bonusEvidence:game==='pb'?res.tickets.map((_,i)=>powerballChoice(i,res.ranked)):[],
      powerballs:game==='pb'?res.tickets.map((_,i)=>powerballFor(i,res.ranked)):[],history:res.ranked.history,possibility:res.possibility,generationAudit:res.generationAudit,coverageTheorem:res.coverageTheorem,validation:res.validation};
    try{localStorage.setItem(STORE,JSON.stringify(payload))}catch(_){}
    window.PLATO_LAST_GENERATION={...payload,patterns};
  }catch(error){summary.textContent=String(error.message||error)}finally{btn.disabled=false;btn.textContent='Generate v3.5'}
}
function install(){
  const select=document.getElementById('v35Game');for(const [key,cfg] of Object.entries(GAME_CFG)){const option=document.createElement('option');option.value=key;option.textContent=cfg.name;select.appendChild(option)}
  select.value='sat';const method=document.getElementById('v35Method');if(method)method.value='astra';document.getElementById('v35Form').addEventListener('submit',run);document.getElementById('v35Generate').disabled=false;
}
window.PLATO_V35_COVERAGE={VERSION,MODES,MODE_DEFAULTS,portfolio,compare,coveragePoolK,modePool,validatePortfolio,powerballChoice,powerballFor,formatTicket,run};install();
})();