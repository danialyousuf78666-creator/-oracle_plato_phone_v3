(function(){
'use strict';

const VERSION='3.4-adaptive-pool-1';
const BASE_K=15;
const MIN_K=12;
const MAX_K=18;

function intersectCount(a,b){const s=new Set(a);return b.filter(x=>s.has(x)).length}
function numbers(rank){return rank.map(x=>x.number)}

function poolFromAgreement(agreement){
  if(agreement>=11)return 12;
  if(agreement>=9)return 13;
  if(agreement===8)return 14;
  if(agreement>=6)return 15;
  if(agreement>=4)return 16;
  if(agreement===3)return 17;
  return 18;
}

function recommend(game){
  if(!window.PLATO_V32)throw new Error('PLATO v3.2 engine is not loaded.');
  const rows=currentRows(game).slice().sort((a,b)=>a[0]-b[0]);
  if(rows.length<80)throw new Error('Not enough current-format history.');
  const model=PLATO_V32.learnCooperativeStable(game,rows,BASE_K,0);
  const v3=numbers(rankNumbers(game,rows,V3_WEIGHTS).slice(0,BASE_K));
  const v31=numbers(rankNumbers(game,rows,model.weights).slice(0,BASE_K));
  const agreement=intersectCount(v3,v31);
  const k=Math.max(MIN_K,Math.min(MAX_K,poolFromAgreement(agreement)));
  const ratio=agreement/BASE_K;
  const label=agreement>=9?'high consensus':agreement>=6?'normal consensus':agreement>=4?'low consensus':'very low consensus';
  return {version:VERSION,game,k,agreement,ratio,label,v3,v31,classicShare:model.classicShare};
}

function setInput(id,k){const el=document.getElementById(id);if(el)el.value=String(k)}
function apply(game,targetId,outId){
  try{
    const r=recommend(game);setInput(targetId,r.k);
    const out=document.getElementById(outId);
    if(out)out.textContent=`Adaptive pool: ${r.k} numbers · v3/v3.1 agreement ${r.agreement}/15 (${r.label}).\nRule is frozen: 11+→12, 9–10→13, 8→14, 6–7→15, 4–5→16, 3→17, 0–2→18.`;
    return r;
  }catch(e){const out=document.getElementById(outId);if(out)out.textContent='ERROR: '+e.message;return null}
}

function addButton(sectionId,gameId,targetId,label){
  const sec=document.getElementById(sectionId),game=document.getElementById(gameId),target=document.getElementById(targetId);
  if(!sec||!game||!target||sec.querySelector('.v34-adaptive-button'))return;
  const b=document.createElement('button');
  b.className='secondary v34-adaptive-button';
  b.textContent='Use adaptive 12–18 pool';
  const out=document.createElement('pre');out.id='v34-'+sectionId+'-out';out.textContent='Adaptive pool not calculated yet.';
  b.onclick=()=>apply(game.value,targetId,out.id);
  const card=target.closest('.card')||sec.querySelector('.card')||sec;
  card.appendChild(b);card.appendChild(out);
}

function install(){
  addButton('analysis','gameSelect','shortK','Analysis');
  addButton('tickets','ticketGame','ticketK','Tickets');
  const home=document.getElementById('home');
  if(home&&!document.getElementById('v34Info')){
    const d=document.createElement('div');d.className='card';d.id='v34Info';
    d.innerHTML='<h2>Adaptive shortlist v3.4</h2><p class="note">Experimental only. Pool size is selected from 12–18 using the predeclared v3/v3.1 top-15 agreement rule. It does not alter classic v3, v3.2, or the fixed v3.3 prospective protocol.</p>';
    home.appendChild(d);
  }
}

window.PLATO_V34={VERSION,BASE_K,MIN_K,MAX_K,recommend,poolFromAgreement,apply};
install();
})();
