(function(){
'use strict';
const VERSION='3.5-prize-coverage-1';
const STORE='ORACLE_PLATO_V35_PRIZE_COVERAGE_V1';

const pairKey=(a,b)=>a<b?`${a}-${b}`:`${b}-${a}`;
const tripleKey=(a,b,c)=>[a,b,c].sort((x,y)=>x-y).join('-');
function clamp(x,a,b){return Math.max(a,Math.min(b,x))}
function avg(a){return a.length?a.reduce((s,x)=>s+x,0)/a.length:0}
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

function portfolio(game,count){
  if(!window.PLATO_V35||!PLATO_V35.rank)throw new Error('v3.5 engine is not ready. Reload once.');
  const cfg=GAME_CFG[game],ranked=PLATO_V35.rank(game),k=coveragePoolK(game,count),pool=ranked.out.slice(0,k);
  const scores=pool.map((x,i)=>Math.max(0.001,x.score||0.001));
  const z=scores.reduce((a,b)=>a+b,0)||1,totalSlots=count*cfg.r,target={},usage={};
  pool.forEach((item,i)=>{
    const uniform=1/pool.length,rankedShare=scores[i]/z;
    target[item.number]=totalSlots*(0.70*uniform+0.30*rankedShare);
    usage[item.number]=0;
  });
  const pairs=new Map(),triples=new Map(),seen=new Set(),tickets=[];
  const rng=seeded(gameSeed(game,count,ranked.rows));
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
      const value=1.1*deficit+0.26*pairNovel+0.10*tripleNovel-0.12*overlapPenalty+rng()*0.1;
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
    seen.add(best.join('-'));tickets.push(best);updateCounts(best,pairs,triples,usage);
  }
  return {cfg,ranked,k,pool:pool.map(x=>x.number),tickets,usage,pairs,triples};
}

function powerballFor(i,seed){return 1+((seed+i*7)%20)}
function formatTicket(game,ticket,i,seed){
  const main=ticket.map(x=>String(x).padStart(2,'0')).join(' ');
  return game==='pb'?`${main}   PB ${String(powerballFor(i,seed)).padStart(2,'0')}`:main;
}

function run(){
  const game=document.getElementById('v35Game').value;
  const count=clamp(parseInt(document.getElementById('v35Count').value||'20',10),1,100);
  const btn=document.getElementById('v35Generate');btn.disabled=true;btn.textContent='Generating…';
  try{
    const res=portfolio(game,count),seed=gameSeed(game,count,res.ranked.rows);
    const usageVals=Object.values(res.usage),minUse=Math.min(...usageVals),maxUse=Math.max(...usageVals);
    document.getElementById('v35Summary').innerHTML=`<div class="stats"><div><b>${res.ranked.rows.length}</b><span>historical draws used</span></div><div><b>${res.k}</b><span>automatic pool</span></div><div><b>${res.tickets.length}</b><span>unique tickets</span></div></div><h3>Candidate pool</h3><div class="pool">${res.pool.map(x=>`<span>${String(x).padStart(2,'0')}</span>`).join('')}</div><p class="muted">Prize Coverage Mode softens concentration: candidate usage ranges ${minUse}–${maxUse} appearances across this portfolio while pair/triple repetition is penalized.</p>`;
    document.getElementById('v35Tickets').innerHTML=res.tickets.map((t,i)=>`<div class="ticket"><b>${String(i+1).padStart(2,'0')}.</b> ${formatTicket(game,t,i,seed)}</div>`).join('');
    localStorage.setItem(STORE,JSON.stringify({version:VERSION,createdAt:new Date().toISOString(),game,count,pool:res.pool,tickets:res.tickets}));
  }catch(e){document.getElementById('v35Tickets').innerHTML=`<div class="error">${String(e.message||e)}</div>`}
  finally{btn.disabled=false;btn.textContent='Generate v3.5'}
}

function render(){
  document.title='ORACLE / PLATO v3.5';
  const style=document.createElement('style');
  style.textContent=`:root{--bg:#0b0c0e;--card:#15181c;--card2:#0f1114;--text:#f4f6f8;--muted:#9da5af;--line:#2a3038}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{padding:max(20px,env(safe-area-inset-top)) 18px 14px;border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(11,12,14,.96);backdrop-filter:blur(14px);z-index:3}h1{font-size:25px;margin:0}.sub{color:var(--muted);font-size:13px;margin-top:5px}main{max-width:760px;margin:auto;padding:18px 16px calc(40px + env(safe-area-inset-bottom))}.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px}label{display:block;color:var(--muted);font-size:12px;margin:12px 0 6px}select,input{width:100%;background:#0d0f12;color:#fff;border:1px solid var(--line);border-radius:12px;padding:12px;font-size:17px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:580px){.grid{grid-template-columns:1fr}}button{width:100%;border:0;border-radius:12px;padding:14px;margin-top:16px;font-weight:800;font-size:16px;background:#f5f6f7;color:#111}.note,.muted{color:var(--muted);font-size:12px;line-height:1.5}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:16px}.stats div{background:var(--card2);border:1px solid var(--line);border-radius:12px;padding:10px}.stats b{display:block;font-size:19px}.stats span{display:block;color:var(--muted);font-size:10px;margin-top:3px}.pool{display:flex;flex-wrap:wrap;gap:6px}.pool span{border:1px solid var(--line);background:#20242a;border-radius:999px;padding:6px 9px;font-weight:700}.ticket{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#0d0f12;border:1px solid var(--line);border-radius:11px;padding:10px;margin-top:7px;font-size:14px}.error{padding:12px;border:1px solid #6a3232;background:#2a1717;border-radius:10px;color:#ffd0d0}h2{margin:0 0 4px;font-size:20px}h3{margin:16px 0 8px;font-size:14px}`;
  document.head.appendChild(style);
  document.body.innerHTML=`<header><h1>ORACLE / PLATO — v3.5</h1><div class="sub">full-history distilled engine • Prize Coverage Mode • on-device</div></header><main><div class="card"><h2>Generate numbers</h2><p class="note">PLATO automatically checks all compatible historical draws. No history-window or fold controls are needed here.</p><div class="grid"><div><label>Game</label><select id="v35Game"></select></div><div><label>Tickets</label><input id="v35Count" type="number" min="1" max="100" value="20"></div></div><button id="v35Generate">Generate v3.5</button><div id="v35Summary"></div><div id="v35Tickets"></div><p class="note" style="margin-top:16px">Prize Coverage Mode is designed to diversify partial-match coverage across the portfolio. It does not change the equal probability of exact combinations in a fair draw.${GAME_CFG.pb?' Powerball numbers are coverage-rotated rather than model-ranked.':''}</p></div></main>`;
  const sel=document.getElementById('v35Game');
  for(const [key,cfg] of Object.entries(GAME_CFG)){const o=document.createElement('option');o.value=key;o.textContent=cfg.name;sel.appendChild(o)}
  sel.value='sat';
  document.getElementById('v35Generate').addEventListener('click',run);
}

if(window.PLATO_V35&&window.GAME_CFG)render();else setTimeout(render,0);
window.PLATO_V35_COVERAGE={VERSION,portfolio,coveragePoolK};
})();
