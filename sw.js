/* Offline-first service worker.
   Bump CACHE when shipping a new tax year or an engine change, or users
   will keep running last year's brackets from cache. */
const CACHE = "canpath-v5-2026";
const ASSETS = [
  "./", "./index.html", "./allocate.html", "./learn.html", "./manifest.webmanifest",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/apple-touch-icon.png",
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
    e.respondWith(caches.match(req).then((r) => r || fetch(req).catch(() => r)));
  }
});
