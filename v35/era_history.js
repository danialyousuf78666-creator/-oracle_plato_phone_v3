(function(){
'use strict';
// Full-history contract: identities stay in their rule era; only normalized
// structure transfers between eras. Draw boundaries are explicit, not inferred
// from the largest number observed in a particular result.
const ERAS=Object.freeze({
  pb:[{start:1,n:45,r:5},{start:877,n:40,r:6},{start:1144,n:35,r:7}],
  sat:[{start:1,n:45,r:6}],
  oz:[{start:1,n:45,r:6},{start:609,n:45,r:7},{start:1474,n:47,r:7}],
  sfl:[{start:1,n:37,r:8},{start:1691,n:44,r:7}],
  ww:[{start:4392,n:45,r:6}]
});
function eraFor(game,id){const eras=ERAS[game];if(!eras)throw new Error('Unsupported game.');return eras.filter(e=>id>=e.start).at(-1);}
function additions(){try{return JSON.parse(localStorage.getItem('oracle_plato_phone_v3_additions')||'{}');}catch{return {};}}
function historyFor(game,options={}){
  if(!ERAS[game])throw new Error('Unsupported game.');
  const target=options.beforeDraw?eraFor(game,options.beforeDraw):ERAS[game].at(-1);
  if(!target)throw new Error('Target draw has no supported era.');
  const supplied=options.rows||[...PLATO_DATA.SEED_DATA[game],...(additions()[game]||[])];
  const cutoff=options.asOf||new Date().toISOString().slice(0,10),byId=new Map();
  for(const row of supplied){
    if(options.beforeDraw&&row[0]>=options.beforeDraw)continue;
    if(typeof row[1]==='string'&&row[1]>cutoff)continue;
    const era=eraFor(game,row[0]);
    if(!era||!Number.isInteger(row[0])||!/^\d{4}-\d{2}-\d{2}$/.test(row[1])||
      !Number.isFinite(Date.parse(row[1]))||new Date(row[1]).toISOString().slice(0,10)!==row[1]||
      !Array.isArray(row[2])||row[2].length!==era.r||new Set(row[2]).size!==era.r||
      row[2].some(x=>!Number.isInteger(x)||x<1||x>era.n))throw new Error(`Invalid ${game} draw ${row[0]}.`);
    const previous=byId.get(row[0]);
    if(previous&&JSON.stringify(previous[2])!==JSON.stringify(row[2]))throw new Error(`Conflicting draw ${row[0]}.`);
    byId.set(row[0],row);
  }
  const rows=[...byId.values()].sort((a,b)=>a[0]-b[0]);
  rows.forEach((row,i)=>{if(i&&row[1]<=rows[i-1][1])throw new Error('Draw dates are not chronological.');});
  const annotated=rows.map(row=>({row,era:eraFor(game,row[0])}));
  const compatible=annotated.filter(x=>x.era.start===target.start).map(x=>x.row);
  return {rows,compatible,annotated,target,eraCounts:Object.fromEntries(ERAS[game].map(e=>[
    `${e.r}/${e.n}@${e.start}`,annotated.filter(x=>x.era.start===e.start).length]))};
}
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
function normalize(o,n){const v=Object.values(o),lo=Math.min(...v),hi=Math.max(...v),d=hi-lo||1;return Object.fromEntries(Array.from({length:n},(_,i)=>[i+1,(o[i+1]-lo)/d]));}
function structuralFeatures(annotated,n,r){
  const empty=()=>Object.fromEntries(Array.from({length:n},(_,i)=>[i+1,0]));
  const density=empty(),sum=empty(),pos=empty(),adj=empty(),sig=empty(),range=empty(),par=empty(),bins=Array(5).fill(0);
  // Linear projection transfers normalized position, never raw number identity.
  function add(o,coordinate,weight){
    const x=Math.max(1,Math.min(n,coordinate*n)),lo=Math.floor(x),hi=Math.ceil(x);
    if(lo===hi)o[lo]+=weight;else {o[lo]+=weight*(hi-x);o[hi]+=weight*(x-lo);}
  }
  const frames=annotated.map(({row,era})=>{
    const coords=row[2].map(x=>x/era.n).sort((a,b)=>a-b),odd=row[2].filter(x=>x%2).length/era.r;
    return {coords,era,odd,mean:avg(coords),low:coords.filter(x=>x<=1/3).length/era.r};
  });
  const means=frames.map(x=>x.mean),centre=avg(means),spread=Math.sqrt(avg(means.map(x=>(x-centre)**2)))||1;
  const last=frames.at(-1),oddRate=avg(frames.map(x=>x.odd/(Math.ceil(x.era.n/2)/x.era.n))),
    evenRate=avg(frames.map(x=>(1-x.odd)/(Math.floor(x.era.n/2)/x.era.n)));
  frames.forEach((frame,i)=>{
    const {coords,era}=frame,weight=1/era.r,z=(frame.mean-centre)/spread;
    const distance=last?4*r*Math.abs(frame.mean-last.mean)+r*Math.abs(frame.odd-last.odd)+r*Math.abs(frame.low-last.low):0;
    coords.forEach((x,j)=>{
      add(density,x,weight);add(sum,x,weight*Math.exp(-z*z/2));
      add(pos,x,weight/(1+n*Math.abs(x-(j+.5)/era.r)));
      if(i<frames.length-1)add(sig,x,weight/(1+distance));
      bins[Math.max(0,Math.min(4,Math.floor((x-.5/era.n)*5)))]+=weight;
      if(j&&((x-coords[j-1])*era.r<=2*r/n)){
        const ageWeight=Math.pow(.5,(frames.length-1-i)/100);
        add(adj,x,weight*ageWeight);add(adj,coords[j-1],weight*ageWeight);
      }
    });
  });
  for(let x=1;x<=n;x++){range[x]=bins[Math.min(4,Math.floor((x-.5)*5/n))];par[x]=x%2?oddRate:evenRate;}
  return {density:normalize(density,n),sum:normalize(sum,n),pos:normalize(pos,n),adj:normalize(adj,n),
    sig:normalize(sig,n),range:normalize(range,n),par:normalize(par,n),draws:frames.length};
}
window.PLATO_HISTORY={ERAS,eraFor,historyFor,structuralFeatures};
})();
