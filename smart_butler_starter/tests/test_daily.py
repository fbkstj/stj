"""L11 每日平安回報（F12；T11）：摘要數字要和資料庫一致。"""
import unittest
from datetime import datetime, timedelta

from helpers import TempDir, make_app
from core.clock import TAIPEI, iso
from core.events import Event
from modules.daily.module import DailyModule
from modules.daily.summary import collect, format_summary


def put(app, hour, minute, source, kind, level, msg, **data):
    t = datetime(2026, 9, 1, hour, minute, tzinfo=TAIPEI)
    app.bus.publish(Event(source, kind, level, msg, data=data, time=iso(t)))


class TestDaily(unittest.TestCase):
    def fill(self, app):
        put(app, 7, 5, "care", "activity", "info", "偵測到活動")
        put(app, 8, 0, "meds", "meds_remind", "info", "提醒", dose="血壓藥", due="2026-09-01T08:00:00+08:00")
        put(app, 8, 10, "meds", "meds_taken", "info", "已服藥", dose="血壓藥", due="2026-09-01T08:00:00+08:00", status="準時")
        put(app, 12, 30, "meds", "meds_remind", "info", "提醒", dose="胃藥", due="2026-09-01T12:30:00+08:00")
        put(app, 13, 0, "meds", "meds_overdue", "warn", "逾時", dose="胃藥", due="2026-09-01T12:30:00+08:00")
        put(app, 14, 0, "camera", "visit", "info", "有訪客")
        put(app, 16, 0, "camera", "visit", "info", "有訪客")
        put(app, 17, 0, "care", "fall", "urgent", "跌倒")
        put(app, 19, 40, "chat", "device", "info", "客廳燈已打開")
        put(app, 21, 0, "care", "activity", "info", "明天才算")    # 20:00 之後，不算在內

    def test_counts(self):
        with TempDir() as tmp:
            app = make_app(tmp)
            self.fill(app)
            until = datetime(2026, 9, 1, 20, 0, tzinfo=TAIPEI)
            s = collect(app.store, until.date(), until)
            self.assertEqual((s["meds_ontime"], s["meds_late"], s["meds_missed"]), (1, 0, 1))
            self.assertEqual(s["visits"], 2)
            self.assertEqual((s["warn"], s["urgent"]), (1, 1))
            self.assertEqual(f"{s['first_activity']:%H:%M}～{s['last_activity']:%H:%M}", "07:05～19:40")
            text = format_summary(s)
            self.assertTrue(text.startswith("⚠️ 今天有緊急事件 1 件、漏服藥 1 次"))
            self.assertIn("胃藥 12:30", text)

    def test_module_sends_once_at_time(self):
        with TempDir() as tmp:
            app = make_app(tmp, start=datetime(2026, 9, 1, 19, 58, tzinfo=TAIPEI))
            self.fill(app)
            m = DailyModule(app)
            m.setup()
            for _ in range(10):
                app.clock.advance(minutes=1)
                m.step()
            self.assertEqual(app.store.count(kind="daily_summary"), 1)

    def test_started_after_time_does_not_send_today(self):
        with TempDir() as tmp:
            app = make_app(tmp, start=datetime(2026, 9, 1, 22, 0, tzinfo=TAIPEI))
            m = DailyModule(app)
            m.setup()
            m.step()
            self.assertEqual(app.store.count(kind="daily_summary"), 0)
            app.clock.advance(minutes=60 * 22 + 1)          # 隔天 20:01
            m.step()
            self.assertEqual(app.store.count(kind="daily_summary"), 1)


if __name__ == "__main__":
    unittest.main()
