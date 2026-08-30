/**
 * Offline take-attendance: IndexedDB roster snapshots, drafts, and a
 * deduped POST queue keyed by (session_id, date). Works in the page and
 * in the service worker (Background Sync).
 *
 * Does not change the server save contract: date, optional double_class=1,
 * student_<class_student_pk>=present.
 */
(function (root) {
    'use strict';

    var DB_NAME = 'ams-attendance-offline';
    var DB_VERSION = 1;
    var STORE_ROSTERS = 'rosters';
    var STORE_DRAFTS = 'drafts';
    var STORE_QUEUE = 'queue';
    var SYNC_TAG = 'ams-attendance-sync';
    var STALE_MS = 7 * 24 * 60 * 60 * 1000;
    var HEADER_VALUE = 'AMSAttendanceOffline';

    var replaying = false;

    function queueKey(sessionId, dateStr) {
        return String(sessionId) + '|' + String(dateStr);
    }

    function openDb() {
        return new Promise(function (resolve, reject) {
            if (typeof indexedDB === 'undefined') {
                reject(new Error('indexedDB unavailable'));
                return;
            }
            var req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = function (event) {
                var db = event.target.result;
                if (!db.objectStoreNames.contains(STORE_ROSTERS)) {
                    db.createObjectStore(STORE_ROSTERS, { keyPath: 'sessionId' });
                }
                if (!db.objectStoreNames.contains(STORE_DRAFTS)) {
                    db.createObjectStore(STORE_DRAFTS, { keyPath: 'key' });
                }
                if (!db.objectStoreNames.contains(STORE_QUEUE)) {
                    db.createObjectStore(STORE_QUEUE, { keyPath: 'key' });
                }
            };
            req.onsuccess = function () { resolve(req.result); };
            req.onerror = function () { reject(req.error || new Error('idb open failed')); };
        });
    }

    function idbGet(storeName, key) {
        return openDb().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction(storeName, 'readonly');
                var req = tx.objectStore(storeName).get(key);
                req.onsuccess = function () { resolve(req.result || null); };
                req.onerror = function () { reject(req.error); };
                tx.oncomplete = function () { db.close(); };
                tx.onerror = function () { db.close(); reject(tx.error); };
            });
        });
    }

    function idbPut(storeName, value) {
        return openDb().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction(storeName, 'readwrite');
                tx.objectStore(storeName).put(value);
                tx.oncomplete = function () { db.close(); resolve(value); };
                tx.onerror = function () { db.close(); reject(tx.error); };
            });
        });
    }

    function idbDelete(storeName, key) {
        return openDb().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction(storeName, 'readwrite');
                tx.objectStore(storeName).delete(key);
                tx.oncomplete = function () { db.close(); resolve(); };
                tx.onerror = function () { db.close(); reject(tx.error); };
            });
        });
    }

    function idbGetAll(storeName) {
        return openDb().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction(storeName, 'readonly');
                var req = tx.objectStore(storeName).getAll();
                req.onsuccess = function () { resolve(req.result || []); };
                req.onerror = function () { reject(req.error); };
                tx.oncomplete = function () { db.close(); };
                tx.onerror = function () { db.close(); reject(tx.error); };
            });
        });
    }

    function notifyChanged() {
        try {
            if (typeof window !== 'undefined' && window.dispatchEvent) {
                window.dispatchEvent(new CustomEvent('ams:attendance-queue-changed'));
            }
        } catch (e) { /* ignore */ }
        try {
            if (typeof self !== 'undefined' && self.clients && self.clients.matchAll) {
                self.clients.matchAll({ includeUncontrolled: true, type: 'window' }).then(function (clients) {
                    clients.forEach(function (client) {
                        client.postMessage({ type: 'ams-attendance-queue-changed' });
                    });
                });
            }
        } catch (e) { /* ignore */ }
    }

    function saveRoster(sessionId, roster) {
        var sid = Number(sessionId);
        var record = {
            sessionId: sid,
            courseName: roster.course_name || roster.courseName || '',
            courseCode: roster.course_code || roster.courseCode || '',
            splitNote: roster.split_note || roster.splitNote || null,
            fetchedAt: roster.fetched_at || roster.fetchedAt || new Date().toISOString(),
            students: roster.students || [],
        };
        return idbPut(STORE_ROSTERS, record);
    }

    function getRoster(sessionId) {
        return idbGet(STORE_ROSTERS, Number(sessionId));
    }

    function saveDraft(sessionId, dateStr, body) {
        var record = {
            key: queueKey(sessionId, dateStr),
            sessionId: Number(sessionId),
            date: String(dateStr),
            body: body,
            savedAt: new Date().toISOString(),
        };
        return idbPut(STORE_DRAFTS, record);
    }

    function getDraft(sessionId, dateStr) {
        return idbGet(STORE_DRAFTS, queueKey(sessionId, dateStr));
    }

    function deleteDraft(sessionId, dateStr) {
        return idbDelete(STORE_DRAFTS, queueKey(sessionId, dateStr));
    }

    function enqueue(sessionId, dateStr, url, body) {
        var record = {
            key: queueKey(sessionId, dateStr),
            sessionId: Number(sessionId),
            date: String(dateStr),
            url: url,
            body: body,
            savedAt: new Date().toISOString(),
        };
        return idbPut(STORE_QUEUE, record).then(function (saved) {
            notifyChanged();
            return saved;
        });
    }

    function getQueue() {
        return idbGetAll(STORE_QUEUE);
    }

    function getQueueItem(sessionId, dateStr) {
        return idbGet(STORE_QUEUE, queueKey(sessionId, dateStr));
    }

    function removeQueueItem(key) {
        return idbDelete(STORE_QUEUE, key).then(function () {
            notifyChanged();
        });
    }

    function queueCount() {
        return getQueue().then(function (items) { return items.length; });
    }

    function collectFormBody(form) {
        var params = new URLSearchParams();
        var fd = new FormData(form);
        fd.forEach(function (value, name) {
            params.append(name, value);
        });
        return params.toString();
    }

    function applyBodyToForm(form, body) {
        if (!form || !body) return;
        var params = new URLSearchParams(body);
        var dateInput = form.querySelector('input[name="date"]');
        if (dateInput && params.get('date')) {
            dateInput.value = params.get('date');
        }
        var doubleEl = form.querySelector('#double_class, input[name="double_class"]');
        if (doubleEl) {
            doubleEl.checked = params.get('double_class') === '1';
        }
        var boxes = form.querySelectorAll('input[type="checkbox"][name^="student_"]');
        for (var i = 0; i < boxes.length; i++) {
            boxes[i].checked = params.get(boxes[i].name) === 'present';
        }
    }

    function isAuthFailure(res, locationHref) {
        if (!res) return false;
        if (res.status === 401 || res.status === 403) return true;
        var loc = locationHref || '';
        return loc.indexOf('/login') !== -1 || loc.indexOf('/auth/login') !== -1;
    }

    function postAttendance(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'Accept': 'application/json',
                'X-Requested-With': HEADER_VALUE,
            },
            body: body,
            credentials: 'same-origin',
            redirect: 'manual',
        }).then(function (res) {
            var loc = '';
            try { loc = res.headers.get('Location') || ''; } catch (e) { loc = ''; }

            if (res.type === 'opaqueredirect' || (res.status >= 300 && res.status < 400)) {
                if (isAuthFailure(res, loc)) {
                    var authErr = new Error('auth');
                    authErr.code = 'auth';
                    throw authErr;
                }
                return { ok: true, redirected: true, redirect: loc };
            }

            if (isAuthFailure(res, loc)) {
                var err = new Error('auth');
                err.code = 'auth';
                throw err;
            }

            var ct = (res.headers.get('content-type') || '');
            if (ct.indexOf('application/json') !== -1) {
                return res.json().then(function (data) {
                    if (data && data.ok) return data;
                    var fail = new Error((data && data.error) || 'save-failed');
                    fail.status = res.status;
                    throw fail;
                });
            }

            if (res.ok) return { ok: true };
            var fail = new Error('save-failed');
            fail.status = res.status;
            throw fail;
        });
    }

    function replayItems(items, index, acc) {
        if (index >= items.length) return Promise.resolve(acc);
        var item = items[index];
        return postAttendance(item.url, item.body).then(function () {
            return removeQueueItem(item.key).then(function () {
                return deleteDraft(item.sessionId, item.date).then(function () {
                    acc.sent += 1;
                    acc.remaining -= 1;
                    return replayItems(items, index + 1, acc);
                });
            });
        }).catch(function (err) {
            if (err && err.code === 'auth') {
                acc.authFailed = true;
                return acc;
            }
            acc.error = err;
            return acc;
        });
    }

    function isOffline() {
        return typeof navigator !== 'undefined' && navigator.onLine === false;
    }

    function replayQueue() {
        if (replaying) return Promise.resolve({ skipped: true });
        if (isOffline()) return Promise.resolve({ offline: true });
        replaying = true;
        return getQueue().then(function (items) {
            if (!items.length) {
                return { sent: 0, remaining: 0 };
            }
            return replayItems(items, 0, { sent: 0, remaining: items.length, authFailed: false });
        }).then(function (result) {
            replaying = false;
            notifyChanged();
            return result;
        }, function (err) {
            replaying = false;
            throw err;
        });
    }

    function requestBackgroundSync() {
        if (typeof navigator === 'undefined' || !navigator.serviceWorker) {
            return Promise.resolve(false);
        }
        return navigator.serviceWorker.ready.then(function (reg) {
            if (reg.sync && typeof reg.sync.register === 'function') {
                return reg.sync.register(SYNC_TAG).then(function () { return true; });
            }
            return false;
        }).catch(function () { return false; });
    }

    function prefetchSession(sessionId) {
        var sid = String(sessionId);
        var rosterUrl = '/class-management/take_attendance/' + sid + '/roster.json';
        var pageUrl = '/class-management/take_attendance/' + sid;
        return fetch(rosterUrl, {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' },
        }).then(function (res) {
            if (!res.ok) return null;
            return res.json();
        }).then(function (data) {
            if (data && data.success) {
                return saveRoster(sid, data);
            }
            return null;
        }).then(function () {
            return fetch(pageUrl, {
                credentials: 'same-origin',
                headers: { 'Accept': 'text/html' },
            });
        }).catch(function () { return null; });
    }

    function isRosterStale(roster, nowMs) {
        if (!roster || !roster.fetchedAt) return true;
        var then = Date.parse(roster.fetchedAt);
        if (isNaN(then)) return true;
        return ((nowMs || Date.now()) - then) > STALE_MS;
    }

    var api = {
        queueKey: queueKey,
        saveRoster: saveRoster,
        getRoster: getRoster,
        saveDraft: saveDraft,
        getDraft: getDraft,
        deleteDraft: deleteDraft,
        enqueue: enqueue,
        getQueue: getQueue,
        getQueueItem: getQueueItem,
        removeQueueItem: removeQueueItem,
        queueCount: queueCount,
        collectFormBody: collectFormBody,
        applyBodyToForm: applyBodyToForm,
        postAttendance: postAttendance,
        replayQueue: replayQueue,
        requestBackgroundSync: requestBackgroundSync,
        prefetchSession: prefetchSession,
        isRosterStale: isRosterStale,
        STALE_MS: STALE_MS,
        SYNC_TAG: SYNC_TAG,
    };

    root.AMSAttendanceOffline = api;
})(typeof self !== 'undefined' ? self : this);
