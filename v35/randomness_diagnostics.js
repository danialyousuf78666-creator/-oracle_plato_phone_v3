(function(){
'use strict';
const VERSION='3.5-randomness-diagnostics-1';
const ENABLED_WEIGHT=0;

function choose(n,k){
  if(!Number.isInteger(n)||!Number.isInteger(k)||n<0||k<0||k>n)return 0;
  k=Math.min(k,n-k);let out=1;
  for(let i=1;i<=k;i++)out=out*(n-k+i)/i;
  return Math.round(out);
}

// Colexicographic rank is a bijection from r-subsets of {1,...,n}
// to {0,...,C(n,r)-1}. Under the uniform lottery null the rank is uniform.
function combinationRank(ticket,n,r){
  const a=[...ticket].sort((x,y)=>x-y);
  if(a.length!==r||new Set(a).size!==r||a.some(x=>!Number.isInteger(x)||x<1||x>n))return null;
  let rank=0;for(let i=1;i<=r;i++)rank+=choose(a[i-1]-1,i);
  return rank;
}

function fairBit(ticket,n,r){
  const rank=combinationRank(ticket,n,r),total=choose(n,r);
  if(rank==null||!total)return null;
  // If C(n,r) is odd, discard exactly one rank so the retained parity classes
  // have equal cardinality. This preserves a calibrated 1/2-1/2 null.
  if(total%2===1&&rank===total-1)return null;
  return rank%2;
}

function bitsFromHistory(game,options={}){
  if(!window.PLATO_HISTORY)throw new Error('Era history is unavailable.');
  const h=PLATO_HISTORY.historyFor(game,options),bits=[];
  let skipped=0;
  for(const item of h.annotated){
    const bit=fairBit(item.row[2],item.era.n,item.era.r);
    if(bit==null)skipped++;else bits.push(bit);
  }
  return {bits,skipped,totalDraws:h.rows.length,eras:h.eraCounts};
}

function strategyFactor(q,bit){return bit?2*q:2*(1-q);}
function martingaleAudit(bits){
  const wealth={up:1,down:1,trend:1,reverse:1};
  let previous=null,maxCapital=1,lastCapital=1,maxAt=0;
  const trace=[];
  for(let i=0;i<bits.length;i++){
    const b=bits[i];
    wealth.up*=strategyFactor(.65,b);
    wealth.down*=strategyFactor(.35,b);
    if(previous==null){
      wealth.trend*=1;wealth.reverse*=1;
    }else{
      const qTrend=previous?0.65:0.35;
      const qReverse=previous?0.35:0.65;
      wealth.trend*=strategyFactor(qTrend,b);
      wealth.reverse*=strategyFactor(qReverse,b);
    }
    previous=b;
    lastCapital=(wealth.up+wealth.down+wealth.trend+wealth.reverse)/4;
    if(lastCapital>maxCapital){maxCapital=lastCapital;maxAt=i+1;}
    if((i+1)%100===0||i===bits.length-1)trace.push([i+1,lastCapital]);
  }
  const mlLevel=maxCapital>=2?Math.floor(Math.log2(maxCapital)):0;
  return {
    initialCapital:1,lastCapital,maxCapital,maxAt,
    mlStyleLevelCrossed:mlLevel,
    villeMeasureUpperBound:mlLevel?Math.pow(2,-mlLevel):1,
    strategies:wealth,trace
  };
}

function lz76PhraseCount(bits){
  if(!bits.length)return 0;
  const s=bits.join(''),seen=new Set();let i=0,count=0;
  while(i<s.length){
    let j=i+1;
    while(j<=s.length&&seen.has(s.slice(i,j)))j++;
    seen.add(s.slice(i,Math.min(j,s.length)));count++;i=Math.min(j,s.length);
  }
  return count;
}
function entropy(bits){
  if(!bits.length)return 0;const ones=bits.reduce((a,b)=>a+b,0),p=ones/bits.length;
  if(p===0||p===1)return 0;return -p*Math.log2(p)-(1-p)*Math.log2(1-p);
}
function normalTailApprox(z){
  // Abramowitz-Stegun erf approximation; diagnostic only.
  const x=Math.abs(z)/Math.SQRT2,t=1/(1+0.3275911*x);
  const a1=.254829592,a2=-.284496736,a3=1.421413741,a4=-1.453152027,a5=1.061405429;
  const erf=1-(((((a5*t+a4)*t+a3)*t+a2)*t+a1)*t)*Math.exp(-x*x);
  return Math.max(0,Math.min(1,1-erf));
}
function finiteStats(bits){
  const n=bits.length,ones=bits.reduce((a,b)=>a+b,0),zeros=n-ones;
  const z=n?(ones-n/2)/Math.sqrt(n/4):0;
  let runs=n?1:0;for(let i=1;i<n;i++)if(bits[i]!==bits[i-1])runs++;
  const phrases=lz76PhraseCount(bits);
  return {
    n,ones,zeros,onesRate:n?ones/n:0,entropyBitsPerSymbol:entropy(bits),runs,
    monobitZ:z,monobitTwoSidedPApprox:normalTailApprox(Math.abs(z)),
    lz76Phrases:phrases,lz76Normalized:n>1?phrases*Math.log2(n)/n:0
  };
}
function audit(game,options={}){
  const sequence=bitsFromHistory(game,options),martingale=martingaleAudit(sequence.bits),stats=finiteStats(sequence.bits);
  return {
    version:VERSION,enabledWeight:ENABLED_WEIGHT,
    interpretation:'Finite computable diagnostics only; not a decision procedure for Martin-Lof, Schnorr, or exact Kolmogorov randomness.',
    sequence:{length:sequence.bits.length,skipped:sequence.skipped,totalDraws:sequence.totalDraws,eras:sequence.eras},
    stats,martingale,
    theoremLinks:{
      mlTestBudget:'For the specific computable nonnegative martingale, crossing capital 2^k defines a finite-horizon event with measure at most 2^-k by Ville/Doob maximal inequality.',
      levinSchnorr:'Exact prefix-free K is uncomputable; LZ76 is stored only as a compression proxy.',
      schnorr:'No pass/fail claim is made from a finite sample.'
    }
  };
}
window.PLATO_V35_RANDOMNESS={VERSION,ENABLED_WEIGHT,choose,combinationRank,fairBit,bitsFromHistory,strategyFactor,martingaleAudit,lz76PhraseCount,finiteStats,audit};
})();
