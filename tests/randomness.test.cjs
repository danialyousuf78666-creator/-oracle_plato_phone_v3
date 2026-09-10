const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const element=()=>({value:'sat',disabled:false,textContent:'',dataset:{},appendChild(){},addEventListener(){},reportValidity:()=>true});
function ctx(loadCoverage=false){
 const c=vm.createContext({console,Date,localStorage:{getItem:()=>null,setItem(){}},document:{getElementById:()=>element(),createElement:()=>element(),createDocumentFragment:()=>({appendChild(){}})}});c.window=c;
 const files=['history.js','era_history.js','randomness_diagnostics.js','plato_v35_phone.js','possibility_space.js'];if(loadCoverage)files.push('prize_coverage.js');
 for(const f of files)vm.runInContext(fs.readFileSync(path.join(root,'v35',f),'utf8'),c,{filename:f});return c;
}
function combinations(n,k){const out=[];function rec(start,a){if(a.length===k){out.push(a.slice());return;}for(let x=start;x<=n-(k-a.length)+1;x++){a.push(x);rec(x+1,a);a.pop();}}rec(1,[]);return out;}
test('combinatorial rank is bijective and fair-bit extraction is exactly balanced when C(n,r) is even',()=>{
 const c=ctx(),R=c.PLATO_V35_RANDOMNESS,sets=combinations(5,2),ranks=sets.map(x=>R.combinationRank(x,5,2));
 assert.deepEqual([...ranks].sort((a,b)=>a-b),Array.from({length:10},(_,i)=>i));
 const bits=sets.map(x=>R.fairBit(x,5,2));assert.equal(bits.filter(x=>x===0).length,5);assert.equal(bits.filter(x=>x===1).length,5);
});
test('odd combination spaces omit exactly one rank to retain a calibrated fair bit',()=>{
 const c=ctx(),R=c.PLATO_V35_RANDOMNESS,sets=combinations(6,2); // 15 combinations
 const bits=sets.map(x=>R.fairBit(x,6,2));assert.equal(bits.filter(x=>x===null).length,1);
 assert.equal(bits.filter(x=>x===0).length,7);assert.equal(bits.filter(x=>x===1).length,7);
});
test('each martingale update satisfies the binary fairness equation',()=>{
 const R=ctx().PLATO_V35_RANDOMNESS;for(const q of [.35,.65])assert.ok(Math.abs((R.strategyFactor(q,0)+R.strategyFactor(q,1))/2-1)<1e-12);
});
test('finite Ville bound holds by enumeration for the implemented mixture on short fair-bit sequences',()=>{
 const R=ctx().PLATO_V35_RANDOMNESS,N=10;
 for(let level=1;level<=3;level++){
  let hits=0;for(let mask=0;mask<2**N;mask++){const bits=Array.from({length:N},(_,i)=>(mask>>(N-1-i))&1);if(R.martingaleAudit(bits).maxCapital>=2**level)hits++;}
  assert.ok(hits/2**N<=2**(-level)+1e-12,`level ${level}: ${hits/2**N}`);
 }
});
test('all games produce finite diagnostics and diagnostics have zero production weight',()=>{
 const c=ctx();for(const game of Object.keys(c.PLATO_DATA.GAME_CFG)){const a=c.PLATO_V35_RANDOMNESS.audit(game);assert.equal(a.enabledWeight,0);assert.ok(a.sequence.length>100);assert.ok(Number.isFinite(a.stats.entropyBitsPerSymbol));assert.ok(Number.isFinite(a.martingale.maxCapital));}
});
test('loading randomness diagnostics does not change generated tickets',()=>{
 const withR=ctx(true),a=JSON.parse(JSON.stringify(withR.PLATO_V35_COVERAGE.portfolio('sat',20).tickets));
 delete withR.PLATO_V35_RANDOMNESS;const b=JSON.parse(JSON.stringify(withR.PLATO_V35_COVERAGE.portfolio('sat',20).tickets));assert.deepEqual(a,b);
});
