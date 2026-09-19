"""把 AirTouch 情境動畫與互動模擬器組進 airtouch_project_guide.html。

模擬器的手勢對應、秒數等設定直接讀 airtouch_starter/config.json，
所以程式包的設定改了之後，重新執行這支程式，網頁就會跟著更新。

用法（在 stjweb 資料夾）：
  python tools/airtouch_sim/build.py           更新手冊
  python tools/airtouch_sim/build.py --check   另外用 node 檢查 JS 與 Python 的語音解析結果是否一致

網頁中由這支程式產生的區塊都夾在 <!-- at-sim:… --> 註解之間，重跑時整段替換，不要手動修改。
"""
import csv
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STARTER = os.path.join(ROOT, "airtouch_starter")
GUIDE = os.path.join(ROOT, "airtouch_project_guide.html")
sys.path.insert(0, STARTER)

MARKUP = '''      <h3 id="simulate">情境動畫</h3>
      <p>先看三個情境怎麼運作。動畫會自動播放（電腦設定「減少動畫」時請按「播放」），也可以按「上一步／下一步」慢慢看。深藍色區塊是鏡頭畫面上的 AirTouch 懸浮視窗（手勢、進度環、狀態列），灰框是電腦螢幕。</p>
      <div class="sim" id="at-scenes">
        <noscript><p>情境動畫需要開啟 JavaScript。</p></noscript>
      </div>

      <h3>互動模擬器</h3>
      <p>自己動手試：先選「最前面的視窗」，再<strong>按住</strong>手勢按鈕（放開＝手放下；用鍵盤時按住空白鍵），或輸入一句話代替語音。可以觀察：</p>
      <ul>
        <li>進度環要填滿才觸發；還沒填滿就放開，什麼都不會發生。</li>
        <li>大拇指、食指按住不放，會連續觸發；手掌張開要放開再按才會再觸發一次。</li>
        <li>按住「握拳」1.5 秒會鎖定，狀態列變紅，其他手勢都沒反應；再按住一次解鎖。</li>
        <li>換到記事本時，模式不會變；在簡報模式說「快轉」，只會提示「沒有這個功能」。</li>
        <li>會議模式說兩次「靜音」：快捷鍵是「切換」，第二次會把麥克風打開。</li>
      </ul>
      <div class="sim" id="at-sim">
        <noscript><p>互動模擬器需要開啟 JavaScript。</p></noscript>
      </div>
      <div class="note tip">
        <strong>模擬器和程式包用同一套規則</strong>
        手勢對應、維持秒數、重複間隔、冷卻、手勢鎖都讀自程式包的 <code>config.json</code>；語音解析的比對順序與 <code>voice_commands.py</code> 相同。網頁只改變畫面上的模擬螢幕，不會操作你的電腦；真正的手勢辨識要用程式包加上鏡頭。
      </div>
'''

# 第一次組裝時對手冊做的文字修改（已經改過就略過）
ONE_TIME = [
    ('<h2><span class="num">2</span>系統架構</h2>', '<h2><span class="num">2</span>系統架構與情境模擬</h2>'),
    ('      <li><a href="#layout">系統架構</a></li>', '      <li><a href="#layout">系統架構與情境模擬</a></li>'),
    ('      <a class="btn btn-ghost" href="#design">看功能設計</a>',
     '      <a class="btn btn-ghost" href="#simulate">看情境模擬</a>\n      <a class="btn btn-ghost" href="#design">看功能設計</a>'),
    ('        <li>說「會議模式」時，程式會看 Teams、Zoom、Meet 哪一個的視窗有開，就切到那一個。</li>',
     '        <li>說「會議模式」時，程式會看 Teams、Zoom、Meet 哪一個的視窗有開，就切到那一個。</li>\n'
     '        <li><strong>快捷鍵是「切換」</strong>：程式不知道麥克風現在是開還是關，原本就靜音時說「靜音」，反而會打開麥克風。請看會議視窗的圖示確認，或在報告中討論怎麼改良（例如讀取會議軟體的狀態）。</li>'),
]


