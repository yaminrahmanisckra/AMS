/**
 * CSRF helper: attaches the CSRF token (from the <meta name="csrf-token"> tag)
 * to same-origin, state-changing requests made via window.fetch and jQuery.ajax.
 *
 * Safe no-op if the meta tag is missing (e.g. CSRF enforcement not yet flipped on).
 * Loaded on every page so AJAX calls keep working once WTF_CSRF_CHECK_DEFAULT is true.
 */
(function () {
    'use strict';

    var UNSAFE_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'];

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : null;
    }

    function isSameOrigin(url) {
        try {
            var resolved = new URL(url, window.location.href);
            return resolved.origin === window.location.origin;
        } catch (e) {
            return true;
        }
    }

    window.getCsrfToken = getCsrfToken;

    if (window.fetch) {
        var originalFetch = window.fetch.bind(window);
        window.fetch = function (input, init) {
            var token = getCsrfToken();
            if (token) {
                var url = typeof input === 'string' ? input : (input && input.url) || '';
                var method = ((init && init.method) || (typeof input === 'object' && input.method) || 'GET').toUpperCase();
                if (UNSAFE_METHODS.indexOf(method) !== -1 && isSameOrigin(url)) {
                    init = init || {};
                    var headers = new Headers(init.headers || (typeof input === 'object' ? input.headers : undefined) || {});
                    if (!headers.has('X-CSRFToken')) {
                        headers.set('X-CSRFToken', token);
                    }
                    init.headers = headers;
                }
            }
            return originalFetch(input, init);
        };
    }

    if (window.jQuery) {
        window.jQuery.ajaxSetup({
            beforeSend: function (xhr, settings) {
                var token = getCsrfToken();
                if (!token) return;
                var method = (settings.type || settings.method || 'GET').toUpperCase();
                if (UNSAFE_METHODS.indexOf(method) === -1) return;
                if (settings.crossDomain) return;
                xhr.setRequestHeader('X-CSRFToken', token);
            }
        });
    }
})();
