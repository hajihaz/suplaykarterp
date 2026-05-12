/* =========================================================================
   Suplaykart Staff — Workforce OS
   Service Worker (offline-capable shell + smart caching)
   -------------------------------------------------------------------------
   Strategy:
     • App shell (index.html + icons + manifest) → cache-first with
       background-revalidate, so the app boots instantly even offline.
     • Same-origin static assets (icons, splash, fonts) → stale-while-revalidate.
     • Cross-origin CDN assets (Leaflet, jsPDF, supabase-js, fonts) →
       stale-while-revalidate, capped 7-day max age.
     • Supabase REST + Realtime + Storage → never cached. Always live.
     • Map tiles (openstreetmap.org) → cache-first with 7-day expiry.
   Bump CACHE_VERSION to force a refresh after a deploy.
   ========================================================================= */

const CACHE_VERSION = 'sk-staff-v1.0.0';
const SHELL_CACHE   = `shell-${CACHE_VERSION}`;
const ASSETS_CACHE  = `assets-${CACHE_VERSION}`;
const TILES_CACHE   = `tiles-${CACHE_VERSION}`;

const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png',
  './icons/icon-maskable-192.png',
  './icons/icon-maskable-512.png',
];

/* ---------- install: pre-cache the shell ---------- */
self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(APP_SHELL).catch((e) => {
      console.warn('[sw] shell precache failed:', e.message);
    }))
  );
});

/* ---------- activate: clean up old caches ---------- */
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => {
      if (k !== SHELL_CACHE && k !== ASSETS_CACHE && k !== TILES_CACHE) {
        return caches.delete(k);
      }
    }));
    await self.clients.claim();
  })());
});

/* ---------- fetch routing ---------- */
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;

  /* Never cache anything Supabase. Always go straight to the network. */
  if (url.hostname.endsWith('.supabase.co') ||
      url.hostname.endsWith('.supabase.in')) {
    return; /* default fetch */
  }

  /* Map tiles → cache-first with 7-day TTL */
  if (url.hostname.endsWith('tile.openstreetmap.org')) {
    event.respondWith(cacheFirst(req, TILES_CACHE, 7 * 24 * 3600));
    return;
  }

  /* Navigation requests (HTML page loads) → network-first, fallback to cached shell */
  if (req.mode === 'navigate') {
    event.respondWith(networkFirst(req, SHELL_CACHE));
    return;
  }

  /* Same-origin static assets (icons, splash, the HTML itself) → SWR */
  if (sameOrigin) {
    event.respondWith(staleWhileRevalidate(req, SHELL_CACHE));
    return;
  }

  /* Trusted CDN assets (jsdelivr, unpkg, cloudflare, googleapis, gstatic) → SWR */
  if (
    url.hostname.endsWith('jsdelivr.net') ||
    url.hostname.endsWith('unpkg.com') ||
    url.hostname.endsWith('cloudflare.com') ||
    url.hostname.endsWith('cdnjs.cloudflare.com') ||
    url.hostname.endsWith('googleapis.com') ||
    url.hostname.endsWith('gstatic.com')
  ) {
    event.respondWith(staleWhileRevalidate(req, ASSETS_CACHE));
    return;
  }

  /* Default: try network, fall back to cache, fall back to a 504 */
  event.respondWith(networkFirst(req, ASSETS_CACHE));
});

/* ---------- listen for "skip waiting" from the page ---------- */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

/* ============================================================
   Caching strategies
   ============================================================ */

async function networkFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const fresh = await fetch(req);
    if (fresh && fresh.status < 400) cache.put(req, fresh.clone());
    return fresh;
  } catch (err) {
    const cached = await cache.match(req);
    if (cached) return cached;
    /* Final fallback for navigations: serve the cached shell */
    if (req.mode === 'navigate') {
      const shell = await cache.match('./index.html') || await cache.match('./');
      if (shell) return shell;
    }
    return new Response('Offline — no cached copy available.', {
      status: 504, statusText: 'Gateway Timeout',
      headers: { 'content-type': 'text/plain;charset=utf-8' },
    });
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  const fetchPromise = fetch(req).then((res) => {
    if (res && res.status < 400) cache.put(req, res.clone());
    return res;
  }).catch(() => cached);
  return cached || fetchPromise;
}

async function cacheFirst(req, cacheName, maxAgeSeconds) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  if (cached) {
    /* refresh in background if older than maxAge */
    const cachedDate = new Date(cached.headers.get('date') || 0).getTime();
    if (maxAgeSeconds && (Date.now() - cachedDate) > maxAgeSeconds * 1000) {
      fetch(req).then((res) => res && res.status < 400 && cache.put(req, res.clone())).catch(() => {});
    }
    return cached;
  }
  try {
    const fresh = await fetch(req);
    if (fresh && fresh.status < 400) cache.put(req, fresh.clone());
    return fresh;
  } catch (e) {
    return new Response('', { status: 504 });
  }
}
