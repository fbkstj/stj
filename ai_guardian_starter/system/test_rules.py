"""
不用攝影機的規則測試：用假的偵測結果檢查 threat_rules.py 和 alerter.py。
改了門檻或規則後執行一次，確認沒有改壞。

用法：python test_rules.py
"""
import sys
import tempfile
from pathlib import Path

import alerter as alerter_mod
from threat_rules import (CROWD_COUNT, LEVEL_HIGH, Detection, SustainedFlag,
                          ThreatAnalyzer)

passed = failed = 0


def check(name, ok):
    global passed, failed
    if ok:
        passed += 1
        print(f"  通過  {name}")
    else:
        failed += 1
        print(f"  失敗  {name}")


def person(x, y, w=80, h=200):
    return Detection(0, 0.9, (x, y, x + w, y + h))


def item(cls, x, y, conf=0.6):
    return Detection(cls, conf, (x, y, x + 30, y + 30))


def run(analyzer, frames, fps=10, start=0.0, frame_h=720):
    """frames：每一幀的偵測清單。回傳每幀的事件種類集合。"""
    out = []
    for i, dets in enumerate(frames):
        events, _ = analyzer.analyze(dets, start + i / fps, frame_h)
        out.append({e.kind for e in events})
    return out


print("1. SustainedFlag 持續判斷")
f = SustainedFlag(0.6, grace_sec=0.8)
check("剛出現不成立", not f.update(True, 0.0))
check("持續 0.6 秒成立", f.update(True, 0.6))
check("短暫消失 0.5 秒仍成立", f.update(False, 1.1) or f.update(True, 1.1))
f = SustainedFlag(0.6, grace_sec=0.8)
f.update(True, 0.0)
f.update(False, 1.0)
check("消失超過 0.8 秒就歸零", not f.update(True, 1.1))
f = SustainedFlag(0.6, grace_sec=0.8)
f.update(True, 0.0)
f.update(True, 0.3)
check("只出現 0.3 秒，容忍時間內也不成立", not f.update(False, 0.7))

# 關卡4、5 用的是上一層的 guard_core.py，規則要和這裡一致
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import guard_core
g = guard_core.SustainedFlag(0.6)
g.update(True, 0.0)
g.update(True, 0.3)
check("guard_core：物品消失時進度條停住", not g.update(False, 0.7) and abs(g.progress(0.7) - 0.5) < 1e-9)

print("2. 持械")
hand = [person(100, 100), item(76, 170, 150)]          # 剪刀在人框邊緣
res = run(ThreatAnalyzer(), [hand] * 10)
check("手持剪刀 0.5 秒內不觸發", not any("持械" in r for r in res[:6]))
check("手持剪刀 0.6 秒後觸發", "持械" in res[6])
desk = [person(100, 100), item(76, 600, 500)]          # 剪刀在遠處桌上
res = run(ThreatAnalyzer(), [desk] * 20)
check("剪刀放遠處桌上不觸發", not any("持械" in r for r in res))
flash = [hand] * 3 + [[person(100, 100)]] * 12        # 晃過鏡頭 0.3 秒
res = run(ThreatAnalyzer(), flash)
check("剪刀只晃過 0.3 秒不觸發", not any("持械" in r for r in res))
low = [person(100, 100), item(43, 170, 150, conf=0.2)]
res = run(ThreatAnalyzer(), [low] * 20)
check("信心度太低的刀不算", not any("持械" in r for r in res))

print("3. 倒地")
lying = [Detection(0, 0.9, (100, 400, 400, 520))]      # 寬 300、高 120
res = run(ThreatAnalyzer(), [lying] * 35)
check("躺臥 2.9 秒不觸發", "倒地" not in res[29])
check("躺臥 3 秒觸發", "倒地" in res[30])
res = run(ThreatAnalyzer(), [[person(100, 100)]] * 40)
check("站著的人不算倒地", not any("倒地" in r for r in res))

print("4. 人群奔逃")
def crowd_at(t, speed):
    # speed：每秒移動幾個畫面高（畫面高 720）
    return [person(100 + k * 200, 100 + speed * 720 * t) for k in range(3)]
res = run(ThreatAnalyzer(), [crowd_at(i / 10, 1.0) for i in range(15)])
check("3 人快速移動 1 秒後觸發", "奔逃" in res[11] or "奔逃" in res[12])
res = run(ThreatAnalyzer(), [crowd_at(i / 10, 0.2) for i in range(20)])
check("3 人慢慢走不觸發", not any("奔逃" in r for r in res))
two = [[person(100 + k * 300, 100 + 720 * i / 10) for k in range(2)] for i in range(20)]
res = run(ThreatAnalyzer(), two)
check("只有 2 人快速移動不觸發", not any("奔逃" in r for r in res))

print("5. 異常聚集")
many = [person(k * 40, 100) for k in range(CROWD_COUNT)]
res = run(ThreatAnalyzer(), [many] * 55)
check(f"{CROWD_COUNT} 人持續 5 秒觸發", "聚集" in res[50])
an = ThreatAnalyzer()
an.analyze(many, 0.0, 720)
levels = {e.kind: e.level for e in an.analyze(many, 5.0, 720)[0]}
check("聚集等級是「低」（只記錄）", levels.get("聚集") == "低")
res = run(ThreatAnalyzer(), [many[:-1]] * 60)
check(f"{CROWD_COUNT - 1} 人不觸發", not any("聚集" in r for r in res))

