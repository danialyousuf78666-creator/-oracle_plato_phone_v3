// Retire the obsolete nested registration. The root owns the single app cache.
self.addEventListener('install',event=>event.waitUntil(self.skipWaiting()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{
  await self.registration.unregister();
  const root=new URL('../',self.location.href);
  for(const client of await self.clients.matchAll({type:'window',includeUncontrolled:true})){
    if(new URL(client.url).pathname.startsWith(new URL('./',self.location.href).pathname))await client.navigate(root.href);
  }
})()));
