/**
 * HTML / JS-literal escaping for values interpolated into innerHTML.
 * Prevents DOM XSS when API or user-controlled strings are rendered.
 */
(function (global) {
    'use strict';

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function jsStringLiteral(value) {
        return JSON.stringify(String(value == null ? '' : value))
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
    }

    global.escapeHtml = escapeHtml;
    global.jsStringLiteral = jsStringLiteral;
})(window);
