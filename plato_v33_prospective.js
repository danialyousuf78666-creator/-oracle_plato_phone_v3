(function(){
'use strict';

const STORE='ORACLE_PLATO_V33_PROSPECTIVE_V1';
const VERSION='3.3-prospective-1';
const MIN_PRIMARY_DRAWS=30;

const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const variance=a=>{if(a.length<2)return 0;const m=avg(a);return a.reduce((s,x)=>s+(x-m)*(x-m),0)/(a.length-1)};
const load=()=>{try{return JSON.parse(localStorage.getItem(STORE)||'[]')}catch(_){return []}};
const save=x=>localStorage.setItem(STORE,JSON.stringify(x));
const rowsFor=key=>currentRows(key).slice().sort((a,b)=>a[0]-b[0]);
const nums=rank=>rank.map(x=>x.number);
const hits=(a,b)=>hitCount(a,b);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function pendingFor(game){return load().find(x=>x.game===game&&x.status==='pending')}

function createSnapshot(){
  const out=document.getElementById('v33Out');
  try{
    const key=document.getElementById('v33Game').value;
    const k=Math.min(Math.max(GAME_CFG[key].r,+document.getElementById('v33K').value||15),GAME_CFG[key].n);
    if(pendingFor(key))throw new Error('A frozen prediction is already pending for this game. Score it after the next draw before creating another.');
    const rows=rowsFor(key); if(rows.length<80)throw new Error('Not enough history.');
    const latest=rows[rows.length-1];
    const model=PLATO_V32.learnCooperativeStable(key,rows,k,0);
    const classic=nums(rankNumbers(key,rows,V3_WEIGHTS).slice(0,k));
    const v32=nums(rankNumbers(key,rows,model.coopWeights).slice(0,k));
    const rec={
      version:VERSION,
      id:`${key}-${latest[0]}-${Date.now()}`,
      createdAt:new Date().toISOString(),
      game:key,k,
      asOfDraw:latest[0],asOfDate:latest[1],
      v3:classic,v32,
      classicShare:model.classicShare,
      coopWeights:model.coopWeights.slice(),
      status:'pending'
    };
    const log=load();log.push(rec);save(log);render();
    out.textContent=`Frozen before next draw.\n${GAME_CFG[key].name}\nAs of draw ${latest[0]} (${latest[1]})\nv3:   ${classic.join(' ')}\nv3.2: ${v32.join(' ')}\n\nDo not alter parameters while this prediction is pending.`;
  }catch(e){out.textContent='ERROR: '+e.message}
}

function scoreAvailable(){
  const log=load(); let scored=0;
  for(const rec of log){
    if(rec.status!=='pending')continue;
    const next=rowsFor(rec.game).find(r=>r[0]>rec.asOfDraw);
    if(!next)continue;
    rec.status='scored';rec.scoredAt=new Date().toISOString();rec.actualDraw=next[0];rec.actualDate=next[1];rec.winners=next[2].slice();
    rec.v3Hits=hits(rec.v3,next[2]);rec.v32Hits=hits(rec.v32,next[2]);rec.diff=rec.v32Hits-rec.v3Hits;scored++;
  }
  save(log);render();
  document.getElementById('v33Out').textContent=scored?`Scored ${scored} frozen prediction(s).`:'No pending prediction has a newer draw available yet.';
}

function clearPending(){
  const log=load();
  if(log.some(x=>x.status==='pending')){
    document.getElementById('v33Out').textContent='Pending predictions are immutable. Score them after the next draw; do not delete them during the trial.';return;
  }
  document.getElementById('v33Out').textContent='No pending predictions.';
}

function stats(scored){
  const a=scored.map(x=>x.v3Hits),b=scored.map(x=>x.v32Hits),d=scored.map(x=>x.diff),n=d.length,m=avg(d),se=n>1?Math.sqrt(variance(d)/n):0;
  return {n,v3:avg(a),v32:avg(b),v3Var:variance(a),v32Var:variance(b),diff:m,ci:[m-1.96*se,m+1.96*se]};
}

function render(){
  const log=load(),scored=log.filter(x=>x.status==='scored'),pending=log.filter(x=>x.status==='pending');
  const primary=scored.filter(x=>x.game==='ww'),s=stats(primary);
  const gate=s.n>=MIN_PRIMARY_DRAWS&&s.diff>0&&s.ci[0]>0&&s.v32Var<=s.v3Var;
  const summary=document.getElementById('v33Summary');
  if(summary)summary.innerHTML=`<div class="grid3"><div class="kpi"><b>${pending.length}</b><span>pending frozen predictions</span></div><div class="kpi"><b>${scored.length}</b><span>scored prospective predictions</span></div><div class="kpi"><b>${s.n}/${MIN_PRIMARY_DRAWS}</b><span>Weekday Windfall primary minimum</span></div></div><p class="note" style="margin-top:9px">Primary WW paired mean: v3 ${s.v3.toFixed(3)} vs v3.2 ${s.v32.toFixed(3)} · Δ ${s.diff.toFixed(3)} · 95% paired CI ${s.ci[0].toFixed(3)} to ${s.ci[1].toFixed(3)} · variance ${s.v3Var.toFixed(3)} vs ${s.v32Var.toFixed(3)}.</p><p class="${gate?'good':'warn'}"><b>${gate?'DESCRIPTIVE GATE PASSED — statistical audit still required':'NO PROMOTION'}</b></p>`;
  const table=document.getElementById('v33Table');
  if(table){
    table.innerHTML='<tr><th>Game</th><th>Frozen at</th><th>Actual</th><th>v3</th><th>v3.2</th><th>Δ</th><th>Status</th></tr>'+log.slice().reverse().map(x=>`<tr><td>${esc(GAME_CFG[x.game]?.name||x.game)}</td><td>${x.asOfDraw}</td><td>${x.actualDraw||'—'}</td><td>${x.v3Hits??'—'}</td><td>${x.v32Hits??'—'}</td><td>${x.diff??'—'}</td><td>${x.status}</td></tr>`).join('');
  }
}

function install(){
  if(document.getElementById('prospective'))return;
  const nav=document.getElementById('nav'),main=document.querySelector('main');if(!nav||!main)return;
  const b=document.createElement('button');b.textContent='Prospective';b.onclick=()=>{document.querySelectorAll('main section').forEach(s=>s.classList.remove('shown'));document.querySelectorAll('#nav button').forEach(x=>x.classList.remove('on'));document.getElementById('prospective').classList.add('shown');b.classList.add('on');render()};nav.appendChild(b);
  const sec=document.createElement('section');sec.id='prospective';sec.innerHTML=`<div class="card"><h2>v3.3 prospective validation</h2><p class="note">This screen freezes v3 and v3.2 shortlists before the next draw. Once the next result is added, scoring uses the stored prediction; the model is not recomputed retroactively.</p><div class="grid"><div><label>Game</label><select id="v33Game"></select></div><div><label>Shortlist size</label><input id="v33K" type="number" value="15" min="7" max="30"></div></div><button class="primary" id="v33Freeze">Freeze prediction for next draw</button><button class="secondary" id="v33Score">Score any completed predictions</button><button class="secondary" id="v33Pending">Check pending lock</button><pre id="v33Out">No prospective action yet.</pre></div><div class="card"><h2>Prospective scoreboard</h2><div id="v33Summary"></div><div class="scroll"><table id="v33Table"></table></div><p class="note">Promotion remains locked until the fixed prospective protocol is completed and corrected statistical testing is run. Historical backtests cannot satisfy this gate.</p></div>`;main.appendChild(sec);
  const sel=sec.querySelector('#v33Game');for(const [k,c] of Object.entries(GAME_CFG)){const o=document.createElement('option');o.value=k;o.textContent=c.name;sel.appendChild(o)}sel.value='ww';
  sec.querySelector('#v33Freeze').onclick=createSnapshot;sec.querySelector('#v33Score').onclick=scoreAvailable;sec.querySelector('#v33Pending').onclick=clearPending;render();
}

window.PLATO_V33={VERSION,createSnapshot,scoreAvailable,render};
install();
})();
