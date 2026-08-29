/**
 * CSRF helper: attaches the CSRF token (from <meta name="csrf-token">) to
 * same-origin state-changing requests.
 *
 * Covers: HTML forms (button submit, form.submit(), dynamically added forms),
 * window.fetch, jQuery.ajax, and XMLHttpRequest.
 *
 * Safe no-op if the meta tag is missing. Extra tokens are ignored while
 * CSRF_ENABLED is false; they keep working after enforcement is turned on.
 *
 * Load after jQuery when jQuery is used on the page.
 */
(function () {
    'use strict';

    var UNSAFE_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'];

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : null;
    }

    function isUnsafeMethod(method) {
        return UNSAFE_METHODS.indexOf(String(method || 'GET').toUpperCase()) !== -1;
    }

    function isSameOrigin(url) {
        try {
            var resolved = new URL(url, window.location.href);
            return resolved.origin === window.location.origin;
        } catch (e) {
            return true;
        }
    }

    function formMethod(form) {
        var attr = form.getAttribute('method');
        if (attr) {
            return attr.toUpperCase();
        }
        return String(form.method || 'GET').toUpperCase();
    }

    function injectTokenIntoForm(form) {
        if (!form || form.nodeName !== 'FORM') {
            return;
        }
        if (!isUnsafeMethod(formMethod(form))) {
            return;
        }
        var token = getCsrfToken();
        if (!token) {
            return;
        }
        var existing = form.querySelector('input[name="csrf_token"]');
        if (existing) {
            existing.value = token;
            return;
        }
        var input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrf_token';
        input.value = token;
        form.appendChild(input);
    }

    function injectAllForms(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        var forms = root.querySelectorAll('form');
        for (var i = 0; i < forms.length; i++) {
            injectTokenIntoForm(forms[i]);
        }
    }

    window.getCsrfToken = getCsrfToken;

    document.addEventListener('submit', function (e) {
        if (e.target && e.target.nodeName === 'FORM') {
            injectTokenIntoForm(e.target);
        }
    }, true);

    if (typeof HTMLFormElement !== 'undefined' && HTMLFormElement.prototype.submit) {
        var originalFormSubmit = HTMLFormElement.prototype.submit;
        HTMLFormElement.prototype.submit = function () {
            injectTokenIntoForm(this);
            return originalFormSubmit.call(this);
        };
    }

    function scanForms() {
        injectAllForms(document);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scanForms);
    } else {
        scanForms();
    }

    if (window.MutationObserver && document.documentElement) {
        var observer = new MutationObserver(function (mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var nodes = mutations[i].addedNodes;
                for (var j = 0; j < nodes.length; j++) {
                    var node = nodes[j];
                    if (!node || node.nodeType !== 1) {
                        continue;
                    }
                    if (node.nodeName === 'FORM') {
                        injectTokenIntoForm(node);
                    } else if (node.querySelectorAll) {
                        injectAllForms(node);
                    }
                }
            }
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });
    }

    if (window.fetch) {
        var originalFetch = window.fetch.bind(window);
        window.fetch = function (input, init) {
            var token = getCsrfToken();
            if (token) {
                var url = typeof input === 'string' ? input : (input && input.url) || '';
                var method = ((init && init.method) || (typeof input === 'object' && input.method) || 'GET').toUpperCase();
                if (isUnsafeMethod(method) && isSameOrigin(url)) {
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

    function setupJqueryCsrf() {
        if (!window.jQuery || window.jQuery.__amsCsrfBound) {
            return;
        }
        window.jQuery.ajaxSetup({
            beforeSend: function (xhr, settings) {
                var token = getCsrfToken();
                if (!token) {
                    return;
                }
                var method = (settings.type || settings.method || 'GET').toUpperCase();
                if (!isUnsafeMethod(method)) {
                    return;
                }
                if (settings.crossDomain) {
                    return;
                }
                xhr.setRequestHeader('X-CSRFToken', token);
            }
        });
        window.jQuery.__amsCsrfBound = true;
    }

    setupJqueryCsrf();
    document.addEventListener('DOMContentLoaded', setupJqueryCsrf);

    if (window.XMLHttpRequest && XMLHttpRequest.prototype) {
        var originalOpen = XMLHttpRequest.prototype.open;
        var originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.open = function (method, url) {
            this.__amsCsrfMethod = method;
            this.__amsCsrfUrl = url;
            return originalOpen.apply(this, arguments);
        };
        XMLHttpRequest.prototype.send = function () {
            var token = getCsrfToken();
            if (
                token &&
                isUnsafeMethod(this.__amsCsrfMethod) &&
                isSameOrigin(this.__amsCsrfUrl || '')
            ) {
                try {
                    this.setRequestHeader('X-CSRFToken', token);
                } catch (e) {
                    /* header already set or request not opened */
                }
            }
            return originalSend.apply(this, arguments);
        };
    }
})();