def hand_poses():
    import make_demo_samples as m
    defs = {
        "open_palm": (m.hand([1, 1, 1, 1], True), 0),
        "v_sign": (m.hand([1, 1, 0, 0], False, {"index": -12, "middle": 10}), 0),
        "fist": (m.hand([0, 0, 0, 0], False), 0),
        "point_right": (m.hand([1, 0, 0, 0], False, {"index": 0}), -90),
        "point_left": (m.hand([1, 0, 0, 0], False, {"index": 0}), 90),
        "none": (m.hand([1, 1, 1, 0], False), 0),
    }
    pts = {k: m.rotate(p, a) for k, (p, a) in defs.items()}
    for name, target in (("thumb_up", 90), ("thumb_down", -90)):
        p = m.hand([0, 0, 0, 0], True)
        d = p[4] - p[2]
        pts[name] = m.rotate(p, target - math.degrees(math.atan2(-d[1], d[0])))
    out = {}
    for name, p in pts.items():
        lo, hi = p.min(0), p.max(0)
        q = (p - (lo + hi) / 2) / max(hi - lo) * 84 + 50
        out[name] = [[round(float(x), 1), round(float(y), 1)] for x, y in q]
    return out


def slim_config():
    with open(os.path.join(STARTER, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    keep = ("name", "window", "keys", "gestures", "voice_map", "seek", "skip_ad", "goto")
    return {
        "lock_hold_sec": cfg["lock_hold_sec"],
        "cooldown_sec": cfg["cooldown_sec"],
        "meeting_profiles": cfg["meeting_profiles"],
        "profiles": {k: {kk: v[kk] for kk in keep if kk in v} for k, v in cfg["profiles"].items()},
    }


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def put_block(s, name, content, anchor, before=True):
    """把 <!-- at-sim:name --> 區塊換成新內容；還沒有區塊時插在 anchor 前（或後）。"""
    start, end = f"<!-- at-sim:{name} -->", f"<!-- /at-sim:{name} -->"
    block = f"{start}\n{content}{end}\n"
    if start in s:
        return re.sub(re.escape(start) + r".*?" + re.escape(end) + r"\n?", lambda _: block, s, flags=re.S)
    assert s.count(anchor) == 1, f"找不到插入位置：{anchor[:40]}"
    return s.replace(anchor, block + anchor if before else anchor + block)


def check_parser():
    import voice_commands
    with open(os.path.join(STARTER, "voice_test_phrases.csv"), encoding="utf-8-sig") as f:
        texts = [r["text"] for r in csv.DictReader(f)]
    texts += ["快轉兩分鐘三十秒", "換聽告五人的MV", "跳到第二十三頁", "切換成Zoom模式", "跳到 預算 那一頁", "跳到30秒", ""]
    js = ("const p=require(process.argv[1]);const t=JSON.parse(require('fs').readFileSync(0,'utf8'));"
          "process.stdout.write(JSON.stringify(t.map(x=>p(x))))")
    r = subprocess.run(["node", "-e", js, os.path.join(HERE, "voice_parse.js")], input=json.dumps(texts),
                       capture_output=True, text=True, encoding="utf-8", check=True)
    bad = [(t, a, b) for t, a, b in zip(texts, (voice_commands.parse(t) for t in texts), json.loads(r.stdout)) if a != b]
    print(f"語音解析比對 {len(texts)} 句，不一致 {len(bad)} 句")
    for t, a, b in bad:
        print("  ", t, "Python:", a, "JS:", b)
    return not bad


def main():
    with open(GUIDE, encoding="utf-8") as f:
        s = f.read()
    for old, new in ONE_TIME:
        if new not in s and old in s:
            s = s.replace(old, new)

    css = read("sim.css")
    parse_js = read("voice_parse.js").replace("if (typeof module !== 'undefined') module.exports = VoiceParse;\n", "")
    data = ('<script type="application/json" id="at-config">'
            + json.dumps(slim_config(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>\n"
            + '<script type="application/json" id="at-poses">'
            + json.dumps(hand_poses(), separators=(",", ":")) + "</script>\n"
            + "<script>\n" + parse_js + read("sim.js") + "</script>\n")

    s = put_block(s, "css", "<style>\n" + css + "</style>\n", "</head>")
    i = s.index('<section id="layout">')
    j = s.index("    </section>", i)
    if "<!-- at-sim:markup -->" in s:
        s = put_block(s, "markup", MARKUP, "")
    else:
        s = s[:j] + "<!-- at-sim:markup -->\n" + MARKUP + "<!-- /at-sim:markup -->\n" + s[j:]
    s = put_block(s, "script", data, "</body>")

    with open(GUIDE, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    print("已更新", os.path.relpath(GUIDE, ROOT))
    if "--check" in sys.argv and not check_parser():
        sys.exit(1)


if __name__ == "__main__":
    main()
