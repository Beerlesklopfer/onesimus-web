// SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
// SPDX-License-Identifier: MIT
//
// Onesimus Service Worker — network-first for pages/API, cache-first for static assets.

const CACHE   = 'onesimus-v{{ cache_version }}';
const STATIC  = '{{ static_url }}';

// ── Install: pre-cache critical static assets ─────────────────────────────
self.addEventListener('install', function (e) {
    e.waitUntil(
        caches.open(CACHE).then(function (cache) {
            return cache.addAll([
                STATIC + '/common/css/variables.css',
                STATIC + '/common/css/base.css',
                STATIC + '/common/css/layout.css',
                STATIC + '/common/css/components.css',
                STATIC + '/common/js/htmx.min.js',
                STATIC + '/common/js/common.js',
                STATIC + '/common/js/settings.js',
                STATIC + '/common/js/ws-manager.js',
                STATIC + '/common/icons/onesimus.svg',
                STATIC + '/common/icons/icon-192.png',
                STATIC + '/common/icons/icon-512.png',
            ]);
        })
    );
    self.skipWaiting();
});

// ── Activate: delete stale caches ─────────────────────────────────────────
self.addEventListener('activate', function (e) {
    e.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys.filter(function (k) { return k !== CACHE; })
                    .map(function (k) { return caches.delete(k); })
            );
        })
    );
    self.clients.claim();
});

// ── Fetch: cache-first for static assets, network-first for everything else
self.addEventListener('fetch', function (e) {
    // Only handle GET requests
    if (e.request.method !== 'GET') return;

    const url = e.request.url;

    // Cache-first for static assets (CSS, JS, fonts, images)
    if (url.startsWith(STATIC)) {
        e.respondWith(
            caches.match(e.request).then(function (cached) {
                if (cached) return cached;
                return fetch(e.request).then(function (response) {
                    if (response.ok) {
                        var clone = response.clone();
                        caches.open(CACHE).then(function (cache) {
                            cache.put(e.request, clone);
                        });
                    }
                    return response;
                });
            })
        );
        return;
    }

    // Network-first for HTML pages and API calls
    e.respondWith(
        fetch(e.request).catch(function () {
            return caches.match(e.request);
        })
    );
});
