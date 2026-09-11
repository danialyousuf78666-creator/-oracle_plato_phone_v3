(function(){
'use strict';
const VERSION='3.5-possibility-space-3-proportions-system';

function choose(n,k){
  if(!Number.isInteger(n)||!Number.isInteger(k)||n<0||k<0||k>n)return 0;
  k=Math.min(k,n-k);let out=1;
  for(let i=1;i<=k;i++)out=out*(n-k+i)/i;
  return Math.round(out);
}
// Hypergeometric matching theorem; unique exact-match events are disjoint.
// P(H=j)=C(r,j)C(n-r,r-j)/C(n,r). Partial-match union bounds are not
// exact portfolio probabilities, because different tickets can win together.
function coverageTheorem(cfg,tickets){
  const {n,r}=cfg,total=choose(n,r);
  if(!total||!Array.isArray(tickets))throw new Error('Invalid coverage inputs.');
  const seen=new Set();
  for(const ticket of tickets){
    if(!Array.isArray(ticket)||ticket.length!==r||new Set(ticket).size!==r||ticket.some(x=>!Number.isInteger(x)||x<1||x>n))throw new Error('Invalid coverage ticket.');
    seen.add([...ticket].sort((a,b)=>a-b).join('-'));
  }
  const count=seen.size,matchProbabilities=Array.from({length:r+1},(_,j)=>choose(r,j)*choose(n-r,r-j)/total);
  const atLeastUnionUpperBounds=matchProbabilities.map((_,j)=>Math.min(1,count*matchProbabilities.slice(j).reduce((a,b)=>a+b,0)));
  return {theorem:'hypergeometric matching and disjoint exact coverage',n,r,totalCombinations:total,uniqueTickets:count,
    matchProbabilities,expectedTicketsByMatches:matchProbabilities.map(p=>count*p),
    exactMainMatchProbability:count/total,atLeastUnionUpperBounds,
    assumptions:'Main-number sets fixed before an independent uniform draw. Bonus balls and prize payouts are excluded.'};
}
// P(category)=category count / total count. This generalizes the user's
// 45/50=90% white and 5/50=10% black example without changing number odds.
function populationProbability(members,total){
  if(!Number.isSafeInteger(total)||total<1||!Number.isSafeInteger(members)||members<0||members>total)throw new Error('Invalid population counts.');
  return {members,total,probability:members/total,percent:100*members/total,otherPercent:100*(total-members)/total};
}
function systemSummary(cfg,numbers,referenceSum){
  const k=numbers.length,r=cfg.r;
  if(k<r||k>cfg.n||new Set(numbers).size!==k||numbers.some(x=>!Number.isInteger(x)||x<1||x>cfg.n))throw new Error('Invalid system numbers.');
  // Exact subset-sum dynamic programming: every covered standard line is counted.
  const maximum=r*cfg.n,dp=Array.from({length:r+1},()=>new Float64Array(maximum+1));dp[0][0]=1;let processed=0;
  for(const number of numbers){processed++;for(let picked=Math.min(r,processed);picked>=1;picked--)for(let sum=maximum;sum>=number;sum--)dp[picked][sum]+=dp[picked-1][sum-number];}
  const sumCounts={},rootCounts=Array(10).fill(0),qCounts={};
  for(let sum=0;sum<=maximum;sum++)if(dp[r][sum]){const count=dp[r][sum];sumCounts[sum]=count;rootCounts[sum===0?0:1+(sum-1)%9]+=count;if(Number.isFinite(referenceSum)){const q=Math.abs(sum-referenceSum);qCounts[q]=(qCounts[q]||0)+count;}}
  const lineCount=choose(k,r),values=Object.keys(sumCounts).map(Number);
  return {size:k,drawSize:r,lineCount,exactMainMatchProbability:lineCount/choose(cfg.n,r),meanLineTSUM:numbers.reduce((sum,x)=>sum+x,0)*r/k,
    minLineTSUM:Math.min(...values),maxLineTSUM:Math.max(...values),sumCounts,rootCounts,qCounts,referenceSum:referenceSum??null};
}
function* expandSystem(numbers,r){
  const ordered=[...numbers].sort((a,b)=>a-b),indices=Array.from({length:r},(_,i)=>i);if(r<1||r>ordered.length)throw new Error('Invalid system size.');
  while(true){yield indices.map(i=>ordered[i]);let i=r-1;while(i>=0&&indices[i]===ordered.length-r+i)i--;if(i<0)return;indices[i]++;for(let j=i+1;j<r;j++)indices[j]=indices[j-1]+1;}
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
    {id:'odd',label:'Odd numbers',test:x=>x%2===1,weight:.60},
    {id:'lowerHalf',label:'Lower half',test:x=>x<=Math.floor(cfg.n/2),weight:.60},
    ...Array.from({length:9},(_,i)=>({id:'droot'+(i+1),label:'DRoot '+(i+1),test:x=>1+(x-1)%9===i+1,weight:.15})),
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
      singleDraw:populationProbability(f.members,targets.cfg.n),
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

window.PLATO_V35_SPACE={VERSION,choose,coverageTheorem,populationProbability,systemSummary,expandSystem,familyDefinitions,exactFamilyDistribution,createTargets,createState,scoreTicket,recordTicket,audit,quantumAudit};
})();
