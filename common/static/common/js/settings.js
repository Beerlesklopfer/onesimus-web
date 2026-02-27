/**
 * OnesimSettings — per-user preference store
 *
 * Two-tier persistence:
 *   1. localStorage  — immediate, works offline / before DB migration runs
 *   2. Server API    — server-side per-user storage (/common/preferences/)
 *                      loaded on first access per scope; wins over localStorage
 *                      when available.
 *
 * Usage:
 *   await OnesimSettings.loadScope('jobs.filter.ui');   // pre-load a scope
 *   const v = OnesimSettings.getSync('jobs.filter.ui', 'fs-basic', true);
 *   OnesimSettings.set('jobs.filter.ui', 'fs-basic', false);
 *   OnesimSettings.setMany('jobs.filter', { per_page: 50, status_open: true });
 */
const OnesimSettings = (() => {
    const API_PREFS = '/common/preferences/';
    const LS_PREFIX  = 'onesim.pref.';   // localStorage key prefix

    // in-memory cache: scope -> { key: value }
    const _cache  = {};
    // scopes fully loaded from server
    const _loaded = new Set();
    // in-flight server requests per scope
    const _loading = {};

    // ── localStorage helpers ───────────────────────────────────────────
    function _lsKey(scope, key) { return LS_PREFIX + scope + '.' + key; }

    function _lsGet(scope, key, defVal) {
        try {
            const raw = localStorage.getItem(_lsKey(scope, key));
            return raw !== null ? JSON.parse(raw) : defVal;
        } catch (e) { return defVal; }
    }

    function _lsSet(scope, key, value) {
        try { localStorage.setItem(_lsKey(scope, key), JSON.stringify(value)); } catch (e) {}
    }

    // ── CSRF token ────────────────────────────────────────────────────
    function _csrf() {
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    function _ensureScope(scope) {
        if (!_cache[scope]) _cache[scope] = {};
    }

    // ── Public API ────────────────────────────────────────────────────

    /**
     * Pre-load all preferences for a scope.
     * Instantly seeds cache from localStorage, then fetches from server
     * (server values override localStorage when available).
     * Subsequent calls for the same scope are no-ops.
     */
    async function loadScope(scope) {
        if (_loaded.has(scope)) return;
        if (_loading[scope])    return _loading[scope];

        _ensureScope(scope);

        // Step 1: seed cache from localStorage (synchronous, instant)
        for (var i = 0; i < localStorage.length; i++) {
            var k = localStorage.key(i);
            var pfx = LS_PREFIX + scope + '.';
            if (k && k.startsWith(pfx)) {
                var prefKey = k.slice(pfx.length);
                try { _cache[scope][prefKey] = JSON.parse(localStorage.getItem(k)); } catch (e) {}
            }
        }

        // Step 2: fetch from server; server values win on success
        _loading[scope] = fetch(API_PREFS + '?scope=' + encodeURIComponent(scope), {
            credentials: 'same-origin',
        })
            .then(function (r) { return r.ok ? r.json() : {}; })
            .then(function (data) {
                Object.assign(_cache[scope], data);
                // mirror server values to localStorage
                var keys = Object.keys(data);
                for (var i = 0; i < keys.length; i++) { _lsSet(scope, keys[i], data[keys[i]]); }
                _loaded.add(scope);
                delete _loading[scope];
            })
            .catch(function () {
                // server unavailable — localStorage values remain in cache
                _loaded.add(scope);
                delete _loading[scope];
            });

        return _loading[scope];
    }

    /**
     * Async get — loads scope on first access.
     */
    async function get(scope, key, defVal) {
        if (defVal === undefined) defVal = null;
        await loadScope(scope);
        _ensureScope(scope);
        var v = _cache[scope][key];
        return v !== undefined ? v : defVal;
    }

    /**
     * Synchronous get from cache.
     * Always call and await loadScope() before using this.
     * Falls back to localStorage, then defVal.
     */
    function getSync(scope, key, defVal) {
        if (defVal === undefined) defVal = null;
        _ensureScope(scope);
        var v = _cache[scope][key];
        if (v !== undefined) return v;
        return _lsGet(scope, key, defVal);
    }

    /**
     * Write a single key.
     * Updates cache + localStorage immediately; persists to server async.
     */
    function set(scope, key, value) {
        _ensureScope(scope);
        _cache[scope][key] = value;
        _lsSet(scope, key, value);

        fetch(API_PREFS, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _csrf() },
            body: JSON.stringify({ scope: scope, key: key, value: value }),
        }).catch(function () {});
    }

    /**
     * Bulk-write multiple keys in one HTTP request.
     * Cache + localStorage updated immediately.
     */
    function setMany(scope, data) {
        _ensureScope(scope);
        Object.assign(_cache[scope], data);
        var keys = Object.keys(data);
        for (var i = 0; i < keys.length; i++) { _lsSet(scope, keys[i], data[keys[i]]); }

        fetch(API_PREFS, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _csrf() },
            body: JSON.stringify({ scope: scope, data: data }),
        }).catch(function () {});
    }

    return { get: get, set: set, setMany: setMany, loadScope: loadScope, getSync: getSync };
})();
