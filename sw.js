const CACHE='oracle-plato-v35-live-1';
const ASSETS=['./v35/index.html','./v35/manifest.webmanifest','./v35/plato_v35_phone.js','./v35/prize_coverage.js','./index.html?legacy=1'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('oracle-plato-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  const u=new URL(e.request.url);if(u.origin!==location.origin)return;
  if(e.request.mode==='navigate'){
    if(u.searchParams.get('legacy')==='1'){
      e.respondWith(fetch(e.request,{cache:'no-store'}).catch(()=>caches.match('./index.html?legacy=1')));
      return;
    }
    if(u.pathname.includes('/v35/'))return;
    e.respondWith(fetch('./v35/index.html?v=live-1',{cache:'no-store'}).catch(()=>caches.match('./v35/index.html')));
    return;
  }
  e.respondWith(fetch(e.request,{cache:'no-store'}).catch(()=>caches.match(e.request)));
});
