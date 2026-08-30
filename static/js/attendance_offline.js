/**
 * Device-first offline queue for attendance, assessment, and exam marks.
 * IndexedDB persists after the browser closes. Replay retries on reconnect,
 * visibility, and a short interval — not only a single `online` event.
 */
(function (root) {
    'use strict';

    var DB_NAME = 'ams-attendance-offline';
    var DB_VERSION = 2;
    var STORE_ROSTERS = 'rosters';
    var STORE_DRAFTS = 'drafts';
    var STORE_QUEUE = 'queue';
    var SYNC_TAG = 'ams-attendance-sync';
    var STALE_MS = 7 * 24 * 60 * 60 * 1000;
    var HEADER_VALUE = 'AMSOfflineSync';
    var WATCH_MS = 8000;

    var replaying = false;
    var watchdogStarted = false;

    function queueKey(sessionId, dateStr) {
        return 'attendance|' + String(sessionId) + '|' + String(dateStr);
    }

    function legacyAttendanceKey(sessionId, dateStr) {
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

    function notifyChanged(detail) {
        try {
            if (typeof window !== 'undefined' && window.dispatchEvent) {
                window.dispatchEvent(new CustomEvent('ams:attendance-queue-changed', { detail: detail || {} }));
            }
        } catch (e) { /* ignore */ }
        try {
            if (typeof self !== 'undefined' && self.clients && self.clients.matchAll) {
                self.clients.matchAll({ includeUncontrolled: true, type: 'window' }).then(function (clients) {
                    clients.forEach(function (client) {
                        client.postMessage({ type: 'ams-attendance-queue-changed', detail: detail || {} });
                    });
                });
            }
        } catch (e) { /* ignore */ }
    }

    function saveRoster(sessionId, roster) {
        var record = {
            sessionId: Number(sessionId),
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
        return idbPut(STORE_DRAFTS, {
            key: queueKey(sessionId, dateStr),
            sessionId: Number(sessionId),
            date: String(dateStr),
            body: body,
            savedAt: new Date().toISOString(),
        });
    }

    function getDraft(sessionId, dateStr) {
        return idbGet(STORE_DRAFTS, queueKey(sessionId, dateStr)).then(function (row) {
            return row || idbGet(STORE_DRAFTS, legacyAttendanceKey(sessionId, dateStr));
        });
    }

    function deleteDraft(sessionId, dateStr) {
        return idbDelete(STORE_DRAFTS, queueKey(sessionId, dateStr)).then(function () {
            return idbDelete(STORE_DRAFTS, legacyAttendanceKey(sessionId, dateStr));
        });
    }

    function normalizeItem(item) {
        if (!item) return item;
        if (!item.kind) item.kind = 'attendance';
        if (!item.contentType) {
            item.contentType = 'application/x-www-form-urlencoded;charset=UTF-8';
        }
        if (!item.label) {
            if (item.kind === 'assessment') item.label = 'Assessment';
            else if (item.kind === 'exam_marks') item.label = 'Exam marks';
            else item.label = item.date ? ('Attendance · ' + item.date) : 'Attendance';
        }
        return item;
    }

    function enqueueItem(item, options) {
        options = options || {};
        if (!item || !item.key || !item.url) {
            return Promise.reject(new Error('invalid queue item'));
        }
        var record = normalizeItem({
            key: item.key,
            kind: item.kind || 'attendance',
            sessionId: item.sessionId || null,
            date: item.date || '',
            url: item.url,
            method: 'POST',
            contentType: item.contentType,
            body: item.body || '',
            label: item.label || '',
            savedAt: new Date().toISOString(),
        });
        return idbPut(STORE_QUEUE, record).then(function (saved) {
            if (!options.quiet) notifyChanged({ reason: 'enqueue', key: saved.key });
            return saved;
        });
    }

    function enqueue(sessionId, dateStr, url, body) {
        return enqueueItem({
            key: queueKey(sessionId, dateStr),
            kind: 'attendance',
            sessionId: Number(sessionId),
            date: String(dateStr),
            url: url,
            body: body,
            label: 'Attendance · ' + dateStr,
        });
    }

    function getQueue() {
        return idbGetAll(STORE_QUEUE).then(function (items) {
            return (items || []).map(normalizeItem);
        });
    }

    function getQueueItem(sessionId, dateStr) {
        return idbGet(STORE_QUEUE, queueKey(sessionId, dateStr)).then(function (row) {
            if (row) return normalizeItem(row);
            return idbGet(STORE_QUEUE, legacyAttendanceKey(sessionId, dateStr)).then(normalizeItem);
        });
    }

    function getItem(key) {
        return idbGet(STORE_QUEUE, key).then(normalizeItem);
    }

    function removeQueueItem(key, options) {
        options = options || {};
        return idbDelete(STORE_QUEUE, key).then(function () {
            if (!options.quiet) notifyChanged({ reason: 'remove', key: key });
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

    function collectAttendanceBody(form) {
        var params = new URLSearchParams();
        if (!form) return params.toString();
        var dateEl = form.querySelector('input[name="date"]');
        if (dateEl && dateEl.value) params.set('date', dateEl.value);
        var doubleEl = form.querySelector('#double_class, input[name="double_class"]');
        if (doubleEl && doubleEl.checked) params.set('double_class', '1');
        var boxes = form.querySelectorAll('input[type="checkbox"][name^="student_"]');
        for (var i = 0; i < boxes.length; i++) {
            params.set(boxes[i].name, boxes[i].checked ? 'present' : 'absent');
        }
        var csrf = form.querySelector('input[name="csrf_token"]');
        if (csrf && csrf.value) params.set('csrf_token', csrf.value);
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

    function authError() {
        var err = new Error('auth');
        err.code = 'auth';
        return err;
    }

    function looksLikeLogin(url) {
        return /\/login(?:\?|$)/i.test(url || '') || /\/auth\/login/i.test(url || '');
    }

    function postItem(item) {
        item = normalizeItem(item);
        var headers = {
            'Accept': 'application/json',
            'X-Requested-With': HEADER_VALUE,
        };
        if (item.contentType) {
            headers['Content-Type'] = item.contentType;
        }
        return fetch(item.url, {
            method: 'POST',
            headers: headers,
            body: item.body,
            credentials: 'same-origin',
            redirect: 'follow',
        }).then(function (res) {
            var finalUrl = '';
            try { finalUrl = res.url || ''; } catch (e) { finalUrl = ''; }
            if (looksLikeLogin(finalUrl) || res.status === 401) {
                throw authError();
            }

            var ct = (res.headers.get('content-type') || '').toLowerCase();
            if (ct.indexOf('json') !== -1) {
                return res.json().then(function (data) {
                    if (data && (data.ok === true || data.success === true)) {
                        return data;
                    }
                    var fail = new Error((data && (data.error || data.message)) || 'save-failed');
                    fail.status = res.status;
                    if (res.status === 401 || res.status === 403) {
                        fail.code = res.status === 401 ? 'auth' : 'forbidden';
                    }
                    throw fail;
                });
            }

            var fail = new Error('save-failed');
            fail.status = res.status;
            fail.code = 'not-json';
            throw fail;
        });
    }

    function postAttendance(url, body) {
        return postItem({
            url: url,
            body: body,
            contentType: 'application/x-www-form-urlencoded;charset=UTF-8',
            kind: 'attendance',
        });
    }

    function clearRelatedDraft(item) {
        if (item && item.kind === 'attendance' && item.sessionId && item.date) {
            return deleteDraft(item.sessionId, item.date);
        }
        return Promise.resolve();
    }

    function withLatestAttendanceBody(item) {
        if (!item || item.kind !== 'attendance' || !item.sessionId || !item.date) {
            return Promise.resolve(item);
        }
        return getDraft(item.sessionId, item.date).then(function (draft) {
            if (draft && draft.body && draft.savedAt && (!item.savedAt || draft.savedAt >= item.savedAt)) {
                item.body = draft.body;
            }
            return item;
        });
    }

    function replayItems(items, index, acc) {
        if (index >= items.length) return Promise.resolve(acc);
        var item = items[index];
        return withLatestAttendanceBody(item).then(function (ready) {
            item = ready;
            return postItem(item);
        }).then(function (result) {
            return removeQueueItem(item.key, { quiet: true }).then(function () {
                return clearRelatedDraft(item).then(function () {
                    acc.sent += 1;
                    acc.remaining -= 1;
                    acc.lastKind = item.kind;
                    acc.lastSessionId = item.sessionId;
                    acc.lastDate = item.date;
                    acc.lastBody = item.body;
                    return replayItems(items, index + 1, acc);
                });
            });
        }).catch(function (err) {
            if (err && err.code === 'auth') {
                acc.authFailed = true;
                return acc;
            }
            acc.error = err;
            return replayItems(items, index + 1, acc);
        });
    }

    function replayQueue() {
        if (replaying) return Promise.resolve({ skipped: true });
        replaying = true;
        notifyChanged({ reason: 'syncing' });
        return getQueue().then(function (items) {
            if (!items.length) {
                return { sent: 0, remaining: 0 };
            }
            return replayItems(items, 0, { sent: 0, remaining: items.length, authFailed: false });
        }).then(function (result) {
            replaying = false;
            notifyChanged({
                reason: result && result.sent ? 'synced' : 'idle',
                sent: result && result.sent,
                remaining: result && result.remaining,
                authFailed: result && result.authFailed,
                kind: result && result.lastKind,
                sessionId: result && result.lastSessionId,
                date: result && result.lastDate,
                body: result && result.lastBody,
            });
            return result;
        }, function (err) {
            replaying = false;
            notifyChanged({ reason: 'idle' });
            throw err;
        });
    }

    function flushItem(item) {
        return enqueueItem(item, { quiet: true }).then(function () {
            return withLatestAttendanceBody(item).then(function (ready) {
                item = ready;
                return postItem(item);
            }).then(function (result) {
                return removeQueueItem(item.key, { quiet: true }).then(function () {
                    return clearRelatedDraft(item).then(function () {
                        notifyChanged({
                            reason: 'synced',
                            sent: 1,
                            remaining: 0,
                            kind: item.kind,
                            sessionId: item.sessionId,
                            date: item.date,
                            body: item.body,
                        });
                        return { synced: true, result: result };
                    });
                });
            }).catch(function (err) {
                notifyChanged({ reason: 'enqueue', key: item.key });
                requestBackgroundSync();
                if (err && err.code === 'auth') {
                    return { synced: false, queued: true, authFailed: true };
                }
                return { synced: false, queued: true, error: err };
            });
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

    function prefetchUrl(url) {
        return fetch(url, {
            credentials: 'same-origin',
            headers: { 'Accept': 'text/html' },
        }).catch(function () { return null; });
    }

    function prefetchSession(sessionId) {
        var sid = String(sessionId);
        var rosterUrl = '/class-management/take_attendance/' + sid + '/roster.json';
        var pageUrl = '/class-management/take_attendance/' + sid;
        var assessmentUrl = '/class-management/assessment/' + sid;
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
            return Promise.all([prefetchUrl(pageUrl), prefetchUrl(assessmentUrl)]);
        }).catch(function () { return null; });
    }

    function isRosterStale(roster, nowMs) {
        if (!roster || !roster.fetchedAt) return true;
        var then = Date.parse(roster.fetchedAt);
        if (isNaN(then)) return true;
        return ((nowMs || Date.now()) - then) > STALE_MS;
    }

    function kickReplay() {
        replayQueue().catch(function () {});
    }

    function startWatchdog() {
        if (watchdogStarted || typeof document === 'undefined') return;
        watchdogStarted = true;
        var delayed = function (ms) {
            return function () { setTimeout(kickReplay, ms); };
        };
        if (typeof window !== 'undefined') {
            window.addEventListener('online', function () {
                kickReplay();
                setTimeout(kickReplay, 800);
                setTimeout(kickReplay, 2500);
                setTimeout(kickReplay, 8000);
            });
            window.addEventListener('pageshow', kickReplay);
            window.addEventListener('focus', delayed(300));
        }
        document.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'visible') kickReplay();
        });
        setInterval(function () {
            if (document.hidden) return;
            getQueue().then(function (items) {
                if (items.length) kickReplay();
            }).catch(function () {});
        }, WATCH_MS);
        requestBackgroundSync();
        kickReplay();
    }

    var api = {
        queueKey: queueKey,
        saveRoster: saveRoster,
        getRoster: getRoster,
        saveDraft: saveDraft,
        getDraft: getDraft,
        deleteDraft: deleteDraft,
        enqueue: enqueue,
        enqueueItem: enqueueItem,
        flushItem: flushItem,
        getQueue: getQueue,
        getQueueItem: getQueueItem,
        getItem: getItem,
        removeQueueItem: removeQueueItem,
        queueCount: queueCount,
        collectFormBody: collectFormBody,
        collectAttendanceBody: collectAttendanceBody,
        applyBodyToForm: applyBodyToForm,
        postAttendance: postAttendance,
        postItem: postItem,
        replayQueue: replayQueue,
        requestBackgroundSync: requestBackgroundSync,
        prefetchSession: prefetchSession,
        prefetchUrl: prefetchUrl,
        isRosterStale: isRosterStale,
        startWatchdog: startWatchdog,
        STALE_MS: STALE_MS,
        SYNC_TAG: SYNC_TAG,
    };

    root.AMSOfflineSync = api;
    root.AMSAttendanceOffline = api;
})(typeof self !== 'undefined' ? self : this);
