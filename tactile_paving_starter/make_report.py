"""步驟 5：把 output/events.csv 整理成一頁報表（output/report.html），可給總務處或放進書面報告。

用法：python make_report.py
      python make_report.py --dir output_demo
"""
import argparse
import csv
import html
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="output", help="paving_monitor.py 的輸出資料夾")
    args = parser.parse_args()
    OUT = args.dir if os.path.isabs(args.dir) else os.path.join(HERE, args.dir)
    path = os.path.join(OUT, "events.csv")
    if not os.path.exists(path):
        raise SystemExit(f"找不到 {path}，請先執行 paving_monitor.py")
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    total_sec = sum(float(r["duration_sec"]) for r in rows)
    by_cause = Counter()
    by_hour = Counter()
    for r in rows:
        for c in (r["cause"] or "unknown").split("+"):
            by_cause[c] += 1
        start = r["start"]
        if len(start) >= 13 and start[4] == "-":  # 攝影機模式：2026-09-16 14:05:00
            by_hour[start[11:13] + ":00"] += 1

    label = {"motorcycle": "機車", "bicycle": "腳踏車", "car": "汽車", "truck": "貨車",
             "bus": "公車", "blocked": "雜物遮擋", "unknown": "未知"}
    e = html.escape

    def bar_rows(counter, keys):
        top = max(counter.values()) if counter else 1
        out = []
        for k in keys:
            n = counter[k]
            out.append(f'<tr><th scope="row">{e(label.get(k, k))}</th><td>{n}</td>'
                       f'<td><div class="bar" style="width:{n / top * 100:.0f}%"></div></td></tr>')
        return "\n".join(out)

    def event_row(r):
        causes = "、".join(label.get(c, c) for c in r["cause"].split("+"))
        snap = '<a href="{0}">查看</a>'.format(e(r["snapshot"])) if r["snapshot"] else "—"
        cells = [e(r["event_id"]), e(r["start"]), e(r["end"]), e(r["duration_sec"]), e(causes), snap]
        return "<tr>" + "".join("<td>" + c + "</td>" for c in cells) + "</tr>"

    event_rows = "\n".join(event_row(r) for r in rows)

    hour_html = ""
    if by_hour:
        hour_html = f"""<h2>各時段事件數</h2>
<table><thead><tr><th scope="col">時段</th><th scope="col">件數</th><th scope="col"><span class="sr">比例</span></th></tr></thead>
<tbody>{bar_rows(by_hour, sorted(by_hour))}</tbody></table>"""

    page = f"""<!DOCTYPE html>
<html lang="zh-Hant-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>導盲磚占用紀錄報表</title>
<style>
body{{font-family:"Noto Sans TC","Microsoft JhengHei",sans-serif;margin:0;padding:24px;color:#0f172a;background:#f8fafc;line-height:1.6}}
main{{max-width:960px;margin:auto}}
.cards{{display:flex;flex-wrap:wrap;gap:12px}}
.card{{background:#fff;border:1px solid #cbd5e1;border-radius:10px;padding:12px 18px;min-width:160px}}
.card b{{display:block;font-size:1.8rem;color:#0369a1}}
table{{border-collapse:collapse;width:100%;background:#fff;margin:8px 0 24px}}
th,td{{border:1px solid #cbd5e1;padding:6px 10px;text-align:left}}
thead th{{background:#e2e8f0}}
.bar{{height:14px;background:#0369a1;border-radius:3px;min-width:2px}}
.sr{{position:absolute;left:-9999px}}
a{{color:#0369a1}}
</style></head><body><main>
<h1>導盲磚占用紀錄報表</h1>
<div class="cards">
<div class="card">事件數<b>{len(rows)}</b></div>
<div class="card">占用總時間<b>{total_sec / 60:.1f} 分</b></div>
<div class="card">平均每件<b>{(total_sec / len(rows) if rows else 0):.0f} 秒</b></div>
</div>
<h2>占用原因</h2>
<table><thead><tr><th scope="col">原因</th><th scope="col">件數</th><th scope="col"><span class="sr">比例</span></th></tr></thead>
<tbody>{bar_rows(by_cause, [k for k, _ in by_cause.most_common()])}</tbody></table>
{hour_html}
<h2>事件明細</h2>
<table><thead><tr><th scope="col">編號</th><th scope="col">開始</th><th scope="col">結束</th><th scope="col">秒數</th><th scope="col">原因</th><th scope="col">截圖</th></tr></thead>
<tbody>{event_rows}</tbody></table>
<p>截圖已模糊行人與車牌位置。本報表僅供改善導盲設施使用。</p>
</main></body></html>"""
    out = os.path.join(OUT, "report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print("報表已產生：", out)


if __name__ == "__main__":
    main()
