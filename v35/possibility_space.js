(function(){
'use strict';
const VERSION='3.5-possibility-space-1';

function choose(n,k){
  if(!Number.isInteger(n)||!Number.isInteger(k)||n<0||k<0||k>n)return 0;
  k=Math.min(k,n-k);let out=1;
  for(let i=1;i<=k;i++)out=out*(n-k+i)/i;
  return Math.round(out);
}
function countWhere(n,predicate){let m=0;for(let x=1;x<=n;x++)if(predicate(x))m++;return m;}
function digitsAllowed(x,maxDigit){
  return String(x).split('').every(ch=>{const d=Number(ch);return d>=1&&d<=maxDigit;});
}
function exactFamilyDistribution(n,r,m){
  const total=choose(n,r),counts=[],probabilities=[];
  for(let j=0;j<=r;j++){
    const count=choose(m,j)*choose(n-m,r-j);
    counts.push(count);probabilities.push(total?count/total:0);
  }
  return {members:m,total,counts,probabilities};
}
function familyDefinitions(cfg){
  const defs=[
    {id:'multiple6',label:'Multiples of 6',test:x=>x%6===0,weight:1},
    {id:'multiple7',label:'Multiples of 7',test:x=>x%7===0,weight:1},
    {id:'multiple6or7',label:'Multiples of 6 or 7',test:x=>x%6===0||x%7===0,weight:.8},
    {id:'digits1to6',label:'Digits 1–6 only',test:x=>digitsAllowed(x,6),weight:.45},
    {id:'digits1to7',label:'Digits 1–7 only',test:x=>digitsAllowed(x,7),weight:.45}
  ];
  return defs.map(def=>{
    const members=countWhere(cfg.n,def.test);
    return {...def,members,distribution:exactFamilyDistribution(cfg.n,cfg.r,members)};
  });
}
function createTargets(cfg,count){
  const total=choose(cfg.n,cfg.r),families=familyDefinitions(cfg);
  const targets={};
  for(const family of families)targets[family.id]=family.distribution.probabilities.map(p=>p*count);
  return {version:VERSION,totalCombinations:total,cfg:{n:cfg.n,r:cfg.r},families,targets};
}
function createState(targets){
  const counts={};for(const family of targets.families)counts[family.id]=Array(targets.cfg.r+1).fill(0);
  return {counts,tickets:0};
}
function signature(ticket,family){let j=0;for(const x of ticket)if(family.test(x))j++;return j;}
function scoreTicket(ticket,targets,state){
  let weighted=0,weightSum=0;
  for(const family of targets.families){
    const j=signature(ticket,family),target=targets.targets[family.id][j]||0,actual=state.counts[family.id][j]||0;
    const scale=Math.max(1,target);
    const deficit=(target-actual)/scale;
    weighted+=family.weight*Math.max(-1,Math.min(1,deficit));weightSum+=family.weight;
  }
  return weightSum?weighted/weightSum:0;
}
function recordTicket(ticket,targets,state){
  for(const family of targets.families){const j=signature(ticket,family);state.counts[family.id][j]++;}
  state.tickets++;return state;
}
function audit(targets,state){
  return {
    version:VERSION,
    totalCombinations:targets.totalCombinations,
    tickets:state.tickets,
    families:targets.families.map(f=>({
      id:f.id,label:f.label,members:f.members,
      exactTicketCounts:f.distribution.counts,
      expectedPortfolioCounts:targets.targets[f.id],
      actualPortfolioCounts:state.counts[f.id]
    }))
  };
}
function quantumAudit(rows,n){
  // Experimental diagnostic only. It intentionally carries zero production weight until
  // chronological out-of-sample validation demonstrates value for the target game.
  const clean=(rows||[]).filter(r=>Array.isArray(r?.[2])&&r[2].length).slice(-4);
  if(clean.length<4)return {version:'quantum-audit-1',enabledWeight:0,raw:null};
  const sums=clean.map(r=>r[2].reduce((a,b)=>a+b,0));
  const raw=Math.abs((sums[3]+sums[2])-(sums[1]+sums[0]));
  return {version:'quantum-audit-1',enabledWeight:0,drawSums:sums,raw,moduloNumber:raw?1+((raw-1)%n):null};
}

window.PLATO_V35_SPACE={VERSION,choose,familyDefinitions,exactFamilyDistribution,createTargets,createState,scoreTicket,recordTicket,audit,quantumAudit};
})();
