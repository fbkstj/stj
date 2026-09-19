// 語音指令解析（與程式包 voice_commands.py 相同的規則與順序）
const VoiceParse = (() => {
  const DIG = { 零: 0, 一: 1, 二: 2, 兩: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };
  const NUM = '(\\d+|[零一二兩三四五六七八九十]+)';
  const cnToInt = s => {
    if (/^\d+$/.test(s)) return parseInt(s, 10);
    if (s === '十') return 10;
    if (s.includes('十')) {
      const [a, b] = s.split('十');
      return (a ? (DIG[a] ?? 1) : 1) * 10 + (b ? (DIG[b] ?? 0) : 0);
    }
    return DIG[s] ?? 0;
  };
  const parseSeconds = (t, def = 10) => {
    let total = 0;
    let m = t.match(new RegExp(NUM + '\\s*(?:個)?(?:分鐘|分)(半)?'));
    if (m) total += cnToInt(m[1]) * 60 + (m[2] ? 30 : 0);
    else if (t.includes('半分鐘')) total += 30;
    m = t.match(new RegExp(NUM + '\\s*秒'));
    if (m) total += cnToInt(m[1]);
    if (total === 0) {
      m = t.match(new RegExp(NUM));
      if (m) total = cnToInt(m[1]);
    }
    return total > 0 ? total : def;
  };
  const parseSteps = (t, def = 3) => {
    const m = t.match(new RegExp(NUM + '\\s*(?:格|次|下)'));
    return m ? Math.max(1, Math.min(20, cnToInt(m[1]))) : def;
  };
  const has = (t, words) => words.some(w => t.includes(w));
  const L = {
    EXIT: ['關閉程式', '結束程式', '退出程式', '關掉程式', '離開程式'],
    LOCK: ['鎖定手勢', '暫停手勢', '關閉手勢', '停用手勢'],
    UNLOCK: ['解鎖手勢', '啟用手勢', '開啟手勢', '恢復手勢'],
    AUTO: ['自動切換', '自動模式', '自動偵測'],
    CLOSE: ['關閉這首', '關掉這首', '關閉影片', '關掉影片', '關閉音樂', '關掉音樂', '關閉分頁', '不要聽了', '別播了', '不要播了'],
    OPEN_YT: ['開啟yt', '打開yt', '開yt', '開啟youtube', '打開youtube', '開youtube'],
    SKIP: ['跳過廣告', '略過廣告', '跳廣告', '略過'],
    FULL: ['全螢幕', '全屏'], EXIT_FULL: ['離開全螢幕', '退出全螢幕'],
    NEXT: ['下一部', '下一首', '下一個影片', '下一支', '換一首', '換一部'],
    PREV_VIDEO: ['上一部', '上一首', '上一個影片', '上一支'],
    FASTER: ['加速', '播快一點', '快一點播', '速度加快'], SLOWER: ['減速', '播慢一點', '慢一點播', '速度放慢'],
    CAPTIONS: ['字幕'], VIDEO_MUTE: ['影片靜音', '影片取消靜音'],
    SYSTEM_MUTE: ['系統靜音', '電腦靜音'], MUTE: ['靜音', '取消靜音', '解除靜音'],
    VOL_UP: ['大聲', '音量調大', '提高音量', '增加音量', '音量大', '音量放大'],
    VOL_DOWN: ['小聲', '音量調小', '降低音量', '減少音量', '音量小', '音量縮小'],
    BACK: ['倒退', '後退', '往後', '倒轉', '退回'], FORWARD: ['快轉', '前進', '往前', '跳過'],
    PAUSE: ['暫停', '停一下', '停止播放', '先停'], PLAY: ['播放', '繼續', '開始播放'],
    START_HERE: ['從這頁放映', '從這頁開始', '從目前這頁', '從這張放映'],
    START_SHOW: ['開始放映', '放映簡報', '播放簡報', '開始簡報'],
    END_SHOW: ['結束放映', '停止放映', '離開放映', '結束簡報'],
    BLACK: ['黑畫面', '黑屏', '螢幕變黑', '畫面變黑'], WHITE: ['白畫面', '白屏', '螢幕變白', '畫面變白'],
    LASER: ['雷射筆', '雷射'], PEN: ['畫筆', '原子筆', '螢光筆'],
    ERASE: ['清除筆跡', '擦掉', '清除畫筆', '清掉筆跡'], ARROW: ['箭頭', '游標', '滑鼠指標'],
    LAST_PAGE: ['最後一頁', '最後一張', '最後頁'],
    NEXT_PAGE: ['下頁', '翻頁', '下一頁', '下一張', '後一頁', '後一張'],
    PREV_PAGE: ['上頁', '翻回去', '上一頁', '上一張', '前一頁', '前一張'],
    ZOOM_IN: ['放大', '拉近'], ZOOM_OUT: ['縮小', '拉遠'],
    FIT_PAGE: ['整頁', '符合頁面', '原始大小', '恢復大小'],
    MIC: ['麥克風'], CAMERA: ['鏡頭', '攝影機'], RAISE: ['舉手', '放下手'],
  };
  const ALIASES = [
    ['powerpoint', ['簡報', '投影片', 'powerpoint', 'ppt']], ['pdf', ['pdf', '文件', '閱讀']],
    ['teams', ['teams']], ['zoom', ['zoom']], ['meet', ['meet']], ['meeting', ['會議', '視訊']],
    ['youtube', ['youtube', 'yt', '影片', '影音']],
  ];
  const GENERIC = new Set(['影片', '音樂', '歌', '歌曲', '一下', '']);
  const clean = q => {
    q = q.trim().replace(/(?:的歌|的歌曲|的mv|mv|歌曲|音樂|影片)$/i, '').trim();
    return GENERIC.has(q) ? null : q;
  };
  const A = (action, arg = null) => ({ action, arg });

  return function parse(text, wake = '') {
    let t = (text || '').replace(/[\s，。！？、,.!?]/g, '');
    if (wake) {
      if (!t.startsWith(wake)) return null;
      t = t.slice(wake.length);
    }
    const tl = t.toLowerCase();
    if (!t) return null;
    if (has(t, L.EXIT)) return A('exit');
    if (has(t, L.LOCK)) return A('lock');
    if (has(t, L.UNLOCK)) return A('unlock');
    if (has(t, L.AUTO)) return A('auto_profile');
    let m = tl.match(/(?:切換到|切換成|換到|進入|改成|使用|開啟)?(.+?)模式/);
    if (m) for (const [name, words] of ALIASES) if (has(m[1], words)) return A('switch_profile', name);

    if (has(t, L.START_HERE)) return A('start_here');
    if (has(t, L.START_SHOW)) return A('start_show');
    if (has(t, L.END_SHOW)) return A('end_show');
    if (has(t, L.BLACK)) return A('black_screen');
    if (has(t, L.WHITE)) return A('white_screen');
    if (has(t, L.LASER)) return A('laser');
    if (has(t, L.PEN)) return A('pen');
    if (has(t, L.ERASE)) return A('erase_ink');
    if (has(t, L.ARROW)) return A('arrow_pointer');
    m = t.match(new RegExp('第' + NUM + '(?:頁|張)'));
    if (m && cnToInt(m[1]) > 0) return A('goto_page', cnToInt(m[1]));
    if (has(t, L.LAST_PAGE)) return A('last_page');
    if (has(t, L.NEXT_PAGE)) return A('next_page');
    if (has(t, L.PREV_PAGE)) return A('prev_page');
    m = t.match(/^(?:跳到|跳去|切到)(.+?)(?:那一?頁|那一?張|的投影片|投影片)?$/);
    if (m && !/\d|秒|分鐘|廣告/.test(m[1])) return A('goto_title', m[1]);
    if (has(t, L.FIT_PAGE)) return A('fit_page');

    if (has(t, L.MIC)) return A('mic_toggle');
    if (has(t, L.CAMERA)) return A('camera_toggle');
    if (has(t, L.RAISE)) return A('raise_hand');

    m = t.match(/(?:關閉這首|關掉這首)?(?:換播|換聽|換成|換一首|換開啟|換首)(.+)/);
    if (m && clean(m[1])) return A('play_song', { query: clean(m[1]), close_current: true });
    if (has(t, L.CLOSE)) return A('close_video');
    if (has(tl, L.OPEN_YT)) return A('open_youtube');
    if (has(t, L.SKIP) && !t.includes('秒')) return A('skip_ad');
    if (has(t, L.EXIT_FULL) || has(t, L.FULL)) return A('fullscreen');
    if (has(t, L.NEXT)) return A('next_video');
    if (has(t, L.PREV_VIDEO)) return A('prev_video');
    if (has(t, L.FASTER)) return A('speed_up');
    if (has(t, L.SLOWER)) return A('speed_down');
    if (has(t, L.CAPTIONS)) return A('captions');
    if (has(t, L.SYSTEM_MUTE)) return A('system_mute');
    if (has(t, L.VIDEO_MUTE)) return A('video_mute');
    if (has(t, L.MUTE)) return A('mute');
    if (has(t, L.VOL_UP)) return A('volume_up', parseSteps(t));
    if (has(t, L.VOL_DOWN)) return A('volume_down', parseSteps(t));
    if (has(t, L.ZOOM_IN)) return A('zoom_in');
    if (has(t, L.ZOOM_OUT)) return A('zoom_out');
    if (has(t, L.BACK)) return A('seek_back', parseSeconds(t));
    if (has(t, L.FORWARD)) return A('seek_forward', parseSeconds(t));
    if (has(t, L.PAUSE)) return A('play_pause');
    m = t.match(/^(?:我想聽|想聽|我要聽|點歌|點播|來一首|播一首|放一首|幫我播放?|播放|搜尋)(.+)/);
    if (m && clean(m[1])) return A('play_song', { query: clean(m[1]), close_current: false });
    if (has(t, L.PLAY)) return A('play_pause');
    return null;
  };
})();
if (typeof module !== 'undefined') module.exports = VoiceParse;
