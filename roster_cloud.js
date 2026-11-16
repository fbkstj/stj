/* roster_cloud.js：輪值表（roster.html）的雲端存檔
 *
 * 輪值表原本只存在瀏覽器的 localStorage（ym_rosters），換電腦就看不到。
 * 這裡把資料同步到 Supabase（Edge Function「roster」），哪台電腦登入都是同一份。
 *
 * 做法：網頁照舊讀寫 localStorage；這個模組負責
 *   登入後 → 先補送離線時改過／刪過的月份 → 再從雲端拉全部 → 合併回 localStorage
 *   存檔／刪除 → 先寫本機，再推上雲端；推不上去就記下來，下次同步時補送
 *
 * 讀寫雲端都要密碼；密碼只送到伺服器比對，不存在網頁或瀏覽器裡。
 */
(function () {
  'use strict';

  var PROD_URL = 'https://mcewgfzeqhdpygfvbfij.supabase.co/functions/v1/roster';
  var LS_DATA = 'ym_rosters';                 // 網頁原本就在用的鍵，不改名
  var LS_DIRTY = 'ym_rosters_dirty';          // 本機改過、還沒送上雲端的月份
  var LS_DELETED = 'ym_rosters_deleted';      // 本機刪掉、還沒在雲端刪掉的月份
  var LS_SKIP = 'ym_rosters_skip_upload';     // 使用者說過「不要上傳」的舊月份
  var TOKEN_KEY = 'ym_roster_token';

  // 本機測試可以用 ?api=http://localhost:埠 指向假伺服器；只有頁面本身也在本機時才接受，避免被釣魚網址導走密碼
  var API_URL = (function () {
    try {
      var q = new URLSearchParams(location.search).get('api');
      var localPage = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
      if (q && localPage && /^http:\/\/(localhost|127\.0\.0\.1):\d+(\/.*)?$/.test(q)) return q;
    } catch (e) { /* 不支援 URLSearchParams 就用正式網址 */ }
    return PROD_URL;
  })();

  /* ---------- 小工具 ---------- */
  function readJSON(store, key, fallback) {
    try {
      var s = store.getItem(key);
      return s ? JSON.parse(s) : fallback;
    } catch (e) { return fallback; }
  }
  function writeJSON(store, key, value) {
    try { store.setItem(key, JSON.stringify(value)); return true; } catch (e) { return false; }
  }
  function readSet(key) { return readJSON(localStorage, key, []); }
  function addToSet(key, item) {
    var s = readSet(key);
    if (s.indexOf(item) < 0) { s.push(item); writeJSON(localStorage, key, s); }
  }
  function removeFromSet(key, item) {
    writeJSON(localStorage, key, readSet(key).filter(function (x) { return x !== item; }));
  }
  function readLocal() { return readJSON(localStorage, LS_DATA, {}) || {}; }
  function writeLocal(all) { writeJSON(localStorage, LS_DATA, all); }

  /* ---------- 登入 token ---------- */
  function getToken() {
    var t = readJSON(sessionStorage, TOKEN_KEY, null) || readJSON(localStorage, TOKEN_KEY, null);
    if (t && t.token && t.exp > Date.now() + 60 * 1000) return t.token;
    clearToken();
    return null;
  }
  function clearToken() {
    try { sessionStorage.removeItem(TOKEN_KEY); } catch (e) {}
    try { localStorage.removeItem(TOKEN_KEY); } catch (e) {}
  }

  /* ---------- 狀態（給網頁顯示用） ---------- */
  var state = { loggedIn: !!getToken(), busy: false, lastSync: null, error: '' };
  var listeners = [];
  function setState(patch) {
    for (var k in patch) state[k] = patch[k];
    listeners.forEach(function (f) { try { f(state); } catch (e) {} });
  }

  /* ---------- 呼叫伺服器 ---------- */
  function call(fn) {
    var args = Array.prototype.slice.call(arguments, 1);
    var ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, 25000) : null;
    return fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' },   // text/plain 不會觸發 CORS 預檢
      body: JSON.stringify({ fn: fn, args: args }),
      signal: ctrl ? ctrl.signal : undefined,
    }).then(function (r) { return r.json(); }, function (e) {
      throw new Error(e && e.name === 'AbortError' ? '連線逾時，請稍後再試' : '無法連到雲端，請檢查網路');
    }).then(function (res) {
      if (timer) clearTimeout(timer);
      if (res && res.ok) return res.result;
      var msg = (res && res.error) || '雲端回應錯誤';
      if (msg.indexOf('AUTH:') === 0) {
        clearToken();
        setState({ loggedIn: false });
        msg = msg.slice(5);
      }
      throw new Error(msg);
    }, function (e) { if (timer) clearTimeout(timer); throw e; });
  }
  function authed(fn) {
    var token = getToken();
    if (!token) {
      setState({ loggedIn: false });
      return Promise.reject(new Error('尚未登入雲端'));
    }
    return call.apply(null, [fn, token].concat(Array.prototype.slice.call(arguments, 1)));
  }

  /* ---------- 對外功能 ---------- */
  function login(pw, remember) {
    setState({ busy: true, error: '' });
    return call('login', pw, !!remember).then(function (r) {
      clearToken();
      writeJSON(remember ? localStorage : sessionStorage, TOKEN_KEY, r);
      setState({ loggedIn: true, busy: false });
      return sync();
    }, function (e) {
      setState({ busy: false, error: e.message });
      throw e;
    });
  }

  function logout() {
    clearToken();
    setState({ loggedIn: false, lastSync: null, error: '' });
  }

  /** 同步一次。回傳 { localOnly: 只在這台電腦、雲端沒有的月份（扣掉說過不要上傳的） } */
  function sync() {
    if (!getToken()) { setState({ loggedIn: false }); return Promise.resolve({ localOnly: [] }); }
    setState({ busy: true, error: '' });
    var local = readLocal();
    var chain = Promise.resolve();
    readSet(LS_DELETED).forEach(function (key) {
      chain = chain.then(function () { return authed('remove', key); })
                   .then(function () { removeFromSet(LS_DELETED, key); });
    });
    readSet(LS_DIRTY).forEach(function (key) {
      chain = chain.then(function () {
        if (!local[key]) { removeFromSet(LS_DIRTY, key); return; }
        return authed('save', key, local[key]).then(function () { removeFromSet(LS_DIRTY, key); });
      });
    });
    return chain.then(function () { return authed('getAll'); }).then(function (cloud) {
      var merged = readLocal();
      Object.keys(cloud).forEach(function (key) { merged[key] = cloud[key].data; });
      writeLocal(merged);
      var skip = readSet(LS_SKIP);
      var localOnly = Object.keys(merged).filter(function (k) {
        return !cloud[k] && skip.indexOf(k) < 0;
      }).sort();
      setState({ busy: false, lastSync: new Date(), error: '' });
      return { localOnly: localOnly, cloudKeys: Object.keys(cloud) };
    }, function (e) {
      setState({ busy: false, error: e.message });
      throw e;
    });
  }

  /** 網頁存檔後呼叫：把這個月推上雲端。回傳 'cloud'（已同步）或 'local'（只存本機） */
  function saveKey(key) {
    var data = readLocal()[key];
    if (!data) return Promise.resolve('local');
    removeFromSet(LS_DELETED, key);
    addToSet(LS_DIRTY, key);
    if (!getToken()) return Promise.resolve('local');
    setState({ busy: true, error: '' });
    return authed('save', key, data).then(function () {
      removeFromSet(LS_DIRTY, key);
      setState({ busy: false, lastSync: new Date() });
      return 'cloud';
    }, function (e) {
      setState({ busy: false, error: e.message });
      return 'local';
    });
  }

  /** 網頁刪除後呼叫：雲端也刪掉。回傳 'cloud' 或 'local' */
  function removeKey(key) {
    removeFromSet(LS_DIRTY, key);
    addToSet(LS_DELETED, key);
    if (!getToken()) return Promise.resolve('local');
    setState({ busy: true, error: '' });
    return authed('remove', key).then(function () {
      removeFromSet(LS_DELETED, key);
      setState({ busy: false, lastSync: new Date() });
      return 'cloud';
    }, function (e) {
      setState({ busy: false, error: e.message });
      return 'local';
    });
  }

  /** 把只在本機的舊月份上傳（雲端已有的月份不會被覆蓋） */
  function uploadLocal(keys) {
    var local = readLocal();
    var rec = {};
    keys.forEach(function (k) { if (local[k]) rec[k] = local[k]; });
    setState({ busy: true, error: '' });
    return authed('importMany', rec).then(function (r) {
      setState({ busy: false, lastSync: new Date() });
      return r;
    }, function (e) {
      setState({ busy: false, error: e.message });
      throw e;
    });
  }

  function skipUpload(keys) { keys.forEach(function (k) { addToSet(LS_SKIP, k); }); }

  /** 把本機全部紀錄下載成 JSON 備份檔 */
  function exportBackup() {
    var all = readLocal();
    var payload = { app: 'ymhs-roster', version: 1, exported_at: new Date().toISOString(), rosters: all };
    var blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    var a = document.createElement('a');
    var d = new Date();
    var stamp = d.getFullYear() + String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0');
    a.href = URL.createObjectURL(blob);
    a.download = '輪值表備份_' + stamp + '.json';
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    return Object.keys(all).length;
  }

  /** 讀入備份檔，合併到本機（同一個月以備份檔為準）。回傳匯入的月份清單 */
  function importBackup(file) {
    return file.text().then(function (text) {
      var obj;
      try { obj = JSON.parse(text); } catch (e) { throw new Error('這不是輪值表備份檔（JSON 格式錯誤）'); }
      var rosters = obj && obj.app === 'ymhs-roster' ? obj.rosters : obj;
      if (!rosters || typeof rosters !== 'object' || Array.isArray(rosters)) throw new Error('這不是輪值表備份檔');
      var keys = Object.keys(rosters).filter(function (k) { return /^\d{4}-(0[1-9]|1[0-2])$/.test(k); });
      if (!keys.length) throw new Error('備份檔裡沒有任何月份資料');
      var local = readLocal();
      keys.forEach(function (k) {
        local[k] = rosters[k];
        addToSet(LS_DIRTY, k);              // 登入後會送上雲端
        removeFromSet(LS_DELETED, k);
      });
      writeLocal(local);
      return keys.sort();
    });
  }

  window.RosterCloud = {
    apiUrl: API_URL,
    state: function () { return Object.assign({}, state); },
    subscribe: function (f) {
      listeners.push(f);
      return function () { listeners = listeners.filter(function (x) { return x !== f; }); };
    },
    isLoggedIn: function () { return !!getToken(); },
    pendingCount: function () { return readSet(LS_DIRTY).length + readSet(LS_DELETED).length; },
    isPending: function (key) { return readSet(LS_DIRTY).indexOf(key) >= 0; },
    login: login, logout: logout, sync: sync,
    saveKey: saveKey, removeKey: removeKey,
    uploadLocal: uploadLocal, skipUpload: skipUpload,
    exportBackup: exportBackup, importBackup: importBackup,
  };
})();
