// Only an offline document is cached. API responses and the dashboard bundle
// always use the network, so updates never replace a page with unsaved forms.
const scope = self.registration.scope;
const prefix = `marzban-offline:${scope}:`;
const cacheName = `${prefix}${__PWA_OFFLINE_REVISION__}`;
const offlineUrl = new URL("__offline__", scope).href;
const offlineHtml = __PWA_OFFLINE_HTML__;

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(cacheName);
    await cache.put(offlineUrl, new Response(offlineHtml, {
      headers: { "Content-Type": "text/html; charset=utf-8" },
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((name) => name.startsWith(prefix) && name !== cacheName)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  const root = new URL(scope);
  if (
    request.method !== "GET" || request.mode !== "navigate" ||
    request.headers.has("Authorization") || url.origin !== root.origin ||
    ![root.pathname, `${root.pathname}index.html`].includes(url.pathname)
  ) return;

  event.respondWith((async () => {
    try {
      return await fetch(request);
    } catch {
      const cache = await caches.open(cacheName);
      return (await cache.match(offlineUrl)) ?? Response.error();
    }
  })());
});
