/* IFPI Academy service worker — installability + offline slide reading.
 * Strategy:
 *  - Navigations: network-first, fallback to cached index.html shell.
 *  - Learn-related GET APIs (/api/courses, /api/learn, /api/organization,
 *    /api/learning-paths): network-first with cache fallback so recently
 *    viewed slides stay readable offline.
 *  - Static assets (hashed JS/CSS, images, fonts): stale-while-revalidate.
 */
const VERSION = 'v2'
const SHELL_CACHE = `ifpi-shell-${VERSION}`
const API_CACHE = `ifpi-api-${VERSION}`
const ASSET_CACHE = `ifpi-assets-${VERSION}`

const API_OFFLINE_PATTERNS = [
  '/api/courses', '/api/learn', '/api/organization', '/api/learning-paths',
  '/api/auth/me',
]

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(SHELL_CACHE).then((c) => c.add('/index.html')).catch(() => {})
  )
  self.skipWaiting()
})

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys()
    await Promise.all(keys
      .filter((k) => k.startsWith('ifpi-') && !k.endsWith(VERSION))
      .map((k) => caches.delete(k)))
    await self.clients.claim()
  })())
})

const isApi = (url) =>
  url.origin === self.location.origin && url.pathname.startsWith('/api/')

const isLearnApi = (url) =>
  url.origin === self.location.origin &&
  API_OFFLINE_PATTERNS.some((p) => url.pathname.startsWith(p))

const isStaticAsset = (url) =>
  url.origin === self.location.origin &&
  (url.pathname.startsWith('/static/') ||
   /\.(png|jpg|jpeg|webp|svg|ico|woff2?)$/.test(url.pathname))

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)

  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(req)
        const cache = await caches.open(SHELL_CACHE)
        cache.put('/index.html', fresh.clone())
        return fresh
      } catch {
        return (await caches.match('/index.html')) || Response.error()
      }
    })())
    return
  }

  if (isApi(url)) {
    const cacheable = isLearnApi(url)
    event.respondWith((async () => {
      const cache = await caches.open(API_CACHE)
      try {
        const fresh = await fetch(req)
        if (cacheable && fresh.ok) cache.put(req, fresh.clone())
        return fresh
      } catch {
        const cached = await cache.match(req)
        if (cached) return cached
        return new Response(JSON.stringify({ detail: 'offline' }), {
          status: 503, headers: { 'Content-Type': 'application/json' },
        })
      }
    })())
    return
  }

  if (isStaticAsset(url)) {
    event.respondWith((async () => {
      const cache = await caches.open(ASSET_CACHE)
      const cached = await cache.match(req)
      const network = fetch(req).then((res) => {
        if (res.ok) cache.put(req, res.clone())
        return res
      }).catch(() => cached)
      return cached || network
    })())
  }
})
