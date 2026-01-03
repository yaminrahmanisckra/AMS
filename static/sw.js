// Service Worker for Academic Management System PWA
const CACHE_NAME = 'ams-ku-v2'; // Updated version to clear old cache
const urlsToCache = [
  // Removed '/' - HTML pages should NEVER be cached
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/js/debug.js',
  '/static/images/KU_logo_2.png'
];

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

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip API requests and dynamic content
  if (event.request.url.includes('/api/') || 
      event.request.url.includes('/download') ||
      event.request.url.includes('.ics')) {
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

          caches.open(CACHE_NAME)
            .then((cache) => {
              cache.put(event.request, responseToCache);
            });

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
