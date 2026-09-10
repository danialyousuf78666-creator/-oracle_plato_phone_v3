(function(){
'use strict';
const VERSION='3.5-prize-coverage-7-three-mode';
const STORE='ORACLE_PLATO_V35_PRIZE_COVERAGE_V1';
const MODES={astra:'Astra baseline',experimental:'PLATO experimental',anti_overlap:'Anti-overlap'};
const MODE_DEFAULTS={
  astra:{seedOffset:0,possibilityWeight:0,pairNovelWeight:.26,tripleNovelWeight:.10,overlapPenaltyWeight:.12},
  experimental:{seedOffset:17017,possibilityWeight:.60,pairNovelWeight:.30,tripleNovelWeight:.12,overlapPenaltyWeight:.16},
  anti_overlap:{seedOffset:29023,possibilityWeight:.40,pairNovelWeight:.38,tripleNovelWeight:.18,overlapPenaltyWeight:.30}
};

const pairKey=(a,b)=>a<b?`${a}-${b}`:`${b}-${a}`;
const tripleKey=(a,b,c)=>[a,b,c].sort((x,y)=>x-y).join('-');
function clamp(x,a,b){return Math.max(a,Math.min(b,x))}
function seeded(seed){let s=seed>>>0;return()=>{s=(1664525*s+1013904223)>>>0;return s/4294967296}}
function gameSeed(game,count,rows){let s=count*9973+(rows?.length||0)*37;for(const ch of game)s=(s*33+ch.charCodeAt(0))>>>0;return s>>>0}

function coveragePoolK(game,count){
  const cfg=GAME_CFG[game];
  let base=15;
  try{ if(window.PLATO_V35&&PLATO_V35.chooseK) base=PLATO_V35.chooseK(game)||15; }catch(_){ }
  const floor=count<=20?15:(count<=50?16:18);
  return clamp(Math.max(base,floor),cfg.r+4,Math.min(cfg.n,20));
}

function updateCounts(ticket,pairs,triples,usage){
  ticket.forEach(x=>usage[x]=(usage[x]||0)+1);
  for(let i=0;i<ticket.length;i++)for(let j=i+1;j<ticket.length;j++){
    const pk=pairKey(ticket[i],ticket[j]);pairs.set(pk,(pairs.get(pk)||0)+1);
    for(let k=j+1;k<ticket.length;k++){
      const tk=tripleKey(ticket[i],ticket[j],ticket[k]);triples.set(tk,(triples.get(tk)||0)+1);
    }
  }
}

function candidateTicket(pool,cfg,target,usage,pairs,triples,rng){
  const chosen=[];
  while(chosen.length<cfg.r){
    let best=null,bestScore=-1e99;
    for(let i=0;i<pool.length;i++){
      const item=pool[i],x=item.number;if(chosen.includes(x))continue;
      const deficit=(target[x]||0)-(usage[x]||0);
      let pairPenalty=0,triplePenalty=0;
      for(let a=0;a<chosen.length;a++)pairPenalty+=pairs.get(pairKey(x,chosen[a]))||0;
      for(let a=0;a<chosen.length;a++)for(let b=a+1;b<chosen.length;b++)triplePenalty+=triples.get(tripleKey(x,chosen[a],chosen[b]))||0;
      const rankBonus=(pool.length-i)/pool.length;
      const score=1.20*deficit+0.18*rankBonus-0.34*pairPenalty-0.16*triplePenalty+rng()*0.16;
      if(score>bestScore){bestScore=score;best=x}
    }
    if(best==null)break;
    chosen.push(best);
  }
  return chosen.sort((a,b)=>a-b);
}

function validatePortfolio(game,count,tickets){
  const cfg=GAME_CFG[game];
  if(!cfg||tickets.length!==count)return {pass:false,reason:'ticket-count'};
  const seen=new Set();
  for(const ticket of tickets){
    if(ticket.length!==cfg.r||new Set(ticket).size!==cfg.r)return {pass:false,reason:'ticket-shape'};
    if(ticket.some(x=>!Number.isInteger(x)||x<1||x>cfg.n))return {pass:false,reason:'number-range'};
    const key=[...ticket].sort((a,b)=>a-b).join('-');if(seen.has(key))return {pass:false,reason:'duplicate-ticket'};seen.add(key);
  }
  return {pass:true,reason:'ok'};
}

function portfolio(game,count,mode='experimental',options={}){
  if(!GAME_CFG[game]||!Number.isInteger(count)||count<1||count>100)throw new Error('Choose 1–100 whole tickets.');
  if(!MODES[mode])throw new Error('Choose Astra baseline, PLATO experimental, or Anti-overlap.');
  if(!window.PLATO_V35||!PLATO_V35.rank)throw new Error('v3.5 engine is not ready. Reload once.');
  const experimental=mode!=='astra',modeDefaults=MODE_DEFAULTS[mode];
  const cfg=GAME_CFG[game],ranked=options.rankedResult||PLATO_V35.rank(game,options),k=coveragePoolK(game,count),pool=ranked.out.slice(0,k);
  const scores=pool.map(x=>Math.max(0.001,x.score||0.001));
  const z=scores.reduce((a,b)=>a+b,0)||1,totalSlots=count*cfg.r,target={},usage={};
  const rankedMix=clamp(options.rankedShare==null?0.30:Number(options.rankedShare),0,1);
  pool.forEach((item,i)=>{
    const uniform=1/pool.length,rankedShare=scores[i]/z;
    target[item.number]=totalSlots*((1-rankedMix)*uniform+rankedMix*rankedShare);
    usage[item.number]=0;
  });
  const pairs=new Map(),triples=new Map(),seen=new Set(),tickets=[];
  const space=experimental&&window.PLATO_V35_SPACE?PLATO_V35_SPACE.createTargets(cfg,count):null;
  const spaceState=space?PLATO_V35_SPACE.createState(space):null;
  const rng=seeded(gameSeed(game,count,ranked.rows)+(Number.isFinite(options.seedOffset)?options.seedOffset:modeDefaults.seedOffset));
  const pairNovelWeight=Number.isFinite(options.pairNovelWeight)?options.pairNovelWeight:modeDefaults.pairNovelWeight;
  const tripleNovelWeight=Number.isFinite(options.tripleNovelWeight)?options.tripleNovelWeight:modeDefaults.tripleNovelWeight;
  const overlapPenaltyWeight=Number.isFinite(options.overlapPenaltyWeight)?options.overlapPenaltyWeight:modeDefaults.overlapPenaltyWeight;
  const possibilityWeight=experimental?(Number.isFinite(options.possibilityWeight)?options.possibilityWeight:modeDefaults.possibilityWeight):0;
  const attemptsPerTicket=Math.max(28,Math.min(70,k*3));
  for(let t=0;t<count;t++){
    let best=null,bestValue=-1e99;
    for(let a=0;a<attemptsPerTicket;a++){
      const cand=candidateTicket(pool,cfg,target,usage,pairs,triples,rng);
      if(cand.length!==cfg.r)continue;
      const key=cand.join('-');if(seen.has(key))continue;
      let overlapPenalty=0;
      for(const old of tickets){let ov=0;for(const x of cand)if(old.includes(x))ov++;overlapPenalty+=ov*ov;}
      let pairNovel=0,tripleNovel=0;
      for(let i=0;i<cand.length;i++)for(let j=i+1;j<cand.length;j++){
        pairNovel+=1/(1+(pairs.get(pairKey(cand[i],cand[j]))||0));
        for(let m=j+1;m<cand.length;m++)tripleNovel+=1/(1+(triples.get(tripleKey(cand[i],cand[j],cand[m]))||0));
      }
      const deficit=cand.reduce((s,x)=>s+(target[x]-(usage[x]||0)),0);
      const possibilityScore=space?PLATO_V35_SPACE.scoreTicket(cand,space,spaceState):0;
      const value=1.1*deficit+pairNovelWeight*pairNovel+tripleNovelWeight*tripleNovel-overlapPenaltyWeight*overlapPenalty+possibilityWeight*possibilityScore+rng()*0.1;
      if(value>bestValue){bestValue=value;best=cand}
    }
    if(!best){
      const ordered=pool.map(x=>x.number);
      for(let shift=0;shift<ordered.length&&!best;shift++){
        const cand=[];for(let j=0;j<cfg.r;j++)cand.push(ordered[(t*cfg.r+shift+j*2)%ordered.length]);
        const uniq=[...new Set(cand)].sort((a,b)=>a-b);
        if(uniq.length===cfg.r&&!seen.has(uniq.join('-')))best=uniq;
      }
    }
    if(!best)break;
    seen.add(best.join('-'));tickets.push(best);updateCounts(best,pairs,triples,usage);if(space)PLATO_V35_SPACE.recordTicket(best,space,spaceState);
  }
  const possibility=space?PLATO_V35_SPACE.audit(space,spaceState):null;
  const quantumAudit=experimental&&!options.skipDiagnostics&&window.PLATO_V35_SPACE?PLATO_V35_SPACE.quantumAudit(ranked.compatibleRows||ranked.rows,cfg.n):null;
  const randomnessAudit=experimental&&!options.skipDiagnostics&&window.PLATO_V35_RANDOMNESS?PLATO_V35_RANDOMNESS.audit(game,options):null;
  const validation=validatePortfolio(game,count,tickets);
  return {mode,modeLabel:MODES[mode],cfg,ranked,k,pool:pool.map(x=>x.number),tickets,usage,pairs,triples,possibility,quantumAudit,randomnessAudit,validation,options:{rankedShare:rankedMix,pairNovelWeight,tripleNovelWeight,overlapPenaltyWeight,possibilityWeight}};
}

function compare(game,count){
  const astra=portfolio(game,count,'astra'),experimental=portfolio(game,count,'experimental');
  return {game,count,astra,experimental,pass:astra.validation.pass&&experimental.validation.pass};
}

function powerballFor(i,seed){return 1+((seed+i*7)%20)}
function formatTicket(game,ticket,i,seed){
  const main=ticket.map(x=>String(x).padStart(2,'0')).join(' ');
  return game==='pb'?`${main}   PB ${String(powerballFor(i,seed)).padStart(2,'0')}`:main;
}

async function run(event){
  if(event)event.preventDefault();
  const form=document.getElementById('v35Form');if(!form.reportValidity())return;
  const game=document.getElementById('v35Game').value,mode=document.getElementById('v35Method').value,count=Number(document.getElementById('v35Count').value);
  const btn=document.getElementById('v35Generate'),summary=document.getElementById('v35Summary'),output=document.getElementById('v35Tickets');
  if(btn.disabled)return;btn.disabled=true;btn.textContent='Generating…';summary.textContent='';output.replaceChildren();
  await new Promise(resolve=>setTimeout(resolve,0));
  try{
    const res=portfolio(game,count,mode),seed=gameSeed(game,count,res.ranked.rows);
    if(!res.validation.pass)throw new Error(`Portfolio validation failed: ${res.validation.reason}`);
    summary.textContent=`${GAME_CFG[game].name} · ${res.modeLabel} · ${res.tickets.length} tickets · PASS`;
    const fragment=document.createDocumentFragment();
    res.tickets.forEach((ticket,i)=>{const item=document.createElement('li');item.className='ticket';item.textContent=formatTicket(game,ticket,i,seed);fragment.appendChild(item);});
    output.appendChild(fragment);
    output.dataset.historyTotal=String(res.ranked.history.total);
    output.dataset.rawDraws=String(res.ranked.history.raw);
    output.dataset.structuralDraws=String(res.ranked.history.structural);
    output.dataset.eras=JSON.stringify(res.ranked.history.eras);
    output.dataset.mode=res.mode;
    output.dataset.validation='PASS';
    try{localStorage.setItem(STORE,JSON.stringify({version:VERSION,createdAt:new Date().toISOString(),game,mode,count,
      pool:res.pool,tickets:res.tickets,powerballs:game==='pb'?res.tickets.map((_,i)=>powerballFor(i,seed)):[],history:res.ranked.history,possibility:res.possibility,quantumAudit:res.quantumAudit,randomnessAudit:res.randomnessAudit,validation:res.validation}));}catch(_){ }
    window.PLATO_LAST_GENERATION={version:VERSION,game,mode,count,history:res.ranked.history,tickets:res.tickets,possibility:res.possibility,quantumAudit:res.quantumAudit,randomnessAudit:res.randomnessAudit,validation:res.validation};
  }catch(error){summary.textContent=String(error.message||error);}
  finally{btn.disabled=false;btn.textContent='Generate v3.5';}
}
function install(){
  const select=document.getElementById('v35Game');
  for(const [key,cfg] of Object.entries(GAME_CFG)){const option=document.createElement('option');option.value=key;option.textContent=cfg.name;select.appendChild(option);}
  select.value='sat';
  const method=document.getElementById('v35Method');if(method)method.value='astra';
  document.getElementById('v35Form').addEventListener('submit',run);
  document.getElementById('v35Generate').disabled=false;
}
window.PLATO_V35_COVERAGE={VERSION,MODES,portfolio,compare,coveragePoolK,validatePortfolio,formatTicket,run};
install();
})();
