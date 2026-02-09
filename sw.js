// Snake Measurer Service Worker
// Cache-first strategy for WASM/JS assets, network-first for HTML
// Auto-updates when new version is deployed

var CACHE_VERSION = 'v3-auto-update';
var CACHE_NAME = 'snake-measurer-' + CACHE_VERSION;

// Assets cached on install (shell)
var SHELL_ASSETS = [
    './',
    './index.html',
    './styles.css',
    './composeApp.js',
];

// Patterns for cache-first strategy (large immutable assets)
function isCacheFirstAsset(url) {
    var path = url.pathname;
    // Content-hashed WASM and JS chunks are immutable
    return path.endsWith('.wasm')
        || (path.endsWith('.js') && /[a-f0-9]{10,}/.test(path))
        || path.endsWith('.mjs');
}

// Patterns for stale-while-revalidate (app shell)
function isAppShellAsset(url) {
    var path = url.pathname;
    return path.endsWith('.css')
        || path.endsWith('.html')
        || path === '/'
        || path.endsWith('/composeApp.js');
}

// Firebase CDN — network-first (external, may update)
function isFirebaseCDN(url) {
    return url.hostname === 'www.gstatic.com';
}

// Install: pre-cache app shell
self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll(SHELL_ASSETS);
        })
    );
    // Activate immediately, don't wait for old tabs to close
    self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(function(names) {
            return Promise.all(
                names
                    .filter(function(name) { return name.startsWith('snake-measurer-') && name !== CACHE_NAME; })
                    .map(function(name) { return caches.delete(name); })
            );
        })
    );
    // Take control of all open tabs immediately
    self.clients.claim();
});

// Fetch: strategy depends on resource type
self.addEventListener('fetch', function(event) {
    var url = new URL(event.request.url);

    // Only handle GET requests
    if (event.request.method !== 'GET') return;

    // Skip non-http(s) requests
    if (!url.protocol.startsWith('http')) return;

    // Force HTTPS for same-origin requests (production only)
    if (url.origin === self.location.origin && url.protocol === 'http:' && self.location.hostname !== 'localhost') {
        url.protocol = 'https:';
        event.respondWith(fetch(url.toString()));
        return;
    }

    // 1. Content-hashed assets (.wasm, chunked .js) → cache-first
    //    These are immutable — once cached, never re-fetch
    if (isCacheFirstAsset(url)) {
        event.respondWith(
            caches.match(event.request).then(function(cached) {
                if (cached) return cached;
                return fetch(event.request).then(function(response) {
                    if (response.ok && response.type !== 'opaque') {
                        var clone = response.clone();
                        caches.open(CACHE_NAME).then(function(cache) {
                            cache.put(event.request, clone).catch(function(err) {
                                console.warn('Cache put failed:', event.request.url, err);
                            });
                        });
                    }
                    return response;
                });
            })
        );
        return;
    }

    // 2. App shell (HTML, CSS, composeApp.js) → stale-while-revalidate
    //    Serve from cache immediately, update cache in background
    if (isAppShellAsset(url)) {
        event.respondWith(
            caches.match(event.request).then(function(cached) {
                var fetchPromise = fetch(event.request).then(function(response) {
                    if (response.ok && response.type !== 'opaque') {
                        var clone = response.clone();
                        caches.open(CACHE_NAME).then(function(cache) {
                            cache.put(event.request, clone).catch(function(err) {
                                console.warn('Cache put failed:', event.request.url, err);
                            });
                        });
                    }
                    return response;
                }).catch(function() {
                    // Offline — cached version is our only option
                    return cached;
                });

                // Return cached immediately if available, otherwise wait for network
                return cached || fetchPromise;
            })
        );
        return;
    }

    // 3. Firebase CDN → network-first with cache fallback
    if (isFirebaseCDN(url)) {
        event.respondWith(
            fetch(event.request).then(function(response) {
                if (response.ok && response.type !== 'opaque') {
                    var clone = response.clone();
                    caches.open(CACHE_NAME).then(function(cache) {
                        cache.put(event.request, clone).catch(function(err) {
                            console.warn('Cache put failed:', event.request.url, err);
                        });
                    });
                }
                return response;
            }).catch(function() {
                return caches.match(event.request);
            })
        );
        return;
    }

    // 4. Everything else (compose resources, etc.) → network-first with cache
    event.respondWith(
        fetch(event.request).then(function(response) {
            if (response.ok && response.type !== 'opaque' && url.origin === self.location.origin) {
                var clone = response.clone();
                caches.open(CACHE_NAME).then(function(cache) {
                    cache.put(event.request, clone).catch(function(err) {
                        console.warn('Cache put failed:', event.request.url, err);
                    });
                });
            }
            return response;
        }).catch(function() {
            return caches.match(event.request);
        })
    );
});