print("6. 通報流程（不發 LINE）")
tmp = Path(tempfile.mkdtemp())
alerter_mod.EVENT_DIR = tmp
alerter_mod.LINE_ENABLED = False
sent = []
alerter_mod.Alerter._send = lambda self, text: sent.append(text)
alerter_mod._beep = lambda: None
import numpy as np
from threat_rules import Event
frame = np.zeros((10, 10, 3), np.uint8)
a = alerter_mod.Alerter()
high = Event("持械", LEVEL_HIGH, "測試")
a.handle("前門", [high], frame, 100.0)
check("高風險事件先進入取消窗口", len(a.pending) == 1 and not sent)
a.tick(104.9)
check("5 秒內不送出", not sent)
a.tick(105.0)
check("5 秒到了送出緊急通報", len(sent) == 1 and "緊急通報" in sent[0])
a.handle("前門", [high], frame, 130.0)
check("60 秒冷卻內不重複通報", not a.pending)
a.handle("前門", [high], frame, 161.0)
a.cancel_all()
a.tick(170.0)
check("按 C 取消後不送出", len(sent) == 1)
rows = (tmp / "events.csv").read_text(encoding="utf-8-sig").splitlines()
check("events.csv 有 2 筆紀錄（通報、取消）", len(rows) == 3 and "取消" in rows[2])

print("7. 警示盒狀態與通訊格式")
from alarm_link import compute_state, parse_line, status_line
b = alerter_mod.Alerter()
check("平常是「監控中」S0N0", status_line(*compute_state(b, 0.0)) == "S0N0")
b.handle("穿堂", [high], frame, 200.0)
check("倒數剩 5 秒送 S2W5", status_line(*compute_state(b, 200.0)) == "S2W5")
check("倒數剩 0.3 秒時顯示 1", status_line(*compute_state(b, 204.7)) == "S2W1")
b.tick(205.0)
check("通報後 10 秒內是「已通報」S3W0", status_line(*compute_state(b, 206.0)) == "S3W0")
check("通報 10 秒後回到監控中", status_line(*compute_state(b, 215.1)) == "S0N0")
b.handle("穿堂", [Event("奔逃", LEVEL_HIGH, "測試")], frame, 300.0)
b.cancel_all(301.0)
check("取消後是「已取消」S4R0", status_line(*compute_state(b, 302.0)) == "S4R0")
b.handle("穿堂", [Event("倒地", "中", "測試")], frame, 400.0)
check("中風險事件是「注意」S1F0", status_line(*compute_state(b, 401.0)) == "S1F0")
b.handle("穿堂", [Event("倒地", "中", "測試")], frame, 420.0)
check("倒地一直持續（冷卻時間內）仍顯示「注意」", status_line(*compute_state(b, 422.0)) == "S1F0")
check("取消鈕訊息 K", parse_line("K\r") == "cancel" and parse_line("I,ready") == "ready"
      and parse_line("S2W5") is None)
check("秒數超過 9 以 9 表示、每行 4 個字元", status_line(2, "聚集", 12) == "S2C9")

print("8. 暫時修改門檻（--set）")
import threat_rules as tr
saved = tr.current_params()
name, value = tr.set_param("weapon_sustain_sec=2")
check("名稱不分大小寫、數值轉成小數", (name, value) == ("WEAPON_SUSTAIN_SEC", 2.0))
tr.set_param("PRACTICE_SCISSORS=false")
check("關掉練習模式後，剪刀不算危險物品", 76 not in tr.weapon_classes() and 76 not in tr.WEAPON_CLASSES)
try:
    tr.set_param("NO_SUCH=1")
    check("打錯名稱會停止", False)
except SystemExit:
    check("打錯名稱會停止", True)
for k, v in saved.items():
    tr.set_param(f"{k}={v}")
check("還原後剪刀又算危險物品", 76 in tr.WEAPON_CLASSES)

print("9. 評估工具（練習資料）")
import demo_scenes
import detlog
import evaluate
frames = demo_scenes.build_frames()
path = tmp / "demo_dets.csv"
detlog.write_dets(path, frames)
back = detlog.read_dets(path)
check("偵測紀錄存檔再讀回，時間點數量相同", len(back) == len(frames) == 1801)
truths = [{"kind": k, "start": s, "end": e, "note": n} for k, s, e, n in demo_scenes.TRUTH]
eps = evaluate.replay(back)
results, falses, repeats = evaluate.match(truths, eps)
total = evaluate.score(results, falses, evaluate.duration_min(back))
check("練習資料：6 件事偵測到 5 件", (total["events"], total["hits"]) == (6, 5))
check("練習資料：誤報 1 次（有人從桌上的剪刀旁走過）",
      len(falses) == 1 and falses[0]["kind"] == "持械" and 33 < falses[0]["start"] < 35)
check("練習資料：漏報的是遠處低信心度的剪刀", [r["start"] for r in results if not r["hit"]] == [152.0])
check("練習資料：平均反應 2.18 秒、重複警示 1 次",
      round(total["avg_latency"], 2) == 2.18 and repeats == 1)
tr.set_param("WEAPON_SUSTAIN_SEC=2")
_, falses2, _ = evaluate.match(truths, evaluate.replay(back))
tr.set_param("WEAPON_SUSTAIN_SEC=0.6")
check("持續秒數改 2 秒：誤報變 0 次", len(falses2) == 0)
tr.set_param("WEAPON_CONF=0.25")
r3, f3, _ = evaluate.match(truths, evaluate.replay(back))
tr.set_param("WEAPON_CONF=0.35")
check("信心度門檻改 0.25：6 件全抓到，但誤報變 2 次", sum(r["hit"] for r in r3) == 6 and len(f3) == 2)

print(f"\n結果：{passed} 項通過，{failed} 項失敗")
raise SystemExit(1 if failed else 0)
