/**
 * Mobile shell: drawer toggle, body class, active nav highlighting.
 */
(function () {
    'use strict';

    var MOBILE_MQ = window.matchMedia('(max-width: 991.98px)');

    function isMobile() {
        return MOBILE_MQ.matches;
    }

    function setShellClass() {
        document.body.classList.toggle('m-shell', isMobile());
        if (!isMobile()) {
            closeDrawer();
        }
    }

    function getDrawer() {
        return document.getElementById('mDrawer');
    }

    function getBackdrop() {
        return document.getElementById('mDrawerBackdrop');
    }

    function openDrawer() {
        var drawer = getDrawer();
        var backdrop = getBackdrop();
        if (!drawer || !backdrop) return;
        drawer.classList.add('is-open');
        drawer.setAttribute('aria-hidden', 'false');
        backdrop.classList.add('is-open');
        backdrop.hidden = false;
        document.body.classList.add('m-drawer-open');
    }

    function closeDrawer() {
        var drawer = getDrawer();
        var backdrop = getBackdrop();
        if (!drawer || !backdrop) return;
        drawer.classList.remove('is-open');
        drawer.setAttribute('aria-hidden', 'true');
        backdrop.classList.remove('is-open');
        backdrop.hidden = true;
        document.body.classList.remove('m-drawer-open');
    }

    function toggleDrawer() {
        var drawer = getDrawer();
        if (!drawer) return;
        if (drawer.classList.contains('is-open')) {
            closeDrawer();
        } else {
            openDrawer();
        }
    }

    function highlightActiveDrawerLink() {
        var endpoint = document.body.getAttribute('data-active-endpoint') || '';
        if (!endpoint) return;
        document.querySelectorAll('.m-drawer-link[data-endpoint]').forEach(function (link) {
            var target = link.getAttribute('data-endpoint') || '';
            var active = endpoint === target || (target && endpoint.indexOf(target) === 0);
            link.classList.toggle('is-active', active);
        });
    }

    function bindEvents() {
        var menuBtn = document.getElementById('mMenuBtn');
        var closeBtn = document.getElementById('mDrawerClose');
        var backdrop = getBackdrop();

        if (menuBtn) {
            menuBtn.addEventListener('click', function (e) {
                e.preventDefault();
                toggleDrawer();
            });
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', function (e) {
                e.preventDefault();
                closeDrawer();
            });
        }

        if (backdrop) {
            backdrop.addEventListener('click', closeDrawer);
        }

        document.querySelectorAll('.m-drawer-link').forEach(function (link) {
            link.addEventListener('click', function () {
                closeDrawer();
            });
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeDrawer();
        });

        if (MOBILE_MQ.addEventListener) {
            MOBILE_MQ.addEventListener('change', setShellClass);
        } else if (MOBILE_MQ.addListener) {
            MOBILE_MQ.addListener(setShellClass);
        }

        window.addEventListener('resize', setShellClass);
    }

    document.addEventListener('DOMContentLoaded', function () {
        setShellClass();
        highlightActiveDrawerLink();
        bindEvents();
    });
})();
