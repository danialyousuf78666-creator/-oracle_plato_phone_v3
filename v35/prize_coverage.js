(function(){
'use strict';
const VERSION='3.5-prize-coverage-9-patterns-q';
const STORE='ORACLE_PLATO_V35_PRIZE_COVERAGE_V1';
const MODES={astra:'Astra baseline',experimental:'PLATO experimental',anti_overlap:'Anti-overlap'};
const MODE_DEFAULTS={
  astra:{seedOffset:0,poolExtra:0,rankedShare:.30,possibilityWeight:0,pairNovelWeight:.26,tripleNovelWeight:.10,overlapPenaltyWeight:.12},
  experimental:{seedOffset:17017,poolExtra:4,rankedShare:.24,possibilityWeight:.65,pairNovelWeight:.32,tripleNovelWeight:.13,overlapPenaltyWeight:.18},
  anti_overlap:{seedOffset:29023,poolExtra:8,rankedShare:.15,possibilityWeight:.30,pairNovelWeight:.46,tripleNovelWeight:.22,overlapPenaltyWeight:.42}
};
const pairKey=(a,b)=>a<b?`${a}-${b}`:`${b}-${a}`;
const tripleKey=(a,b,c)=>[a,b,c].sort((x,y)=>x-y).join('-');
function clamp(x,a,b){return Math.max(a,Math.min(b,x))}
function seeded(seed){let s=seed>>>0;return()=>{s=(1664525*s+1013904223)>>>0;return s/4294967296}}
function gameSeed(game,count,rows){let s=count*9973+(rows?.length||0)*37;for(const ch of game)s=(s*33+ch.charCodeAt(0))>>>0;return s>>>0}
function coveragePoolK(game,count){
  const cfg=GAME_CFG[game];let base=15;
  try{if(window.PLATO_V35&&PLATO_V35.chooseK)base=PLATO_V35.chooseK(game)||15}catch(_){ }
  const floor=count<=20?15:(count<=50?16:18);
  return clamp(Math.max(base,floor),cfg.r+4,Math.min(cfg.n,20));
}
function modePool(ranked,cfg,baseK,mode,options={}){
  const defaults=MODE_DEFAULTS[mode],extra=Number.isFinite(options.poolExtra)?Math.max(0,Math.floor(options.poolExtra)):defaults.poolExtra;
  const k=clamp(baseK+extra,cfg.r+4,Math.min(cfg.n,28));
  return {k,pool:ranked.out.slice(0,k)};
}
function updateCounts(ticket,pairs,triples,usage){
  ticket.forEach(x=>usage[x]=(usage[x]||0)+1);
  for(let i=0;i<ticket.length;i++)for(let j=i+1;j<ticket.length;j++){
    const pk=pairKey(ticket[i],ticket[j]);pairs.set(pk,(pairs.get(pk)||0)+1);
    for(let k=j+1;k<ticket.length;k++){const tk=tripleKey(ticket[i],ticket[j],ticket[k]);triples.set(tk,(triples.get(tk)||0)+1)}
  }
}
function candidateTicket(pool,cfg,target,usage,pairs,triples,rng){
  const chosen=[];
  while(chosen.length<cfg.r){
    let best=null,bestScore=-1e99;
    for(let i=0;i<pool.length;i++){
      const item=pool[i],x=item.number;if(chosen.includes(x))continue;
      const deficit=(target[x]||0)-(usage[x]||0);let pairPenalty=0,triplePenalty=0;
      for(let a=0;a<chosen.length;a++)pairPenalty+=pairs.get(pairKey(x,chosen[a]))||0;
      for(let a=0;a<chosen.length;a++)for(let b=a+1;b<chosen.length;b++)triplePenalty+=triples.get(tripleKey(x,chosen[a],chosen[b]))||0;
      const rankBonus=(pool.length-i)/pool.length;
      const score=1.20*deficit+0.18*rankBonus-0.34*pairPenalty-0.16*triplePenalty+rng()*0.16;
      if(score>bestScore){bestScore=score;best=x}
    }
    if(best==null)break;chosen.push(best);
  }
  return chosen.sort((a,b)=>a-b);
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
  if(!MODES[mode])throw new Error('Choose Astra baseline, PLATO experimental, or Anti-overlap.');
  if(!window.PLATO_V35||!PLATO_V35.rank)throw new Error('v3.5 engine is not ready. Reload once.');
  const experimental=mode!=='astra',d=MODE_DEFAULTS[mode],cfg=GAME_CFG[game],ranked=options.rankedResult||PLATO_V35.rank(game,options),baseK=coveragePoolK(game,count),picked=modePool(ranked,cfg,baseK,mode,options),k=picked.k,pool=picked.pool;
  const scores=pool.map(x=>Math.max(.001,x.score||.001)),z=scores.reduce((a,b)=>a+b,0)||1,totalSlots=count*cfg.r,target={},usage={};
  const rankedMix=clamp(options.rankedShare==null?d.rankedShare:Number(options.rankedShare),0,1);
  pool.forEach((item,i)=>{const uniform=1/pool.length,rankedShare=scores[i]/z;target[item.number]=totalSlots*((1-rankedMix)*uniform+rankedMix*rankedShare);usage[item.number]=0});
  const pairs=new Map(),triples=new Map(),seen=new Set(),tickets=[];
  const space=experimental&&window.PLATO_V35_SPACE?PLATO_V35_SPACE.createTargets(cfg,count):null,spaceState=space?PLATO_V35_SPACE.createState(space):null;
  const rng=seeded(gameSeed(game,count,ranked.rows)+(Number.isFinite(options.seedOffset)?options.seedOffset:d.seedOffset));
  const pairNovelWeight=Number.isFinite(options.pairNovelWeight)?options.pairNovelWeight:d.pairNovelWeight;
  const tripleNovelWeight=Number.isFinite(options.tripleNovelWeight)?options.tripleNovelWeight:d.tripleNovelWeight;
  const overlapPenaltyWeight=Number.isFinite(options.overlapPenaltyWeight)?options.overlapPenaltyWeight:d.overlapPenaltyWeight;
  const possibilityWeight=experimental?(Number.isFinite(options.possibilityWeight)?options.possibilityWeight:d.possibilityWeight):0;
  const attemptsPerTicket=Math.max(30,Math.min(84,k*3));
  for(let t=0;t<count;t++){
    let best=null,bestValue=-1e99;
    for(let a=0;a<attemptsPerTicket;a++){
      const cand=candidateTicket(pool,cfg,target,usage,pairs,triples,rng);if(cand.length!==cfg.r)continue;
      const key=cand.join('-');if(seen.has(key))continue;let overlapPenalty=0;
      for(const old of tickets){let ov=0;for(const x of cand)if(old.includes(x))ov++;overlapPenalty+=ov*ov}
      let pairNovel=0,tripleNovel=0;
      for(let i=0;i<cand.length;i++)for(let j=i+1;j<cand.length;j++){
        pairNovel+=1/(1+(pairs.get(pairKey(cand[i],cand[j]))||0));
        for(let m=j+1;m<cand.length;m++)tripleNovel+=1/(1+(triples.get(tripleKey(cand[i],cand[j],cand[m]))||0));
      }
      const deficit=cand.reduce((s,x)=>s+(target[x]-(usage[x]||0)),0),possibilityScore=space?PLATO_V35_SPACE.scoreTicket(cand,space,spaceState):0;
      const value=1.1*deficit+pairNovelWeight*pairNovel+tripleNovelWeight*tripleNovel-overlapPenaltyWeight*overlapPenalty+possibilityWeight*possibilityScore+rng()*.1;
      if(value>bestValue){bestValue=value;best=cand}
    }
    if(!best){
      const ordered=pool.map(x=>x.number);
      for(let shift=0;shift<ordered.length&&!best;shift++){
        const cand=[];for(let j=0;j<cfg.r;j++)cand.push(ordered[(t*cfg.r+shift+j*2)%ordered.length]);
        const uniq=[...new Set(cand)].sort((a,b)=>a-b);if(uniq.length===cfg.r&&!seen.has(uniq.join('-')))best=uniq;
      }
    }
    if(!best)break;seen.add(best.join('-'));tickets.push(best);updateCounts(best,pairs,triples,usage);if(space)PLATO_V35_SPACE.recordTicket(best,space,spaceState);
  }
  const possibility=space?PLATO_V35_SPACE.audit(space,spaceState):null;
  const quantumAudit=experimental&&!options.skipDiagnostics&&window.PLATO_V35_SPACE?PLATO_V35_SPACE.quantumAudit(ranked.compatibleRows||ranked.rows,cfg.n):null;
  const randomnessAudit=experimental&&!options.skipDiagnostics&&window.PLATO_V35_RANDOMNESS?PLATO_V35_RANDOMNESS.audit(game,options):null;
  const validation=validatePortfolio(game,count,tickets);
  return {mode,modeLabel:MODES[mode],cfg,ranked,k,baseK,pool:pool.map(x=>x.number),tickets,usage,pairs,triples,possibility,quantumAudit,randomnessAudit,validation,options:{poolExtra:k-baseK,rankedShare:rankedMix,pairNovelWeight,tripleNovelWeight,overlapPenaltyWeight,possibilityWeight}};
}
function compare(game,count){
  const astra=portfolio(game,count,'astra'),experimental=portfolio(game,count,'experimental'),antiOverlap=portfolio(game,count,'anti_overlap');
  return {game,count,astra,experimental,antiOverlap,pass:astra.validation.pass&&experimental.validation.pass&&antiOverlap.validation.pass};
}
function powerballFor(i,seed){return 1+((seed+i*7)%20)}
function formatTicket(game,ticket,i,seed){const main=ticket.map(x=>String(x).padStart(2,'0')).join(' ');return game==='pb'?`${main}   PB ${String(powerballFor(i,seed)).padStart(2,'0')}`:main}
function renderPatterns(analysis,theoremAudit){
  let panel=document.getElementById('v35Patterns');
  if(!panel){panel=document.createElement('section');panel.id='v35Patterns';document.getElementById('v35Tickets').after(panel);}
  panel.replaceChildren();panel.hidden=false;
  const title=document.createElement('h2');title.textContent='Common and uncommon patterns';panel.appendChild(title);
  const note=document.createElement('p');note.className='note';
  note.textContent=`${analysis.totalDraws} stored draws analysed. Counts use the ${analysis.current.drawCount} draws under current rules. Common = most observed; uncommon = least observed. Ties stay unclassified. Q compares main-number sums with the preceding draw in the same era.`;panel.appendChild(note);
  if(theoremAudit){
    const info=document.createElement('p');info.className='note';
    info.textContent=`Randomness diagnostic: peak capital 2^${theoremAudit.martingale.maxLog2Capital.toFixed(2)}; bound across ${theoremAudit.simultaneousGames} games ${theoremAudit.familywiseVilleUpperBound.toPrecision(3)} under independent uniform draws. Historical diagnostic only.`;panel.appendChild(info);
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
    const res=portfolio(game,count,mode),seed=gameSeed(game,count,res.ranked.rows)+(MODE_DEFAULTS[mode]?.seedOffset||0);if(!res.validation.pass)throw new Error(`Portfolio validation failed: ${res.validation.reason}`);
    summary.textContent=`${GAME_CFG[game].name} · ${res.modeLabel} · ${res.tickets.length} tickets · ${res.pool.length} candidate numbers · PASS`;
    const patterns=PLATO_V35.analysePatterns(game,{rows:res.ranked.rows}),setDetails=res.tickets.map(ticket=>PLATO_V35.classifySet(ticket,patterns));
    const theoremAudit=res.randomnessAudit||(window.PLATO_V35_RANDOMNESS?PLATO_V35_RANDOMNESS.audit(game,{rows:res.ranked.rows}):null);
    const fragment=document.createDocumentFragment();
    res.tickets.forEach((ticket,i)=>{
      const item=document.createElement('li'),details=setDetails[i];item.className='ticket';item.textContent=formatTicket(game,ticket,i,seed);
      const stats=document.createElement('span');stats.style.display='block';stats.style.fontSize='12px';stats.style.color='#b9c2ce';
      stats.textContent=`Main TSUM: ${details.tsum} · Set DRoot: ${details.setDigitalRoot}\nNumber DRoots: ${details.individualDigitalRoots.map(x=>`${x.number}→${x.droot}`).join(' ')}`;
      if(details.comparison)stats.textContent+=`\nQ: ${details.comparison.q_t} vs draw ${details.comparison.referenceDraw} · Q DRoot: ${details.comparison.qDigitalRoot}`;
      for(const status of ['common','uncommon','not observed']){
        const labels=Object.entries(details.behaviour).filter(([,value])=>value.status===status).map(([key])=>patterns.current.groups[key].label);
        if(labels.length)stats.textContent+=`\n${status[0].toUpperCase()+status.slice(1)}: ${labels.join(', ')}`;
      }
      if(game==='pb')stats.textContent+=`\nPB DRoot: ${PLATO_V35.digitalRoot(powerballFor(i,seed))}`;
      item.appendChild(stats);fragment.appendChild(item);
    });
    output.appendChild(fragment);renderPatterns(patterns,theoremAudit);
    output.dataset.historyTotal=String(res.ranked.history.total);output.dataset.rawDraws=String(res.ranked.history.raw);output.dataset.structuralDraws=String(res.ranked.history.structural);output.dataset.eras=JSON.stringify(res.ranked.history.eras);output.dataset.mode=res.mode;output.dataset.validation='PASS';output.dataset.pool=res.pool.join(',');
    try{localStorage.setItem(STORE,JSON.stringify({version:VERSION,createdAt:new Date().toISOString(),game,mode,count,pool:res.pool,tickets:res.tickets,setDetails,powerballs:game==='pb'?res.tickets.map((_,i)=>powerballFor(i,seed)):[],history:res.ranked.history,possibility:res.possibility,quantumAudit:res.quantumAudit,randomnessAudit:res.randomnessAudit,theoremAudit,validation:res.validation}))}catch(_){ }
    window.PLATO_LAST_GENERATION={version:VERSION,game,mode,count,pool:res.pool,history:res.ranked.history,tickets:res.tickets,setDetails,patterns,possibility:res.possibility,quantumAudit:res.quantumAudit,randomnessAudit:res.randomnessAudit,theoremAudit,validation:res.validation};
  }catch(error){summary.textContent=String(error.message||error)}finally{btn.disabled=false;btn.textContent='Generate v3.5'}
}
function install(){const select=document.getElementById('v35Game');for(const [key,cfg] of Object.entries(GAME_CFG)){const option=document.createElement('option');option.value=key;option.textContent=cfg.name;select.appendChild(option)}select.value='sat';const method=document.getElementById('v35Method');if(method)method.value='astra';document.getElementById('v35Form').addEventListener('submit',run);document.getElementById('v35Generate').disabled=false}
window.PLATO_V35_COVERAGE={VERSION,MODES,MODE_DEFAULTS,portfolio,compare,coveragePoolK,modePool,validatePortfolio,formatTicket,run};install();
})();
