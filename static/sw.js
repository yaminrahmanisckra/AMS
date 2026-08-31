// Service Worker for Academic Management System PWA
const CACHE_NAME = 'ams-ku-v9';
const urlsToCache = [
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/images/KU_logo_2.png'
];

function isOfflineEntryUrl(url) {
  try {
    const parsed = new URL(url);
    return (
      /\/class-management\/take_attendance\/\d+(\/roster\.json)?$/.test(parsed.pathname) ||
      /\/class-management\/assessment\/\d+$/.test(parsed.pathname) ||
      /\/exam-evaluation\/\d+\/marks$/.test(parsed.pathname)
    );
  } catch (_) {
    return false;
  }
}

function shouldIgnore(request) {
  if (request.method !== 'GET') {
    return true;
  }
  const url = request.url;
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    return true;
  }
  try {
    const parsed = new URL(url);
    if (parsed.pathname.indexOf('/socket.io') === 0) {
      return true;
    }
  } catch (_) {
    return true;
  }
  if (
    url.indexOf('/api/') !== -1 ||
    url.indexOf('/download') !== -1 ||
    url.indexOf('/admission-exam/') !== -1 ||
    url.indexOf('.ics') !== -1
  ) {
    return true;
  }
  return false;
}

function isSameOriginStatic(request) {
  try {
    const parsed = new URL(request.url);
    if (parsed.origin !== self.location.origin) {
      return false;
    }
    return /\.(css|js|png|jpg|jpeg|gif|svg|webp|woff|woff2|ttf|eot|ico)$/i.test(parsed.pathname);
  } catch (_) {
    return false;
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(urlsToCache))
      .catch((error) => {
        console.error('Cache installation failed:', error);
      })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Page watchdog already replays the offline queue. Keep this listener so
// browsers that support Background Sync still try, without importScripts.
self.addEventListener('sync', (event) => {
  if (event.tag !== 'ams-attendance-sync') {
    return;
  }
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      clients.forEach((client) => {
        client.postMessage({ type: 'ams-attendance-sync-please' });
      });
    })
  );
});

self.addEventListener('fetch', (event) => {
  if (shouldIgnore(event.request)) {
    return;
  }

  // Opt-in classroom pages: network first, cache only for offline reopen.
  if (isOfflineEntryUrl(event.request.url)) {
    event.respondWith(
      fetch(event.request).then((response) => {
        if (response && response.ok) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME)
            .then((cache) => cache.put(event.request, responseToCache))
            .catch(() => {});
        }
        return response;
      }).catch(() => caches.match(event.request))
    );
    return;
  }

  // Do not proxy HTML, Flask routes, or CDN. Browser default is faster and
  // avoids hanging navigations when the worker or Socket.IO is busy.
  if (!isSameOriginStatic(event.request)) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(event.request).then((response) => {
        if (!response || response.status !== 200 || response.type !== 'basic') {
          return response;
        }
        const responseToCache = response.clone();
        caches.open(CACHE_NAME)
          .then((cache) => cache.put(event.request, responseToCache))
          .catch(() => {});
        return response;
      });
    })
  );
});
