(function(){
'use strict';
const VERSION='3.5-phone-distilled-4-patterns';
const STORE='ORACLE_PLATO_V35_PHONE_V2';
const MAP={pb:'powerball',sat:'saturday',oz:'oz',sfl:'set_for_life',ww:'windfall'};
const W={
 powerball:{m2_06_sum_band:.1587839135,m2_08_spacing_pattern:.1587839135,m2_05_parity_structure:.1270271308,m1_18_temporal_month:.1241394632,m1_14_sum_conditional:.1239009799,m1_06_recency:.1164415366,m1_13_parity_conditional:.0996939665,m2_14_regime_structure:.0912290958},
 saturday:{m1_08_gap_zscore:.2414698068,m1_07_gap_pressure:.2224693524,m2_10_recurrence_structure:.1800802680,m2_05_parity_structure:.1350602010,m1_13_parity_conditional:.0736830346,m1_12_range_density:.0506135748,m2_04_range_structure:.0506135748,m1_11_position_density:.0460101876},
 oz:{m1_12_range_density:.1633024018,m2_04_range_structure:.1633024018,m2_06_sum_band:.1621858339,m1_14_sum_conditional:.1413402732,m2_13_feature_interactions:.1117271255,m1_10_pair_transition:.0888840731,m1_02_short_frequency:.0846289453,m2_11_signature_similarity:.0846289453},
 set_for_life:{m2_01_structural_draw_templates:.2225580422,m2_12_normalized_number_density:.2225580422,m2_10_recurrence_structure:.1937564132,m2_05_parity_structure:.1073515262,m1_05_exponential_frequency:.0904092089,m2_07_adjacency_structure:.0785498972,m2_09_position_transition:.0497482682,m1_13_parity_conditional:.0350686019},
 windfall:{m1_05_exponential_frequency:.1841527353,m1_03_medium_frequency:.1311399261,m1_02_short_frequency:.1252955115,m1_17_transition:.1152018064,m1_01_global_frequency:.1110525052,m1_04_long_frequency:.1110525052,m1_09_pair_association:.1110525052,m2_02_pair_graph:.1110525052}
};
const clamp=x=>Math.max(0,Math.min(1,x));
const mean=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const sd=a=>{if(a.length<2)return 0;const m=mean(a);return Math.sqrt(a.reduce((s,x)=>s+(x-m)*(x-m),0)/(a.length-1))};
function normObj(o,n){const vals=[];for(let i=1;i<=n;i++)vals.push(o[i]||0);const lo=Math.min(...vals),hi=Math.max(...vals),d=hi-lo||1,r={};for(let i=1;i<=n;i++)r[i]=clamp(((o[i]||0)-lo)/d);return r}
function countNums(rows,n,decay){const o={};for(let i=1;i<=n;i++)o[i]=0;const L=rows.length;rows.forEach((r,idx)=>{const w=decay?Math.pow(.5,(L-1-idx)/decay):1;r[2].forEach(x=>{if(x<=n)o[x]+=w})});return normObj(o,n)}
function gaps(rows,n){const occ=Array.from({length:n+1},()=>[]);rows.forEach((r,i)=>r[2].forEach(x=>{if(x<=n)occ[x].push(i)}));const pressure={},z={};for(let x=1;x<=n;x++){const a=occ[x],cur=a.length?rows.length-1-a[a.length-1]:rows.length,gs=[];for(let j=1;j<a.length;j++)gs.push(a[j]-a[j-1]);const m=mean(gs)||rows.length/Math.max(1,a.length),s=sd(gs)||Math.max(1,m/2);pressure[x]=cur/(m+1e-9);z[x]=(cur-m)/s}return {pressure:normObj(pressure,n),z:normObj(z,n)}}
function pairMatrix(rows,n){const p=Array.from({length:n+1},()=>new Float64Array(n+1));rows.forEach((r,idx)=>{const w=Math.pow(.5,(rows.length-1-idx)/120),a=r[2].filter(x=>x<=n);for(let i=0;i<a.length;i++)for(let j=i+1;j<a.length;j++){p[a[i]][a[j]]+=w;p[a[j]][a[i]]+=w}});return p}
function parityScore(rows,n){const oddCounts=rows.map(r=>r[2].filter(x=>x%2).length),target=Math.round(mean(oddCounts)),r=rows[0]?.[2].length||6,oddPref=target/r,o={};for(let x=1;x<=n;x++)o[x]=x%2?oddPref:1-oddPref;return normObj(o,n)}
function rangeScore(rows,n){const bins=5,cnt=Array(bins).fill(0);rows.forEach(r=>r[2].forEach(x=>cnt[Math.min(bins-1,Math.floor((x-1)*bins/n))]++));const m=Math.max(...cnt,1),o={};for(let x=1;x<=n;x++)o[x]=cnt[Math.min(bins-1,Math.floor((x-1)*bins/n))]/m;return o}
function positionScore(rows,n){const o={};for(let x=1;x<=n;x++)o[x]=0;rows.forEach(r=>{const a=r[2].filter(x=>x<=n).slice().sort((a,b)=>a-b);a.forEach((x,j)=>{const expected=(j+.5)*n/a.length;o[x]+=1/(1+Math.abs(x-expected))})});return normObj(o,n)}
function adjacencyScore(rows,n){const o={};for(let x=1;x<=n;x++)o[x]=0;rows.forEach((r,idx)=>{const w=Math.pow(.5,(rows.length-1-idx)/100),a=r[2].filter(x=>x<=n).slice().sort((a,b)=>a-b);for(let i=1;i<a.length;i++)if(a[i]-a[i-1]<=2){o[a[i]]+=w;o[a[i-1]]+=w}});return normObj(o,n)}
function sumBand(rows,n){const recent=rows,sums=recent.map(r=>r[2].reduce((a,b)=>a+b,0)),m=mean(sums),s=sd(sums)||1,o={};for(let x=1;x<=n;x++)o[x]=0;recent.forEach(r=>{const z=Math.abs(r[2].reduce((a,b)=>a+b,0)-m)/s,w=Math.exp(-z*z/2);r[2].forEach(x=>{if(x<=n)o[x]+=w})});return normObj(o,n)}
function monthScore(rows,n){const last=rows[rows.length-1],month=last?new Date(last[1]).getMonth():new Date().getMonth(),o={};for(let x=1;x<=n;x++)o[x]=0;rows.forEach(r=>{if(new Date(r[1]).getMonth()===month)r[2].forEach(x=>{if(x<=n)o[x]++})});return normObj(o,n)}
function pairScores(rows,n){const p=pairMatrix(rows,n),latest=rows[rows.length-1]?.[2].filter(x=>x<=n)||[],assoc={},graph={},trans={};for(let x=1;x<=n;x++){graph[x]=0;assoc[x]=0;trans[x]=0;for(let y=1;y<=n;y++)graph[x]+=p[x][y];latest.forEach(y=>assoc[x]+=p[x][y])}for(let i=1;i<rows.length;i++){const prev=rows[i-1][2].filter(x=>x<=n),cur=new Set(rows[i][2].filter(x=>x<=n));for(let x=1;x<=n;x++)if(cur.has(x))latest.forEach(y=>{if(prev.includes(y))trans[x]++})}return {assoc:normObj(assoc,n),graph:normObj(graph,n),trans:normObj(trans,n)}}
function recurrence(rows,n){const o={},tot={},den={};for(let x=1;x<=n;x++)o[x]=0,tot[x]=0,den[x]=0;for(let i=1;i<rows.length;i++){const a=new Set(rows[i-1][2]),b=new Set(rows[i][2]);for(let x=1;x<=n;x++)if(a.has(x)){den[x]++;if(b.has(x))tot[x]++}}for(let x=1;x<=n;x++)o[x]=den[x]?tot[x]/den[x]:0;return normObj(o,n)}
function signature(rows,n){const last=rows[rows.length-1],sig=r=>{const a=r[2].filter(x=>x<=n),sum=a.reduce((s,x)=>s+x,0),odd=a.filter(x=>x%2).length,lo=a.filter(x=>x<=n/3).length;return [Math.round(sum/(n*.25)),odd,lo]},target=sig(last),o={};for(let x=1;x<=n;x++)o[x]=0;rows.slice(0,-1).forEach(r=>{const q=sig(r),dist=Math.abs(q[0]-target[0])+Math.abs(q[1]-target[1])+Math.abs(q[2]-target[2]),w=1/(1+dist);r[2].forEach(x=>{if(x<=n)o[x]+=w})});return normObj(o,n)}
function featureSet(rows,n){const short=countNums(rows.slice(-40),n),medium=countNums(rows.slice(-120),n),long=countNums(rows.slice(-300),n),global=countNums(rows,n),expo=countNums(rows,n,80),g=gaps(rows,n),pair=pairScores(rows,n),par=parityScore(rows,n),range=rangeScore(rows,n),pos=positionScore(rows,n),adj=adjacencyScore(rows,n),sum=sumBand(rows,n),month=monthScore(rows,n),rec=recurrence(rows,n),sig=signature(rows,n),recent=countNums(rows.slice(-40),n),older=countNums(rows.slice(-200,-40),n),reg={};for(let x=1;x<=n;x++)reg[x]=clamp(.65*recent[x]+.35*older[x]-.25*Math.abs(recent[x]-older[x]));return {short,medium,long,global,expo,g,pair,par,range,pos,adj,sum,month,rec,sig,reg:normObj(reg,n)}}
function methodScore(id,x,f,rows){const s=f.structural;switch(id){case'm1_01_global_frequency':return f.global[x];case'm1_02_short_frequency':return f.short[x];case'm1_03_medium_frequency':return f.medium[x];case'm1_04_long_frequency':return f.long[x];case'm1_05_exponential_frequency':return f.expo[x];case'm1_06_recency':{let since=rows.length;for(let i=rows.length-1;i>=0;i--)if(rows[i][2].includes(x)){since=rows.length-1-i;break}return Math.exp(-since/12)}case'm1_07_gap_pressure':return f.g.pressure[x];case'm1_08_gap_zscore':return f.g.z[x];case'm1_09_pair_association':return f.pair.assoc[x];case'm1_10_pair_transition':return f.pair.trans[x];case'm1_11_position_density':return f.pos[x];case'm1_12_range_density':return f.range[x];case'm1_13_parity_conditional':return f.par[x];case'm1_14_sum_conditional':return f.sum[x];case'm1_17_transition':return clamp(.55*f.pair.trans[x]+.45*f.rec[x]);case'm1_18_temporal_month':return f.month[x];case'm2_01_structural_draw_templates':return clamp(.45*s.sig[x]+.3*s.sum[x]+.25*s.par[x]);case'm2_02_pair_graph':return f.pair.graph[x];case'm2_04_range_structure':return s.range[x];case'm2_05_parity_structure':return s.par[x];case'm2_06_sum_band':return s.sum[x];case'm2_07_adjacency_structure':return s.adj[x];case'm2_08_spacing_pattern':return clamp(.6*s.adj[x]+.4*s.pos[x]);case'm2_09_position_transition':return clamp(.55*s.pos[x]+.45*f.pair.trans[x]);case'm2_10_recurrence_structure':return f.rec[x];case'm2_11_signature_similarity':return s.sig[x];case'm2_12_normalized_number_density':return clamp(.5*s.density[x]+.5*s.range[x]);case'm2_13_feature_interactions':return Math.sqrt(Math.max(0,f.short[x]*f.g.pressure[x]*f.pair.trans[x]));case'm2_14_regime_structure':return f.reg[x];default:return 0}}
function rank(game,options={}){
 const history=PLATO_HISTORY.historyFor(game,options),cfg=history.target,rows=history.compatible,key=MAP[game],weights=W[key];
 if(!weights)throw new Error('Unsupported game');if(rows.length<60)throw new Error('Not enough compatible-era history');
 const f=featureSet(rows,cfg.n);f.structural=PLATO_HISTORY.structuralFeatures(history.annotated,cfg.n,cfg.r);
 const out=[];for(let x=1;x<=cfg.n;x++){let score=0;for(const [id,w] of Object.entries(weights))score+=w*methodScore(id,x,f,rows);out.push({number:x,score});}
 out.sort((a,b)=>b.score-a.score||a.number-b.number);
 return {rows:history.rows,compatibleRows:rows,weights,out,history:{total:history.rows.length,raw:rows.length,structural:f.structural.draws,eras:history.eraCounts,target:cfg}};
}
// Descriptive pattern discovery. Counts are learned separately for each rule era;
// common/uncommon mean most/least observed, never a prediction of the next draw.
const PATTERN_LABELS={frequency:'Numbers',recency:'Recent numbers (40 draws)',gaps:'Appearance gaps',pairs:'Pairs',triples:'Triples',position:'Sorted positions',ranges:'Low/middle/high split',parity:'Odd/even split',sum:'TSUM',digital_root:'Set DRoot',adjacency:'Adjacent numbers',transition:'Repeated numbers',temporal:'Month and DRoot',structural:'Set span',pattern_signatures:'Set patterns',feature_interactions:'TSUM, DRoot and parity',regimes:'TSUM movement'};
function digitalRoot(value){
 if(!Number.isSafeInteger(value)||value<0)throw new Error('Digital root needs a non-negative whole number.');
 return value===0?0:1+(value-1)%9;
}
function describeSet(numbers,n){
 if(!Array.isArray(numbers)||!numbers.length||numbers.some(x=>!Number.isSafeInteger(x)||x<1||x>n)||new Set(numbers).size!==numbers.length)throw new Error('Invalid number set.');
 const ordered=[...numbers].sort((a,b)=>a-b),tsum=ordered.reduce((s,x)=>s+x,0),odd=ordered.filter(x=>x%2).length;
 const ranges=[0,0,0],spacing=[];let adjacentPairs=0,run=1,longestRun=1;
 ordered.forEach((x,i)=>{ranges[Math.min(2,Math.floor((x-1)*3/n))]++;if(i){const gap=x-ordered[i-1];spacing.push(gap);if(gap===1){adjacentPairs++;run++;}else run=1;longestRun=Math.max(longestRun,run);}});
 return {numbers:[...numbers],tsum,setDigitalRoot:digitalRoot(tsum),individualDigitalRoots:numbers.map(number=>({number,droot:digitalRoot(number)})),odd,even:ordered.length-odd,ranges,spacing,span:ordered.at(-1)-ordered[0],adjacentPairs,longestRun};
}
function setPatterns(metrics,previous,date){
 const parity=`${metrics.odd} odd / ${metrics.even} even`,ranges=metrics.ranges.join('/'),droot=String(metrics.setDigitalRoot);
 const keys={ranges,parity,sum:String(metrics.tsum),digital_root:droot,adjacency:`${metrics.adjacentPairs} adjacent pairs; run ${metrics.longestRun}`,structural:String(metrics.span),pattern_signatures:`${parity}; ${ranges}; DRoot ${droot}`,feature_interactions:`${metrics.tsum}; DRoot ${droot}; ${parity}`};
 if(date)keys.temporal=`month ${date.slice(5,7)}; DRoot ${droot}`;
 if(previous){keys.transition=String(metrics.numbers.filter(x=>previous.numbers.includes(x)).length);keys.regimes=metrics.tsum>previous.tsum?'rising':metrics.tsum<previous.tsum?'falling':'unchanged';}
 return keys;
}
function patternSummary(counts){
 const entries=Object.entries(counts).map(([pattern,count])=>({pattern,count})).sort((a,b)=>b.count-a.count||a.pattern.localeCompare(b.pattern));
 const maximum=entries[0]?.count||0,minimum=entries.at(-1)?.count||0,distinct=maximum>minimum;
 return {counts,maximum,minimum,common:distinct?entries.filter(x=>x.count===maximum).slice(0,3):[],uncommon:distinct?entries.filter(x=>x.count===minimum).slice(0,3):[],tied:entries.length>0&&!distinct};
}
function analysePatterns(game,options={}){
 const history=options.history||PLATO_HISTORY.historyFor(game,options),buckets=new Map();
 for(const item of history.annotated){const id=item.era.start;if(!buckets.has(id))buckets.set(id,{era:item.era,rows:[]});buckets.get(id).rows.push(item.row);}
 const eras={};
 for(const [start,{era,rows}] of buckets){
  const counts=Object.fromEntries(Object.keys(PATTERN_LABELS).map(key=>[key,Object.create(null)])),lastSeen=new Map(),sets=[];
  const bump=(group,key)=>{counts[group][key]=(counts[group][key]||0)+1;};
  rows.forEach((row,index)=>{
   const metrics=describeSet(row[2],era.n),ordered=[...row[2]].sort((a,b)=>a-b),keys=setPatterns(metrics,sets.at(-1),row[1]);
   for(const [group,key] of Object.entries(keys))bump(group,key);
   ordered.forEach((number,position)=>{
    bump('frequency',String(number));if(index>=rows.length-40)bump('recency',String(number));
    bump('position',`${position+1}: ${number}`);
    if(lastSeen.has(number))bump('gaps',`${number}: ${index-lastSeen.get(number)-1} skipped draws`);
    lastSeen.set(number,index);
    for(let j=position+1;j<ordered.length;j++){
     bump('pairs',`${number} ${ordered[j]}`);
     for(let k=j+1;k<ordered.length;k++)bump('triples',`${number} ${ordered[j]} ${ordered[k]}`);
    }
   });
   sets.push({draw:row[0],date:row[1],...metrics});
  });
  eras[start]={era,drawCount:rows.length,sets,groups:Object.fromEntries(Object.entries(counts).map(([key,value])=>[key,{label:PATTERN_LABELS[key],...patternSummary(value)}]))};
 }
 const current=eras[history.target.start]||{era:history.target,drawCount:0,sets:[],groups:{}};
 return {game,totalDraws:history.rows.length,eraCount:buckets.size,eras,current};
}
function classifySet(numbers,analysis){
 const current=analysis.current,metrics=describeSet(numbers,current.era.n),keys=setPatterns(metrics,current.sets.at(-1)),behaviour={};
 for(const [group,key] of Object.entries(keys)){
  const known=current.groups[group],count=known?.counts[key]||0;
  behaviour[group]={pattern:key,count,status:!known||!current.drawCount?'no history':!count?'not observed':known.tied?'tied':count===known.maximum?'common':count===known.minimum?'uncommon':'observed'};
 }
 return {...metrics,behaviour};
}
function chooseK(game){const cfg=GAME_CFG[game];return Math.max(cfg.r+5,Math.min(18,Math.round(cfg.n/3)))}
function makePortfolio(game,count){const cfg=GAME_CFG[game],r=rank(game),k=chooseK(game),pool=r.out.slice(0,k),tickets=[],seen=new Set(),used={};pool.forEach(x=>used[x.number]=0);const totalSlots=count*cfg.r;const raw=pool.map(x=>Math.max(.05,x.score));const z=raw.reduce((a,b)=>a+b,0)||1;const target={};pool.forEach((x,i)=>target[x.number]=totalSlots*raw[i]/z);
 for(let t=0;t<count;t++){
   let best=null,bestVal=-1e9;
   for(let attempt=0;attempt<Math.max(24,k*2);attempt++){
     const chosen=[];
     while(chosen.length<cfg.r){
       let pick=null,pickVal=-1e9;
       for(let i=0;i<pool.length;i++){
         const x=pool[i].number;if(chosen.includes(x))continue;
         const deficit=target[x]-used[x];
         let pairPenalty=0;for(const y of chosen){let together=0;for(const q of tickets)if(q.includes(x)&&q.includes(y))together++;pairPenalty+=together}
         const jitter=((t+1)*37+(attempt+1)*17+(i+1)*13)%101/1000;
         const v=deficit-0.35*pairPenalty+0.12*(pool.length-i)/pool.length+jitter;
         if(v>pickVal){pickVal=v;pick=x}
       }
       if(pick==null)break;chosen.push(pick)
     }
     chosen.sort((a,b)=>a-b);const key=chosen.join('-');if(chosen.length!==cfg.r||seen.has(key))continue;
     let overlap=0;for(const q of tickets){let c=0;for(const x of chosen)if(q.includes(x))c++;overlap+=c*c}
     const score=chosen.reduce((s,x)=>s+(target[x]-used[x]),0)-.15*overlap;
     if(score>bestVal){bestVal=score;best=chosen}
   }
   if(!best){
     best=pool.slice((t*cfg.r)%pool.length).concat(pool).slice(0,cfg.r).map(x=>x.number).sort((a,b)=>a-b);
   }
   const key=best.join('-');if(seen.has(key))continue;seen.add(key);tickets.push(best);best.forEach(x=>used[x]++)
 }
 return {rank:r,k,pool:pool.map(x=>x.number),tickets};
}
window.PLATO_V35={VERSION,rank,chooseK,makePortfolio,weights:W,featureSet,methodScore,digitalRoot,describeSet,analysePatterns,classifySet};
})();
