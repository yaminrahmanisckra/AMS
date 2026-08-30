// Service Worker for Academic Management System PWA
const CACHE_NAME = 'ams-ku-v8';
const urlsToCache = [
  // Removed '/' - HTML pages should NEVER be cached globally
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/js/debug.js',
  '/static/js/attendance_offline.js',
  '/static/images/KU_logo_2.png'
];

importScripts('/static/js/attendance_offline.js');

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

// Install event - cache resources
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
      .catch((error) => {
        console.error('Cache installation failed:', error);
      })
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

// Background Sync: replay queued take-attendance POSTs when the network returns.
// Does not intercept live POSTs. iPhone Safari support is limited; page replay still runs.
self.addEventListener('sync', (event) => {
  if (event.tag !== 'ams-attendance-sync') {
    return;
  }
  event.waitUntil(
    (self.AMSOfflineSync || self.AMSAttendanceOffline)
      ? (self.AMSOfflineSync || self.AMSAttendanceOffline).replayQueue()
      : Promise.resolve()
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests (attendance POSTs are never intercepted)
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip non-HTTP/HTTPS requests (chrome-extension://, file://, etc.)
  if (!event.request.url.startsWith('http://') && !event.request.url.startsWith('https://')) {
    return;
  }

  // Skip API requests and dynamic content (including admission candidate pages)
  if (event.request.url.includes('/api/') || 
      event.request.url.includes('/download') ||
      event.request.url.includes('/admission-exam/') ||
      event.request.url.includes('.ics')) {
    return;
  }

  // Opt-in: attendance / assessment / exam-marks GET — network first, cache for offline reopen
  if (isOfflineEntryUrl(event.request.url)) {
    event.respondWith(
      fetch(event.request).then((response) => {
        if (response && response.ok) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME)
            .then((cache) => cache.put(event.request, responseToCache))
            .catch((error) => {
              console.debug('Take-attendance cache put failed (non-critical):', error);
            });
        }
        return response;
      }).catch(() => caches.match(event.request))
    );
    return;
  }

  // NEVER cache HTML pages (login, dashboard, etc.) - always fetch from network
  const isHTMLRequest = event.request.destination === 'document' || 
                        event.request.headers.get('accept')?.includes('text/html') ||
                        event.request.url.match(/\.(html|htm)$/i) ||
                        !event.request.url.match(/\.(css|js|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot|ico|json)$/i);
  
  if (isHTMLRequest) {
    // For HTML pages, always fetch from network, never cache
    event.respondWith(
      fetch(event.request).then((response) => {
        return response;
      }).catch(() => {
        // Only fallback to cache if network fails completely
        return caches.match(event.request);
      })
    );
    return;
  }

  // For static assets (CSS, JS, images), use cache-first strategy
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Return cached version or fetch from network
        return response || fetch(event.request).then((response) => {
          // Don't cache if not a valid response
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }

          // Clone the response
          const responseToCache = response.clone();

          // Only cache if URL is http/https (skip chrome-extension://, file://, etc.)
          let url;
          try {
            url = new URL(event.request.url);
          } catch (_) {
            url = null;
          }
          const isCacheableScheme = url && (url.protocol === 'http:' || url.protocol === 'https:');
          if (isCacheableScheme) {
            caches.open(CACHE_NAME)
              .then((cache) => cache.put(event.request, responseToCache))
              .catch((error) => {
                // Silently fail if caching fails (e.g. unsupported scheme in some contexts)
                console.debug('Cache put failed (non-critical):', error);
              });
          }

          return response;
        });
      })
      .catch(() => {
        // If both cache and network fail, return offline page if available
        if (event.request.destination === 'document') {
          return caches.match('/');
        }
      })
  );
});
