"""L9 本機管理介面（Flask）：只綁定 127.0.0.1，別台電腦連不進來。

頁面：儀表板、和管家說話、訪客查詢、留言板、事件紀錄（可匯出 CSV）、設定。
設定頁存檔前會用 core/config.py 檢查；.env 不會顯示也不能編輯。
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_file, url_for

from core import config as cfgmod
from core.clock import TAIPEI, iso
from core.events import LEVEL_NAMES
from modules.camera.visits import visits as query_visits
from modules.daily.summary import day_range

LOCAL = {"127.0.0.1", "::1"}

# 設定頁可以編輯的欄位：(欄位, 顯示名稱, 型別)
EDITABLE = [
    ("system.privacy_mode", "隱私模式（不存影像與對話）", bool),
    ("system.retention_days", "資料保存天數", int),
    ("system.voice", "用語音念出提醒", bool),
    ("discord.dry_run", "Discord 模擬模式（不真的送出）", bool),
    ("discord.urgent_repeat_min", "緊急通報重送間隔（分鐘）", float),
    ("care.fall_sec", "倒地幾秒算跌倒", float),
    ("care.inactive_min", "幾分鐘沒動算久未活動", float),
    ("camera.merge_gap_sec", "來訪合併間隔（秒）", float),
    ("camera.night_start", "深夜開始（HH:MM）", str),
    ("camera.night_end", "深夜結束（HH:MM）", str),
    ("meds.timeout_min", "吃藥逾時分鐘", float),
    ("daily.time", "每日平安回報時間（HH:MM）", str),
    ("routine.wake_tolerance_min", "起床容許分鐘", float),
] + [(f"modules.{m}", f"模組開關：{m}", bool) for m in cfgmod.MODULE_NAMES]


def create_app(app, supervisor=None, health=None, settings_path: Path | None = None) -> Flask:
    web = Flask(__name__)
    web.secret_key = "local-only-flash-key"     # 只用於本機提示訊息，不是金鑰
    web.jinja_env.globals.update(LEVEL_NAMES=LEVEL_NAMES, system_name=app.settings["system"]["name"])
    settings_path = settings_path or cfgmod.SETTINGS_PATH

    @web.before_request
    def local_only():
        if request.remote_addr not in LOCAL:
            abort(403)

    def module(name):
        return app.modules.get(name)

    @web.context_processor
    def common():
        return {"privacy": app.privacy, "demo": app.demo, "open_alerts": app.notifier.open_alerts()}

    @web.route("/")
    def dashboard():
        start, end = day_range(app.clock.now().date())
        status = supervisor.status() if supervisor else []
        meds = module("meds").today() if module("meds") and hasattr(module("meds"), "scheduler") else []
        return render_template("dashboard.html", status=status, meds=meds,
                               events=app.store.query(limit=20, newest_first=True),
                               visits_today=app.store.count(start, end, kind="visit"),
                               taken_today=app.store.count(start, end, kind="meds_taken"),
                               pending=app.notifier.pending_count(),
                               health=health.last if health else {})

    @web.post("/ack/<int:alert_id>")
    def ack(alert_id):
        flash("已標記為處理完畢" if app.notifier.ack(alert_id, "管理介面") else "這則通報已經處理過了")
        return redirect(request.referrer or url_for("dashboard"))

    @web.post("/meds/confirm")
    def meds_confirm():
        m = module("meds")
        flash(m.confirm("管理介面") if m else "用藥提醒模組沒有開啟")
        return redirect(url_for("dashboard"))

    @web.post("/sos")
    def sos():
        m = module("sos")
        if not m:
            flash("一鍵求救模組沒有開啟")
        else:
            ok = m.trigger("管理介面")
            flash(f"已送出緊急通報（{m.last_latency_ms} 毫秒）" if ok else "剛剛已經送出過，10 秒內不重複送")
        return redirect(url_for("dashboard"))

    @web.post("/privacy")
    def privacy():
        new = not app.privacy
        errors = cfgmod.save_changes({"system.privacy_mode": new}, settings_path)
        if errors:
            flash("存檔失敗：" + "；".join(errors))
        else:
            app.settings["system"]["privacy_mode"] = new
            flash("隱私模式已開啟：不再儲存影像與對話" if new else "隱私模式已關閉")
        return redirect(request.referrer or url_for("dashboard"))

    @web.route("/chat", methods=["GET", "POST"])
    def chat():
        m = module("chat")
        log = []
        if request.method == "POST" and m:
            text = request.form.get("text", "")
            log = [("你", text), ("管家", m.handle(text))]
        return render_template("chat.html", enabled=m is not None, log=log)

    @web.route("/visits")
    def visits():
        now = app.clock.now()
        start = request.args.get("start") or (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
        end = request.args.get("end") or (now + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")
        try:
            s = datetime.fromisoformat(start).replace(tzinfo=TAIPEI)
            e = datetime.fromisoformat(end).replace(tzinfo=TAIPEI)
        except ValueError:
            flash("時間格式不正確")
            return redirect(url_for("visits"))
        rows = query_visits(app.store, s, e)
        for r in rows:
            r["img"] = Path(r["snapshot"]).name if r["snapshot"] else None
        return render_template("visits.html", rows=rows, start=start, end=end)

    @web.route("/snapshots/<name>")
    def snapshot(name):
        path = (app.snapshot_dir / name).resolve()
        if path.parent != app.snapshot_dir.resolve() or not path.exists():
            abort(404)
        return send_file(path, mimetype="image/jpeg")

    @web.route("/board", methods=["GET", "POST"])
    def board():
        m = module("board")
        if request.method == "POST" and m:
            try:
                m.post(request.form.get("author", ""), request.form.get("text", ""))
                flash("留言已送出")
            except ValueError as e:
                flash(str(e))
            return redirect(url_for("board"))
        return render_template("board.html", enabled=m is not None, rows=m.list(50) if m else [])

    @web.route("/events")
    def events():
        level = request.args.get("level") or None
        source = request.args.get("source") or None
        rows = app.store.query(level=level, source=source, limit=200, newest_first=True)
        sources = sorted({r["source"] for r in app.store.fetch_all("SELECT DISTINCT source FROM events")})
        return render_template("events.html", rows=rows, level=level, source=source, sources=sources)

    @web.route("/events.csv")
    def events_csv():
        tmp = app.data_dir / "export_events.csv"
        app.store.export_csv(tmp, level=request.args.get("level") or None, source=request.args.get("source") or None)
        data = io.BytesIO(tmp.read_bytes())
        tmp.unlink()
        return send_file(data, mimetype="text/csv", as_attachment=True,
                         download_name=f"events_{app.clock.now():%Y%m%d_%H%M}.csv")

    @web.route("/settings", methods=["GET", "POST"])
    def settings_page():
        errors = []
        if request.method == "POST":
            changes = {}
            for key, _, typ in EDITABLE:
                if typ is bool:
                    changes[key] = key in request.form
                    continue
                raw = request.form.get(key, "").strip()
                try:
                    if typ is float:
                        v = float(raw)
                        changes[key] = int(v) if v.is_integer() else v   # 30.0 存成 30
                    else:
                        changes[key] = int(raw) if typ is int else raw
                except ValueError:
                    errors.append(f"{key} 要填數字（收到「{raw}」）")
            if not errors:
                errors = cfgmod.save_changes(changes, settings_path)
            if not errors:
                for key, value in changes.items():       # 立即生效的部分（示範模式只同步隱私模式，其他保留示範值）
                    sect, name = key.split(".", 1)
                    if "." not in name and (not app.demo or key == "system.privacy_mode"):
                        app.settings[sect][name] = value
                flash("已存檔。模組開關、影像參數在重新啟動主程式後生效。")
                return redirect(url_for("settings_page"))
        current = cfgmod.load_settings(settings_path)
        fields = [(k, label, typ is bool, cfgmod.get_path(current, k)) for k, label, typ in EDITABLE]
        if errors:
            form = request.form
            fields = [(k, label, typ is bool, (k in form) if typ is bool else form.get(k, "")) for k, label, typ in EDITABLE]
        return render_template("settings.html", fields=fields, errors=errors)

    return web
