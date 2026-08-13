/* Offline-first service worker.
   Bump CACHE when shipping a new tax year or an engine change, or users
   will keep running last year's brackets from cache. */
const CACHE = "canpath-v6-2026";
const ASSETS = [
  "./", "./index.html", "./allocate.html", "./learn.html", "./manifest.webmanifest",
  "./icons/icon-192.png", "./icons/icon-512.png",
  "./icons/icon-512-maskable.png", "./icons/apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

/* Network-first for the app shell so a deploy reaches users promptly;
   cache-first for everything else. Fonts are optional -- the app is fully
   functional on system fonts if Google Fonts is unreachable. */
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const isShell = req.mode === "navigate" || /\/(index|allocate|learn)\.html$/.test(req.url);
  if (isShell) {
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req).then((r) => r || caches.match("./index.html")))
    );
  } else {
    /* Cache-first, but ACTUALLY CACHE what it fetches. The previous version
       fetched on a miss and threw the response away, so the Google Fonts CSS
       and the font files were re-requested on every load and were never
       available offline -- the app fell back to system fonts every time it
       lost the network, which for a terminal look built on IBM Plex Mono is
       a visible downgrade rather than a cosmetic one. */
    e.respondWith(caches.match(req).then((hit) => {
      if (hit) return hit;
      return fetch(req).then((res) => {
        // Opaque cross-origin responses (the fonts) are cacheable and worth it.
        if (req.url.startsWith("http") && (res.ok || res.type === "opaque")) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      }).catch(() => hit);
    }));
  }
});
