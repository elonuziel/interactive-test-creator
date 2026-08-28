const CACHE_NAME = 'quiz-builder-pwa-v2.1.0';

const PRECACHE_ASSETS = [
    './',
    'index.html',
    'quiz_player.html',
    'style.css',
    'generator.js',
    'quiz-core.js',
    'quiz-export.js',
    'app.js',
    'manifest.webmanifest',
    'favicon.svg',
    'icons/icon-192.png',
    'icons/icon-512.png',
    'icons/maskable-192.png',
    'icons/maskable-512.png',
    'icons/icon.svg',
    'js/progress-controller.js',
    'js/gemini-service.js',
    'js/pdf-service.js',
    'js/ocr-tesseract.js',
    'js/question-parser.js',
    'js/cropper-modal.js',
    'js/editor-ui.js',
    'js/export-service.js'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(PRECACHE_ASSETS);
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Only handle GET requests and http/https schemes
    if (event.request.method !== 'GET' || !url.protocol.startsWith('http')) {
        return;
    }

    // Skip caching external API calls (e.g. Google Generative AI / Gemini endpoints)
    if (url.hostname.includes('googleapis.com') || url.hostname.includes('freebuff.com')) {
        return;
    }

    // Network-first with cache fallback for HTML pages, cache-first for static assets
    if (event.request.mode === 'navigate' || event.request.destination === 'document') {
        event.respondWith(
            fetch(event.request)
                .then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseClone = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return networkResponse;
                })
                .catch(() => caches.match(event.request).then((cached) => cached || caches.match('index.html')))
        );
        return;
    }

    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
                // Fetch in background to update cache for next time
                fetch(event.request)
                    .then((networkResponse) => {
                        if (networkResponse && networkResponse.status === 200) {
                            caches.open(CACHE_NAME).then((cache) => {
                                cache.put(event.request, networkResponse);
                            });
                        }
                    })
                    .catch(() => {});
                return cachedResponse;
            }

            return fetch(event.request).then((networkResponse) => {
                if (networkResponse && networkResponse.status === 200) {
                    const responseClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return networkResponse;
            });
        })
    );
});

