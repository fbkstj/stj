"""L3 通報分級、緊急重送、斷網補送（F4；T5、T14）。"""
import re
import unittest

from helpers import FailingTransport, TempDir, make_app
from core.events import Event
from core.notify import DryRunTransport


class TestNotify(unittest.TestCase):
    def test_three_levels_format(self):
        with TempDir() as tmp:
            t = DryRunTransport(echo=False)
            app = make_app(tmp, transport=t)
            for level in ("info", "warn", "urgent"):
                app.bus.publish(Event("care", "test", level, "測試"))
            texts = [x["text"] for x in t.sent]
            self.assertTrue(texts[0].startswith("ℹ️"))
            self.assertTrue(texts[1].startswith("⚠️ 注意"))
            self.assertIn("@everyone", texts[2])
            self.assertIn("長照監護", texts[0])

    def test_skip_kinds(self):
        with TempDir() as tmp:
            t = DryRunTransport(echo=False)
            app = make_app(tmp, transport=t)
            app.bus.publish(Event("care", "activity", "info", "偵測到活動"))
            self.assertEqual(t.sent, [])
            self.assertEqual(app.store.count(kind="activity"), 1)     # 不送 Discord，但有存紀錄

    def test_urgent_repeats_until_ack(self):
        with TempDir() as tmp:
            t = DryRunTransport(echo=False)
            app = make_app(tmp, transport=t)
            app.bus.publish(Event("care", "fall", "urgent", "跌倒"))
            for _ in range(16):                          # 每分鐘檢查一次，共 16 分鐘
                app.clock.advance(minutes=1)
                app.notifier.tick()
            urgent = [x for x in t.sent if "緊急" in x["text"]]
            self.assertEqual(len(urgent), 4)            # 第 0、5、10、15 分鐘
            alert_id = app.notifier.open_alerts()[0]["id"]
            self.assertTrue(app.notifier.ack(alert_id, "測試"))
            for _ in range(5):
                app.clock.advance(minutes=5)
                app.notifier.tick()
            self.assertEqual(len([x for x in t.sent if "緊急" in x["text"] and "✅" not in x["text"]]), 4)

    def test_urgent_max_repeats(self):
        with TempDir() as tmp:
            t = DryRunTransport(echo=False)
            app = make_app(tmp, transport=t)
            app.bus.publish(Event("sos", "sos", "urgent", "求救"))
            for _ in range(20):
                app.clock.advance(minutes=5)
                app.notifier.tick()
            self.assertEqual(len(t.sent), app.settings["discord"]["urgent_repeat_max"])

    def test_offline_outbox_then_flush_in_order(self):
        with TempDir() as tmp:
            t = FailingTransport()
            app = make_app(tmp, transport=t)
            for i in range(3):
                app.bus.publish(Event("camera", "visit", "info", f"訪客{i}"))
                app.clock.advance(seconds=1)
            self.assertEqual(app.notifier.pending_count(), 3)
            t.online = True
            self.assertEqual(app.notifier.flush_outbox(), 3)
            self.assertEqual(app.notifier.pending_count(), 0)
            self.assertEqual([re.search(r"訪客\d", x["text"])[0] for x in t.sent], ["訪客0", "訪客1", "訪客2"])
            self.assertTrue(all("延遲送達" in x["text"] for x in t.sent))


if __name__ == "__main__":
    unittest.main()
