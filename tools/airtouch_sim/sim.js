// AirTouch 網頁模擬器：與程式包相同的手勢對應、觸發規則與語音解析，但只改變畫面上的模擬螢幕
(() => {
  const CFG = JSON.parse(document.getElementById('at-config').textContent);
  const POSES = JSON.parse(document.getElementById('at-poses').textContent);
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const BONES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
    [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [0, 17], [17, 18], [18, 19], [19, 20]];
  const G_NAME = { open_palm: '手掌張開', point_right: '食指向右', point_left: '食指向左', thumb_up: '大拇指朝上',
    thumb_down: '大拇指朝下', v_sign: '剪刀手', fist: '握拳', none: '沒有指令', no_hand: '沒有手' };
  const G_ICON = { open_palm: '🖐️', point_right: '👉', point_left: '👈', thumb_up: '👍', thumb_down: '👎', v_sign: '✌️', fist: '✊', none: '🤟' };
  const ACTION_TEXT = {
    play_pause: '播放／暫停', seek_forward: '快轉', seek_back: '倒退', video_mute: '影片靜音切換', fullscreen: '全螢幕切換',
    captions: '字幕切換', next_video: '下一部影片', prev_video: '上一部影片', speed_up: '播放加速', speed_down: '播放減速',
    skip_ad: '按下「略過」', close_video: '關閉目前影片分頁', next_page: '下一頁', prev_page: '上一頁', first_page: '第一頁',
    last_page: '最後一頁', goto_page: '跳頁', goto_title: '跳到指定投影片', black_screen: '黑畫面切換', white_screen: '白畫面切換',
    start_show: '從頭放映', start_here: '從這頁放映', end_show: '結束放映', laser: '雷射筆', pen: '畫筆', arrow_pointer: '一般游標',
    erase_ink: '清除筆跡', zoom_in: '放大', zoom_out: '縮小', fit_page: '恢復頁面大小', mic_toggle: '麥克風開關',
    camera_toggle: '鏡頭開關', raise_hand: '舉手／放下', volume_up: '音量調大', volume_down: '音量調小', mute: '系統靜音切換',
    system_mute: '系統靜音切換', open_youtube: '開啟 YouTube', play_song: '搜尋並播放', lock: '手勢已鎖定', unlock: '手勢已解鎖',
    switch_profile: '切換模式', auto_profile: '自動切換模式', exit: '結束程式',
  };
  const GLOBAL = new Set(['volume_up', 'volume_down', 'mute', 'open_youtube', 'play_song', 'lock', 'unlock',
    'switch_profile', 'auto_profile', 'exit']);
  const WINDOWS = { youtube: 'YouTube', powerpoint: 'PowerPoint', pdf: 'PDF', teams: 'Teams', notepad: '記事本' };
  const TITLES = { youtube: '蔥油餅教學 - YouTube - Google Chrome', powerpoint: '期末報告.pptx - PowerPoint',
    pdf: '實習講義.pdf - Microsoft Edge', teams: '專題討論 | Microsoft Teams', notepad: '未命名 - 記事本',
    zoom: 'Zoom Meeting', meet: 'Meet - abc-defg-hij' };
  const SLIDES = ['AirTouch 無接觸遙控', '專題動機', '系統架構', '手勢辨識原理', '語音指令', '應用程式模式', '測試方法',
    '手勢辨識結果', '語音測試結果', '使用者回饋', '限制與改良', '結論與未來展望'];
  const NOTES = {
    1: '先自我介紹，說明三個使用情境。', 3: '指著架構圖：手勢和語音兩條輸入，最後交給動作執行。',
    8: '先說明混淆矩陣怎麼看，再講最常認錯的手勢。', 12: '總結三個重點，最後感謝指導老師。',
  };
  const SPEEDS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const mmss = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };

  // ---------- 觸發規則（與 gestures.py 的 GestureTrigger 相同） ----------
  class Trigger {
    constructor(map) {
      this.map = map; this.hist = []; this.cur = 'no_hand'; this.start = 0; this.fired = false;
      this.lastFire = -1e9; this.lastAction = ['', -1e9]; this.locked = false;
    }
    setMap(map) { this.map = map; this.fired = true; }
    stable(g) {
      this.hist.push(g);
      if (this.hist.length > 5) this.hist.shift();
      const counts = new Map();
      this.hist.forEach(x => counts.set(x, (counts.get(x) || 0) + 1));
      let best = null;
      counts.forEach((n, x) => { if (best === null || n > counts.get(best)) best = x; });
      return best;
    }
    update(gesture, now) {
      const g = this.stable(gesture);
      if (g !== this.cur) { this.cur = g; this.start = now; this.fired = false; }
      const held = now - this.start;
      if (g === 'fist') {
        if (this.fired) return [g, 1, null];
        if (held >= CFG.lock_hold_sec) {
          this.fired = true; this.locked = !this.locked;
          return [g, 1, { action: this.locked ? 'lock' : 'unlock', gesture: g }];
        }
        return [g, held / CFG.lock_hold_sec, null];
      }
      const spec = this.map[g];
      if (!spec || this.locked) return [g, 0, null];
      if (!this.fired) {
        if (held < spec.hold_sec) return [g, held / spec.hold_sec, null];
        const [lastName, lastTime] = this.lastAction;
        if (spec.action !== lastName && now - lastTime < CFG.cooldown_sec) return [g, 1, null];
        return [g, 1, this.fire(spec.action, g, now)];
      }
      if ((spec.repeat_sec || 0) > 0 && now - this.lastFire >= spec.repeat_sec) return [g, 1, this.fire(spec.action, g, now)];
      return [g, 1, null];
    }
    fire(action, g, now) {
      this.fired = true; this.lastFire = now; this.lastAction = [action, now];
      return { action, gesture: g };
    }
  }

  function matchProfile(title) {
    const t = (title || '').toLowerCase();
    if (!t || t.includes('airtouch')) return null;
    for (const [name, p] of Object.entries(CFG.profiles)) if (p.window.some(k => t.includes(k.toLowerCase()))) return name;
    return null;
  }

  function freshState() {
    return {
      fg: 'youtube', open: new Set(['youtube', 'powerpoint', 'pdf', 'teams', 'notepad']),
      vol: 30, sysMute: false, notes: false,
      yt: { title: '蔥油餅教學', t: 130, dur: 480, playing: true, muted: false, cc: false, full: false, speed: 1, ad: false, closed: false },
      ppt: { show: false, idx: 1, black: false, white: false, tool: '一般游標' },
      pdf: { page: 1, total: 30, zoom: 100 },
      meet: { mic: true, cam: true, hand: false },
    };
  }

  // ---------- 一台模擬的電腦 ----------
  function createDevice(root, onLog) {
    const dev = { st: freshState(), profile: CFG.profiles.youtube ? 'youtube' : Object.keys(CFG.profiles)[0],
      auto: true, gesture: 'no_hand', progress: 0, stable: 'no_hand', visible: true, last: performance.now() / 1000 };
    dev.trig = new Trigger(CFG.profiles[dev.profile].gestures);
    dev.toast = { text: 'AirTouch 模擬器已啟動', ok: true };

    const box = el('div', 'dev');
    const cam = el('div', 'cam');
    cam.setAttribute('aria-label', '鏡頭畫面與 AirTouch 懸浮視窗');
    const hud = el('div', 'hud');
    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('viewBox', '0 0 100 100');
    svg.setAttribute('class', 'hand-svg');
    svg.setAttribute('aria-hidden', 'true');
    svg.innerHTML = '<circle cx="50" cy="50" r="47" fill="none" stroke="#475569" stroke-width="3"/>' +
      '<circle class="ring" cx="50" cy="50" r="47" fill="none" stroke-width="3.5" stroke-linecap="round" transform="rotate(-90 50 50)" stroke-dasharray="295.3" stroke-dashoffset="295.3"/>' +
      '<g class="hand"></g><text class="nohand" x="50" y="54" text-anchor="middle">沒有手</text>';
    const notes = el('div', 'notes');
    const bubble = el('div', 'bubble');
    bubble.hidden = true;
    const toast = el('div', 'toast');
    cam.append(hud, svg, notes, bubble, toast);
    const screen = el('div', 'screen');
    const title = el('div', 'win-title');
    const body = el('div', 'win-body');
    const sys = el('div', 'sysbar');
    screen.append(title, body, sys);
    screen.setAttribute('aria-label', '模擬的電腦螢幕');
    box.append(cam, screen);
    root.append(box);

    const gesturesOf = () => CFG.profiles[dev.profile].gestures;
    const windowOf = p => (p in WINDOWS ? p : p);

    function resolve(action) {
      const prof = CFG.profiles[dev.profile];
      let a = (prof.voice_map || {})[action] || action;
      if (a === 'system_mute') a = 'mute';
      if (GLOBAL.has(a) || a in prof.keys) return [a, true];
      if (a === 'seek_forward' || a === 'seek_back') return [a, !!prof.seek];
      if (a === 'skip_ad') return [a, !!prof.skip_ad];
      if (a === 'goto_page' || a === 'goto_title') return [a, prof.goto === 'powerpoint'];
      return [a, false];
    }

    function describe(a, arg) {
      const label = ACTION_TEXT[a] || a;
      if (a === 'seek_forward' || a === 'seek_back') return `${label} ${arg || 10} 秒`;
      if (a === 'volume_up' || a === 'volume_down') return `${label} ${arg || 1} 格`;
      if (a === 'play_song' && arg) return `${arg.close_current ? '換播' : '播放'}「${arg.query}」`;
      if (a === 'goto_page') return `跳到第 ${arg} 頁`;
      if (a === 'goto_title') return `跳到「${arg}」那頁`;
      return label;
    }

    function setProfile(name, source, raw) {
      dev.profile = name;
      dev.trig.setMap(gesturesOf());
      const msg = `切換到「${CFG.profiles[name].name}」模式`;
      dev.toast = { text: msg, ok: true };
      onLog && onLog(dev, source, raw || name, msg, true);
    }

    dev.setForeground = name => {
      dev.st.fg = name;
      if (dev.auto) {
        const p = matchProfile(TITLES[name]);
        if (p && p !== dev.profile) setProfile(p, 'auto', TITLES[name]);
      }
      render();
    };

    function apply(a, arg) {
      const st = dev.st, yt = st.yt, ppt = st.ppt, pdf = st.pdf, m = st.meet;
      const needShow = () => (ppt.show ? null : [false, '要在「投影片放映」中才有作用，請先說「開始放映」']);
      switch (a) {
        case 'play_pause': if (yt.closed) return [false, '影片分頁已關閉']; yt.playing = !yt.playing; return [true, yt.playing ? '繼續播放' : '已暫停'];
        case 'seek_forward': yt.t = Math.min(yt.dur, yt.t + (arg || 10)); return [true, null];
        case 'seek_back': yt.t = Math.max(0, yt.t - (arg || 10)); return [true, null];
        case 'volume_up': st.vol = Math.min(100, st.vol + 2 * (arg || 1)); return [true, null];
        case 'volume_down': st.vol = Math.max(0, st.vol - 2 * (arg || 1)); return [true, null];
        case 'mute': st.sysMute = !st.sysMute; return [true, st.sysMute ? '電腦已靜音' : '電腦取消靜音'];
        case 'video_mute': yt.muted = !yt.muted; return [true, null];
        case 'fullscreen': yt.full = !yt.full; return [true, null];
        case 'captions': yt.cc = !yt.cc; return [true, null];
        case 'next_video': case 'prev_video': yt.title = a === 'next_video' ? '下一部：蛋餅教學' : '上一部：蔥花切法'; yt.t = 0; yt.playing = true; return [true, null];
        case 'speed_up': case 'speed_down': {
          const i = SPEEDS.indexOf(yt.speed) + (a === 'speed_up' ? 1 : -1);
          yt.speed = SPEEDS[Math.max(0, Math.min(SPEEDS.length - 1, i))];
          return [true, `播放速度 ${yt.speed}x`];
        }
        case 'skip_ad': if (!yt.ad) return [false, '畫面上沒有「略過」按鈕（相似度 0.21）']; yt.ad = false; return [true, '已按下「略過」（相似度 0.97）'];
        case 'close_video': yt.closed = true; yt.playing = false; return [true, null];
        case 'open_youtube': st.open.add('youtube'); st.fg = 'youtube'; yt.closed = false; yt.title = 'YouTube 首頁'; yt.playing = false; return [true, null];
        case 'play_song': st.fg = 'youtube'; Object.assign(yt, { title: arg.query, t: 0, playing: true, closed: false, ad: false }); return [true, null];
        case 'next_page': case 'prev_page': case 'first_page': case 'last_page': case 'goto_page': case 'goto_title': {
          if (dev.profile === 'pdf') {
            const n = { next_page: pdf.page + 1, prev_page: pdf.page - 1, first_page: 1, last_page: pdf.total }[a];
            pdf.page = Math.max(1, Math.min(pdf.total, n));
            return [true, `第 ${pdf.page}／${pdf.total} 頁`];
          }
          if (a === 'goto_title') {
            const i = SLIDES.findIndex(s => s.includes(arg));
            if (i < 0) return [false, `找不到含有「${arg}」的投影片`];
            ppt.idx = i + 1;
            return [true, `「${arg}」→ 跳到第 ${ppt.idx}／${SLIDES.length} 頁`];
          }
          if (a === 'goto_page') {
            if (arg < 1 || arg > SLIDES.length) return [false, `沒有第 ${arg} 頁（共 ${SLIDES.length} 頁）`];
            ppt.idx = arg;
            return [true, `跳到第 ${arg}／${SLIDES.length} 頁`];
          }
          const block = needShow(); if (block) return block;
          const n = { next_page: ppt.idx + 1, prev_page: ppt.idx - 1, first_page: 1, last_page: SLIDES.length }[a];
          ppt.idx = Math.max(1, Math.min(SLIDES.length, n)); ppt.black = ppt.white = false;
          return [true, `第 ${ppt.idx}／${SLIDES.length} 頁`];
        }
        case 'start_show': ppt.show = true; ppt.idx = 1; return [true, null];
        case 'start_here': ppt.show = true; return [true, `從第 ${ppt.idx} 頁放映`];
        case 'end_show': ppt.show = false; ppt.black = ppt.white = false; ppt.tool = '一般游標'; return [true, null];
        case 'black_screen': case 'white_screen': {
          const block = needShow(); if (block) return block;
          const key = a === 'black_screen' ? 'black' : 'white';
          ppt[key] = !ppt[key]; ppt[key === 'black' ? 'white' : 'black'] = false;
          return [true, ppt[key] ? `${key === 'black' ? '黑' : '白'}畫面` : '恢復投影片'];
        }
        case 'laser': case 'pen': case 'arrow_pointer': {
          const block = needShow(); if (block) return block;
          ppt.tool = ACTION_TEXT[a]; return [true, null];
        }
        case 'erase_ink': return needShow() || [true, null];
        case 'zoom_in': pdf.zoom = Math.min(400, pdf.zoom + 10); return [true, `縮放 ${pdf.zoom}%`];
        case 'zoom_out': pdf.zoom = Math.max(30, pdf.zoom - 10); return [true, `縮放 ${pdf.zoom}%`];
        case 'fit_page': pdf.zoom = 100; return [true, null];
        case 'mic_toggle': m.mic = !m.mic; return [true, m.mic ? '麥克風已開啟' : '麥克風已關閉'];
        case 'camera_toggle': m.cam = !m.cam; return [true, m.cam ? '鏡頭已開啟' : '鏡頭已關閉'];
        case 'raise_hand': m.hand = !m.hand; return [true, m.hand ? '已舉手' : '已放下手'];
        default: return [false, `不認得的動作：${a}`];
      }
    }

    dev.execute = (action, arg, source, raw) => {
      const prof = CFG.profiles[dev.profile];
      const [a, ok0] = resolve(action);
      let ok = ok0, msg;
      if (!ok) {
        msg = `「${prof.name}」模式沒有「${ACTION_TEXT[a] || a}」`;
      } else if (a === 'lock' || a === 'unlock') {
        dev.trig.locked = a === 'lock'; msg = ACTION_TEXT[a];
      } else if (a === 'switch_profile') {
        const name = arg === 'meeting' ? CFG.meeting_profiles.find(p => dev.st.open.has(p)) || CFG.meeting_profiles[0] : arg;
        dev.auto = false;
        setProfile(name, source, raw);
        render();
        return;
      } else if (a === 'auto_profile') {
        dev.auto = true; msg = '已開啟自動切換模式';
        const p = matchProfile(TITLES[dev.st.fg]);
        if (p && p !== dev.profile) { onLog && onLog(dev, source, raw, msg, true); setProfile(p, 'auto', TITLES[dev.st.fg]); render(); return; }
      } else if (a === 'exit') {
        msg = '結束程式（網頁模擬器不會真的關閉）';
      } else if (!GLOBAL.has(a) && !dev.st.open.has(windowOf(dev.profile))) {
        ok = false; msg = `找不到「${prof.name}」的視窗`;
      } else {
        if (!GLOBAL.has(a)) dev.st.fg = windowOf(dev.profile);   // 程式會先把該視窗叫到最前面
        const [ok2, m2] = apply(a, arg);
        ok = ok2; msg = m2 || describe(a, arg);
      }
      dev.toast = { text: (ok ? '完成：' : '失敗：') + msg, ok };
      onLog && onLog(dev, source, raw, msg, ok);
      render();
    };

    dev.voice = text => {
      const cmd = VoiceParse(text);
      if (!cmd) {
        dev.toast = { text: `聽不懂：「${text}」`, ok: false };
        onLog && onLog(dev, 'voice', text, '聽不懂', false);
        render();
        return;
      }
      dev.execute(cmd.action, cmd.arg, 'voice', text);
    };
    dev.say = (text, ms = 1600) => {
      bubble.textContent = `🎙️「${text}」`;
      bubble.hidden = false;
      clearTimeout(dev.bubbleTimer);
      dev.bubbleTimer = setTimeout(() => { bubble.hidden = true; }, ms);
    };
    dev.hold = g => { dev.gesture = g; };
    dev.release = () => { dev.gesture = 'no_hand'; };
    dev.reset = () => {
      dev.st = freshState(); dev.auto = true; dev.gesture = 'no_hand'; dev.profile = 'youtube';
      dev.trig = new Trigger(gesturesOf()); dev.toast = { text: '已重設', ok: true };
      bubble.hidden = true; render();
    };
    dev.setProfileNow = name => { dev.profile = name; dev.trig = new Trigger(gesturesOf()); render(); };

    dev.tick = now => {
      const dt = Math.min(0.1, now - dev.last);
      dev.last = now;
      const [stable, progress, ev] = dev.trig.update(dev.gesture, now);
      dev.stable = stable; dev.progress = progress;
      if (ev) {
        const spec = gesturesOf()[ev.gesture] || {};
        dev.execute(ev.action, spec.arg ?? null, 'gesture', G_NAME[ev.gesture]);
      }
      const yt = dev.st.yt;
      if (yt.playing && !yt.ad) yt.t = Math.min(yt.dur, yt.t + dt * yt.speed);
      if (dev.visible) render();
    };

    let lastHand = '';
    function render() {
      const st = dev.st, prof = CFG.profiles[dev.profile], locked = dev.trig.locked;
      const g = dev.stable;
      const spec = gesturesOf()[g];
      hud.className = 'hud' + (locked ? ' locked' : '');
      const pct = dev.progress > 0 && dev.progress < 1 ? `（${Math.round(dev.progress * 100)}%）` : '';
      const target = spec && !locked ? ` → ${ACTION_TEXT[spec.action]}` : '';
      const page = dev.profile === 'powerpoint' ? `｜第 ${st.ppt.idx}／${SLIDES.length} 頁${st.ppt.show ? '' : '（編輯中）'}` : '';
      hud.innerHTML = `<b>模式：${esc(prof.name)}</b>（${dev.auto ? '自動' : '固定'}）｜${locked ? '手勢鎖定' : '手勢啟用'}<br>` +
        `手勢：${G_NAME[g] || g}${pct}${esc(target)}${page}`;
      const ring = svg.querySelector('.ring');
      ring.style.strokeDashoffset = String(295.3 * (1 - Math.max(0, Math.min(1, dev.progress))));
      ring.style.stroke = locked ? '#f87171' : (dev.progress >= 1 ? '#34d399' : '#fbbf24');
      if (g !== lastHand) {
        lastHand = g;
        const pts = POSES[g];
        const hand = svg.querySelector('.hand');
        svg.querySelector('.nohand').style.display = pts ? 'none' : '';
        hand.innerHTML = pts ? BONES.map(([a, b]) => `<line x1="${pts[a][0]}" y1="${pts[a][1]}" x2="${pts[b][0]}" y2="${pts[b][1]}"/>`).join('') +
          pts.map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="${[4, 8, 12, 16, 20].includes(i) ? 2.6 : 1.8}"/>`).join('') : '';
      }
      const showNotes = dev.profile === 'powerpoint' && st.notes;
      notes.hidden = !showNotes;
      if (showNotes) notes.innerHTML = `<b>備忘稿｜${esc(SLIDES[st.ppt.idx - 1])}</b><br>${esc(NOTES[st.ppt.idx] || '（這頁沒有備忘稿）')}`;
      toast.className = 'toast ' + (dev.toast.ok ? 'ok' : 'fail');
      toast.textContent = dev.toast.text;

      title.innerHTML = `<span>${esc(TITLES[st.fg])}</span><span class="fg-tag">最前面的視窗</span>`;
      body.innerHTML = screenHTML(st);
      sys.innerHTML = `<span>${st.sysMute ? '🔇 電腦靜音' : `🔊 音量 ${st.vol}%`}</span><span>AirTouch 懸浮視窗置頂中</span>`;
    }

    function screenHTML(st) {
      const yt = st.yt, ppt = st.ppt, pdf = st.pdf, m = st.meet;
      switch (st.fg) {
        case 'youtube':
          if (yt.closed) return '<div class="yt-closed">YouTube 分頁已關閉</div>';
          return `<div class="yt${yt.full ? ' full' : ''}"><div class="yt-video"><div class="yt-icon">${yt.playing ? '▶' : '❚❚'}</div>` +
            (yt.ad ? '<div class="yt-ad">廣告・5 秒後可略過 <span class="yt-skip">略過 ▶|</span></div>' : '') +
            (yt.cc ? '<div class="yt-cc">（字幕）把麵團揉到表面光滑</div>' : '') + '</div>' +
            `<div class="yt-bar"><div style="width:${(yt.t / yt.dur * 100).toFixed(1)}%"></div></div>` +
            `<div class="yt-meta"><b>${esc(yt.title)}</b><span>${mmss(yt.t)} / ${mmss(yt.dur)}${yt.speed !== 1 ? `・${yt.speed}x` : ''}${yt.muted ? '・影片靜音' : ''}${yt.full ? '・全螢幕' : ''}</span></div></div>`;
        case 'powerpoint':
          if (!ppt.show) {
            return `<div class="ppt-edit"><ol>${SLIDES.map((s, i) => `<li class="${i + 1 === ppt.idx ? 'on' : ''}">${i + 1}</li>`).join('')}</ol>` +
              `<div class="ppt-slide small"><b>${esc(SLIDES[ppt.idx - 1])}</b><span>編輯畫面</span></div></div>`;
          }
          if (ppt.black) return '<div class="ppt-show black">（黑畫面）</div>';
          if (ppt.white) return '<div class="ppt-show white">（白畫面）</div>';
          return `<div class="ppt-show"><b>${esc(SLIDES[ppt.idx - 1])}</b><span class="ppt-no">${ppt.idx} / ${SLIDES.length}</span>` +
            (ppt.tool === '雷射筆' ? '<i class="laser"></i>' : '') + `<span class="ppt-tool">${esc(ppt.tool)}</span></div>`;
        case 'pdf':
          return `<div class="pdf"><div class="pdf-page" style="transform:scale(${Math.min(1.6, pdf.zoom / 100)})"><b>實習講義</b>` +
            `<p>第 ${pdf.page} 頁</p><i></i><i></i><i></i><i></i></div><div class="pdf-meta">第 ${pdf.page}／${pdf.total} 頁・縮放 ${pdf.zoom}%</div></div>`;
        case 'teams':
          return `<div class="meet"><div class="tiles"><div class="tile">老師<br><small>發言中</small></div>` +
            `<div class="tile me${m.cam ? '' : ' off'}">${m.cam ? '你（鏡頭開）' : '你（鏡頭關）'}${m.hand ? '<span class="hand-up">✋</span>' : ''}</div></div>` +
            `<div class="meet-bar"><span class="${m.mic ? 'on' : 'off'}">${m.mic ? '🎤 麥克風開' : '🔇 麥克風關'}</span>` +
            `<span class="${m.cam ? 'on' : 'off'}">${m.cam ? '📷 鏡頭開' : '🚫 鏡頭關'}</span><span class="${m.hand ? 'on' : ''}">✋ ${m.hand ? '已舉手' : '舉手'}</span></div></div>`;
        default:
          return '<div class="notepad">這是記事本，AirTouch 不認得這個視窗，<br>所以維持原本的模式。</div>';
      }
    }

    new IntersectionObserver(es => es.forEach(e => { dev.visible = e.isIntersecting; })).observe(box);
    DEVICES.push(dev);
    render();
    return dev;
  }

  const DEVICES = [];
  const loop = () => {
    const now = performance.now() / 1000;
    DEVICES.forEach(d => d.tick(now));
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);

  function logger(list) {
    const t0 = performance.now();
    return (dev, source, raw, msg, ok) => {
      const s = (performance.now() - t0) / 1000;
      const src = { gesture: '手勢', voice: '語音', auto: '自動', key: '按鍵', button: '按鈕' }[source] || source;
      const li = el('li', ok ? 'ok' : 'fail');
      li.textContent = `${mmss(s)}｜${CFG.profiles[dev.profile].name}｜${src}：${raw} → ${msg}`;
      list.prepend(li);
      while (list.children.length > 8) list.lastChild.remove();
    };
  }

  // ---------- 互動模擬器 ----------
  const simRoot = document.getElementById('at-sim');
  if (simRoot) {
    const controls = el('div', 'sim-controls');
    const rowWin = el('div', 'sim-row', '<span class="sim-label">最前面的視窗</span>');
    const winBtns = {};
    Object.entries(WINDOWS).forEach(([k, name]) => {
      const b = el('button', 'sim-chip', esc(name));
      b.type = 'button';
      b.addEventListener('click', () => dev.setForeground(k));
      winBtns[k] = b;
      rowWin.append(b);
    });
    const autoLabel = el('label', 'sim-auto', '<input type="checkbox" checked> 自動切換模式');
    const autoBox = autoLabel.querySelector('input');
    autoBox.addEventListener('change', () => {
      if (autoBox.checked) dev.execute('auto_profile', null, 'button', '勾選自動切換');
      else { dev.auto = false; }
    });
    rowWin.append(autoLabel);

    const rowG = el('div', 'sim-row', '<span class="sim-label">按住手勢</span>');
    const gBtns = {};
    ['open_palm', 'point_right', 'point_left', 'thumb_up', 'thumb_down', 'v_sign', 'fist', 'none'].forEach(g => {
      const b = el('button', 'sim-gesture');
      b.type = 'button';
      const start = e => { e.preventDefault(); dev.hold(g); b.classList.add('down'); };
      const stop = () => { if (dev.gesture === g) dev.release(); b.classList.remove('down'); };
      b.addEventListener('pointerdown', e => { b.setPointerCapture(e.pointerId); start(e); });
      b.addEventListener('pointerup', stop);
      b.addEventListener('pointercancel', stop);
      b.addEventListener('keydown', e => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) start(e); });
      b.addEventListener('keyup', e => { if (e.key === ' ' || e.key === 'Enter') stop(); });
      b.addEventListener('contextmenu', e => e.preventDefault());
      b.addEventListener('blur', stop);
      gBtns[g] = b;
      rowG.append(b);
    });

    const rowV = el('div', 'sim-row', '<span class="sim-label">語音（打字代替）</span>');
    const form = el('form', 'sim-voice', '<label class="visually-hidden" for="at-sim-text">語音指令</label>' +
      '<input id="at-sim-text" type="text" placeholder="例如：快轉一分半" autocomplete="off"><button type="submit">說出</button>');
    form.addEventListener('submit', e => {
      e.preventDefault();
      const input = form.querySelector('input');
      const text = input.value.trim();
      if (!text) return;
      dev.say(text); dev.voice(text); input.value = '';
    });
    rowV.append(form);
    const chips = el('div', 'sim-row sim-examples', '<span class="sim-label">試試看</span>');
    ['暫停', '快轉一分半', '換播 周杰倫 稻香', '開始放映', '跳到第五頁', '跳到結論那頁', '黑畫面', '放大', '靜音', '電腦靜音',
      '舉手', '切換到簡報模式', '自動切換', '鎖定手勢', '今天天氣很好'].forEach(t => {
      const b = el('button', 'sim-chip small', esc(t));
      b.type = 'button';
      b.addEventListener('click', () => { dev.say(t); dev.voice(t); });
      chips.append(b);
    });
    const rowX = el('div', 'sim-row', '<span class="sim-label">模擬狀況</span>');
    const adBtn = el('button', 'sim-chip', 'YouTube 出現「略過」按鈕');
    adBtn.type = 'button';
    adBtn.addEventListener('click', () => { dev.st.yt.ad = true; dev.st.fg = 'youtube'; dev.setForeground('youtube'); });
    const notesBtn = el('button', 'sim-chip', '按 n 顯示備忘稿');
    notesBtn.type = 'button';
    notesBtn.addEventListener('click', () => { dev.st.notes = !dev.st.notes; notesBtn.setAttribute('aria-pressed', dev.st.notes); });
    notesBtn.setAttribute('aria-pressed', 'false');
    const resetBtn = el('button', 'sim-chip', '全部重設');
    resetBtn.type = 'button';
    resetBtn.addEventListener('click', () => { dev.reset(); autoBox.checked = true; notesBtn.setAttribute('aria-pressed', 'false'); });
    rowX.append(adBtn, notesBtn, resetBtn);
    controls.append(rowWin, rowG, rowV, chips, rowX);

    const stage = el('div');
    const logTitle = el('p', 'sim-log-title', '動作紀錄（和程式的 logs/ 一樣，最新的在上面）');
    const logList = el('ol', 'sim-log');
    logList.setAttribute('aria-live', 'polite');
    simRoot.append(controls, stage, logTitle, logList);
    const dev = createDevice(stage, logger(logList));

    const refresh = () => {
      Object.entries(winBtns).forEach(([k, b]) => b.setAttribute('aria-pressed', String(dev.st.fg === k)));
      autoBox.checked = dev.auto;
      const map = CFG.profiles[dev.profile].gestures;
      Object.entries(gBtns).forEach(([g, b]) => {
        const spec = g === 'fist' ? { action: dev.trig.locked ? 'unlock' : 'lock', hold_sec: CFG.lock_hold_sec } : map[g];
        const sub = spec ? `${ACTION_TEXT[spec.action]}・${spec.hold_sec} 秒${spec.repeat_sec ? '・可連續' : ''}` : '這個模式沒有作用';
        b.innerHTML = `<span class="gi" aria-hidden="true">${G_ICON[g]}</span><span><b>${G_NAME[g]}</b><small>${esc(sub)}</small></span>`;
      });
    };
    const oldTick = dev.tick;
    let lastKey = '';
    dev.tick = now => {
      oldTick(now);
      const key = `${dev.profile}|${dev.st.fg}|${dev.auto}|${dev.trig.locked}`;
      if (key !== lastKey) { lastKey = key; refresh(); }
    };
    refresh();
  }

  // ---------- 情境動畫 ----------
  const SCENES = {
    kitchen: {
      name: '廚房看食譜', fg: 'youtube',
      setup: d => { Object.assign(d.st.yt, { title: '蔥油餅教學', t: 130, playing: true }); },
      steps: [
        { cap: '手上沾滿麵粉，食譜影片正在播放。最前面的視窗是 YouTube，AirTouch 自動進入 YouTube 模式。', wait: 2600 },
        { cap: '要先揉麵團：手掌張開維持 0.5 秒，進度環填滿就暫停。', g: 'open_palm', hold: 1.0, act: ['play_pause'] },
        { cap: '揉好了，再比一次手掌張開，影片繼續播放。', g: 'open_palm', hold: 1.0, act: ['play_pause'] },
        { cap: '剛剛的步驟沒看清楚：食指向左 0.35 秒，倒退 10 秒。', g: 'point_left', hold: 0.8, act: ['seek_back', 10] },
        { cap: '抽油煙機很吵：大拇指朝上，比著不放會一直調大音量。', g: 'thumb_up', hold: 1.4, act: ['volume_up', 1], times: 5 },
        { cap: '廣告出現了，等到畫面出現「略過」按鈕……', run: d => { d.st.yt.ad = true; }, wait: 2000 },
        { cap: '比剪刀手 0.6 秒：程式在畫面上找到「略過」按鈕，才代替你按下去。', g: 'v_sign', hold: 1.1, act: ['skip_ad'] },
        { cap: '想換一道菜，直接說「換播 蛋餅教學」：舊分頁關掉，新影片開始播放。', voice: '換播 蛋餅教學' },
        { cap: '要去洗手了：握拳 1.5 秒鎖定手勢，之後擦手、揮手都不會誤觸。', g: 'fist', hold: 2.0, act: ['lock'] },
        { cap: '鎖定中比手掌張開，進度環不會動，也不會暫停（狀態列變紅）。', g: 'open_palm', hold: 1.4 },
      ],
    },
    slides: {
      name: '上台簡報', fg: 'powerpoint',
      setup: d => { d.st.ppt.idx = 1; },
      steps: [
        { cap: '上台前 PowerPoint 還在編輯畫面。切到 PowerPoint 視窗，AirTouch 自動換成簡報模式。', wait: 2600 },
        { cap: '說「開始放映」，從第 1 頁開始。', voice: '開始放映' },
        { cap: '食指向右 0.35 秒換下一頁；比著不放，每 1.2 秒再換一頁。', g: 'point_right', hold: 1.9, act: ['next_page'], times: 2 },
        { cap: '比剪刀手 0.8 秒，換成雷射筆指重點。', g: 'v_sign', hold: 1.3, act: ['laser'] },
        { cap: '評審問到結論：說「跳到結論那頁」，程式找投影片標題直接跳過去。', voice: '跳到結論那頁' },
        { cap: '講者按 n，懸浮視窗顯示這頁的備忘稿，不用回頭看螢幕。', run: d => { d.st.notes = true; }, wait: 2800 },
        { cap: '進入討論：手掌張開 0.8 秒變黑畫面，大家看著講者。', g: 'open_palm', hold: 1.3, act: ['black_screen'] },
        { cap: '再比一次，恢復投影片。', g: 'open_palm', hold: 1.3, act: ['black_screen'] },
        { cap: '簡報模式沒有「快轉」：說了也只會提示，不會亂按鍵。', voice: '快轉20秒' },
        { cap: '說「結束放映」回到編輯畫面。', voice: '結束放映' },
      ],
    },
    meeting: {
      name: '線上會議', fg: 'teams',
      setup: d => { Object.assign(d.st.meet, { mic: false, cam: true, hand: false }); },
      steps: [
        { cap: '會議剛開始，麥克風是關的。最前面的視窗是 Teams，AirTouch 自動進入會議模式。', wait: 2600 },
        { cap: '輪到我發言：手掌張開維持 1 秒打開麥克風。會議模式故意設得比較久，避免誤開。', g: 'open_palm', hold: 1.6, act: ['mic_toggle'] },
        { cap: '講完了，說「靜音」。會議模式會把「靜音」換成「關麥克風」。', voice: '靜音' },
        { cap: '想提問：食指向右維持 1.2 秒，舉手。', g: 'point_right', hold: 1.8, act: ['raise_hand'] },
        { cap: '家人從後面經過：剪刀手 1 秒關鏡頭。', g: 'v_sign', hold: 1.6, act: ['camera_toggle'] },
        { cap: '窗外很吵，想關電腦喇叭：要說「電腦靜音」。', voice: '電腦靜音' },
        { cap: '手掌只比 0.6 秒就放下：進度環沒填滿，麥克風不會被打開。', g: 'open_palm', hold: 0.6 },
      ],
    },
  };

  const sceneRoot = document.getElementById('at-scenes');
  if (sceneRoot) {
    const tabs = el('div', 'sim-tabs');
    tabs.setAttribute('role', 'tablist');
    tabs.setAttribute('aria-label', '選擇情境');
    const stage = el('div');
    const caption = el('p', 'scene-caption');
    caption.setAttribute('aria-live', 'polite');
    const bar = el('div', 'scene-bar');
    const prevB = el('button', 'sim-chip', '⏮ 上一步');
    const playB = el('button', 'sim-chip primary', '▶ 播放');
    const nextB = el('button', 'sim-chip', '下一步 ⏭');
    const stepT = el('span', 'scene-step');
    [prevB, playB, nextB].forEach(b => { b.type = 'button'; });
    const dots = el('div', 'scene-dots');
    dots.setAttribute('aria-hidden', 'true');
    bar.append(prevB, playB, nextB, stepT, dots);
    sceneRoot.append(tabs, stage, caption, bar);
    const dev = createDevice(stage, null);

    let scene = 'kitchen', index = 0, playing = false, token = 0;
    const tabBtns = {};
    Object.entries(SCENES).forEach(([k, s]) => {
      const b = el('button', 'sim-tab', esc(s.name));
      b.type = 'button';
      b.setAttribute('role', 'tab');
      b.addEventListener('click', () => { stop(); scene = k; jump(0); });
      tabBtns[k] = b;
      tabs.append(b);
    });

    const sleep = (ms, my) => new Promise(resolve => {
      const end = performance.now() + ms;
      const check = () => {
        if (my !== token) return resolve(false);
        if (performance.now() >= end) return resolve(true);
        setTimeout(check, 40);
      };
      check();
    });

    function prepare() {
      dev.reset();
      const s = SCENES[scene];
      dev.st.fg = s.fg;
      dev.setProfileNow(matchProfile(TITLES[s.fg]));
      s.setup(dev);
      dev.toast = { text: `情境：${s.name}`, ok: true };
    }

    function applyInstant(step) {
      if (step.run) step.run(dev);
      if (step.voice) dev.voice(step.voice);
      if (step.act) for (let i = 0; i < (step.times || 1); i++) dev.execute(step.act[0], step.act[1] ?? null, 'gesture', G_NAME[step.g]);
    }

    function show() {
      const steps = SCENES[scene].steps;
      Object.entries(tabBtns).forEach(([k, b]) => b.setAttribute('aria-selected', String(k === scene)));
      caption.textContent = steps[index].cap;
      stepT.textContent = `第 ${index + 1}／${steps.length} 步`;
      dots.innerHTML = steps.map((_, i) => `<i class="${i === index ? 'on' : i < index ? 'done' : ''}"></i>`).join('');
      prevB.disabled = index === 0;
      nextB.disabled = index >= steps.length - 1;
      playB.textContent = playing ? '⏸ 暫停' : (index >= steps.length - 1 ? '↻ 重新播放' : '▶ 播放');
    }

    function jump(i) {
      token++;
      prepare();
      const steps = SCENES[scene].steps;
      index = Math.max(0, Math.min(steps.length - 1, i));
      for (let k = 0; k < index; k++) applyInstant(steps[k]);
      dev.release();
      show();
    }

    async function runStep(step, my) {
      if (step.wait) return sleep(step.wait, my);
      if (!(await sleep(900, my))) return false;
      if (step.run) step.run(dev);
      if (step.g) {
        dev.hold(step.g);
        const ok = await sleep(step.hold * 1000, my);
        dev.release();
        if (!ok) return false;
        return sleep(1300, my);
      }
      if (step.voice) {
        dev.say(step.voice, 2200);
        if (!(await sleep(1100, my))) return false;
        dev.voice(step.voice);
        return sleep(1800, my);
      }
      return sleep(1500, my);
    }

    async function play() {
      const steps = SCENES[scene].steps;
      if (index >= steps.length - 1) jump(0);
      playing = true;
      const my = ++token;
      // 重新整理目前步驟之前的狀態，再從目前步驟開始播放
      prepare();
      for (let k = 0; k < index; k++) applyInstant(steps[k]);
      show();
      while (index < steps.length) {
        show();
        if (!(await runStep(steps[index], my))) return;
        if (index >= steps.length - 1) break;
        index++;
      }
      playing = false;
      show();
    }

    function stop() { if (playing) { playing = false; token++; dev.release(); show(); } }

    playB.addEventListener('click', () => { if (playing) stop(); else play(); });
    prevB.addEventListener('click', () => { stop(); jump(index - 1); });
    nextB.addEventListener('click', () => { stop(); jump(index + 1); });
    jump(0);

    if (!REDUCED) {
      const io = new IntersectionObserver(es => {
        if (es.some(e => e.isIntersecting)) { io.disconnect(); if (!playing && index === 0) play(); }
      }, { threshold: 0.5 });
      io.observe(sceneRoot);
    }
  }
})();
