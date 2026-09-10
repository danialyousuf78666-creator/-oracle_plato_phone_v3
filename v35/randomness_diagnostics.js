(function(){
'use strict';
const VERSION='3.5-randomness-diagnostics-2-log-capital';
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
  const logWealth={up:0,down:0,trend:0,reverse:0};
  let previous=null,maxLogCapital=0,lastLogCapital=0,maxAt=0;
  const trace=[];
  const maxLog=Math.log(Number.MAX_VALUE),minLog=Math.log(Number.MIN_VALUE);
  const finiteExp=x=>x>=maxLog?Number.MAX_VALUE:x<=minLog?Number.MIN_VALUE:Math.exp(x);
  const logMean=values=>{const top=Math.max(...values);return top+Math.log(values.reduce((s,x)=>s+Math.exp(x-top),0))-Math.log(values.length);};
  for(let i=0;i<bits.length;i++){
    const b=bits[i];if(b!==0&&b!==1)throw new Error('Randomness diagnostic requires binary observations.');
    logWealth.up+=Math.log(strategyFactor(.65,b));
    logWealth.down+=Math.log(strategyFactor(.35,b));
    if(previous!=null){
      const qTrend=previous?0.65:0.35;
      const qReverse=previous?0.35:0.65;
      logWealth.trend+=Math.log(strategyFactor(qTrend,b));
      logWealth.reverse+=Math.log(strategyFactor(qReverse,b));
    }
    previous=b;
    lastLogCapital=logMean(Object.values(logWealth));
    if(lastLogCapital>maxLogCapital){maxLogCapital=lastLogCapital;maxAt=i+1;}
    if((i+1)%100===0||i===bits.length-1)trace.push([i+1,finiteExp(lastLogCapital)]);
  }
  const mlLevel=Math.max(0,Math.floor(maxLogCapital/Math.LN2));
  return {
    initialCapital:1,lastCapital:finiteExp(lastLogCapital),maxCapital:finiteExp(maxLogCapital),maxAt,
    lastLogCapital,maxLogCapital,maxLog2Capital:maxLogCapital/Math.LN2,
    capitalDisplayClamped:lastLogCapital>maxLog||lastLogCapital<minLog||maxLogCapital>maxLog,
    mlStyleLevelCrossed:mlLevel,
    // The running maximum gives the sharper anytime bound 1/max(M), without
    // rounding capital down to a power of two. Preserve log values at extremes.
    villeMeasureUpperBound:Math.min(1,finiteExp(-maxLogCapital)),
    dyadicVilleMeasureUpperBound:Math.min(1,finiteExp(-mlLevel*Math.LN2)),
    strategies:Object.fromEntries(Object.entries(logWealth).map(([name,value])=>[name,finiteExp(value)])),logStrategies:logWealth,trace
  };
}

function lz76PhraseCount(bits){
  // Legacy API name: this is a dictionary-phrase proxy, not exact LZ76 or K.
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
    dictionaryPhrases:phrases,dictionaryNormalized:n>1?phrases*Math.log2(n)/n:0,
    compressionMethod:'dictionary-phrase proxy',
    lz76Phrases:phrases,lz76Normalized:n>1?phrases*Math.log2(n)/n:0
  };
}
function audit(game,options={}){
  const sequence=bitsFromHistory(game,options),martingale=martingaleAudit(sequence.bits),stats=finiteStats(sequence.bits);
  const gameCount=Object.keys(PLATO_HISTORY.ERAS).length;
  return {
    version:VERSION,enabledWeight:ENABLED_WEIGHT,
    interpretation:'Finite computable diagnostics only; not a decision procedure for Martin-Lof, Schnorr, or exact Kolmogorov randomness.',
    sequence:{length:sequence.bits.length,skipped:sequence.skipped,totalDraws:sequence.totalDraws,eras:sequence.eras},
    stats,martingale,
    simultaneousGames:gameCount,
    familywiseVilleUpperBound:Math.min(1,gameCount*martingale.villeMeasureUpperBound),
    assumptions:'Conditionally independent uniform draws within their declared eras; the bit transform and four betting strategies are fixed before confirmatory observations.',
    evidence:'Exploratory historical diagnostic. Confirmatory interpretation requires a frozen configuration and new prospective observations. The game adjustment covers only the declared games, not additional post-hoc method searches.',
    theoremLinks:{
      mlTestBudget:'For this fixed nonnegative martingale starting at 1, P(sup M >= a) <= 1/a. The running-maximum bound is adjusted across the declared games by the union bound.',
      levinSchnorr:'Exact prefix-free K is uncomputable; dictionary phrase count is only a compression proxy.',
      schnorr:'No pass/fail claim is made from a finite sample.'
    }
  };
}
window.PLATO_V35_RANDOMNESS={VERSION,ENABLED_WEIGHT,choose,combinationRank,fairBit,bitsFromHistory,strategyFactor,martingaleAudit,lz76PhraseCount,finiteStats,audit};
})();
