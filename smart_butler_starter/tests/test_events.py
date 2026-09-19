"""L2 事件匯流排與紀錄（F3）。"""
import csv
import unittest
from datetime import datetime, timedelta

from helpers import TempDir
from core.clock import TAIPEI, FakeClock
from core.events import Event, EventBus
from core.store import Store


class TestEvents(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(datetime(2026, 9, 1, 8, 0, tzinfo=TAIPEI))
        self.bus = EventBus(self.clock)

    def test_publish_subscribe_and_filter(self):
        got_all, got_fall = [], []
        self.bus.subscribe(got_all.append)
        self.bus.subscribe(got_fall.append, kinds=["fall"])
        self.bus.publish(Event("care", "fall", "urgent", "跌倒"))
        self.bus.publish(Event("meds", "meds_remind", "info", "吃藥"))
        self.assertEqual(len(got_all), 2)
        self.assertEqual([e.kind for e in got_fall], ["fall"])
        self.assertEqual(got_all[0].time, "2026-09-01T08:00:00+08:00")

    def test_bad_subscriber_does_not_block_others(self):
        got = []

        def broken(event):
            raise RuntimeError("故意出錯")
        self.bus.subscribe(broken)
        self.bus.subscribe(got.append)
        self.bus.publish(Event("care", "fall", "urgent", "跌倒"))
        self.assertEqual(len(got), 1)
        self.assertEqual(len(self.bus.errors), 1)

    def test_invalid_level(self):
        with self.assertRaises(ValueError):
            Event("care", "fall", "danger", "等級打錯")

    def test_store_query_and_csv(self):
        with TempDir() as tmp:
            store = Store(tmp / "aina.db")
            self.bus.subscribe(store.save_event)
            for i in range(5):
                self.bus.publish(Event("care" if i % 2 else "camera", "k", "info", f"事件{i}"))
                self.clock.advance(minutes=10)
            start = datetime(2026, 9, 1, 8, 15, tzinfo=TAIPEI)
            rows = store.query(start, start + timedelta(minutes=20))
            self.assertEqual([r["message"] for r in rows], ["事件2", "事件3"])
            self.assertEqual(len(store.query(source="care")), 2)
            n = store.export_csv(tmp / "out.csv")
            self.assertEqual(n, 5)
            raw = (tmp / "out.csv").read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))            # 有 BOM，Excel 不會亂碼
            with open(tmp / "out.csv", encoding="utf-8-sig") as f:
                self.assertEqual(next(csv.reader(f))[0], "編號")
            store.close()


if __name__ == "__main__":
    unittest.main()
