"""L10 用藥提醒（F11；T10）。"""
import unittest
from datetime import datetime

from helpers import BASE_SETTINGS
from core.clock import TAIPEI, FakeClock
from modules.meds.module import MedsScheduler


class TestMeds(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(datetime(2026, 9, 1, 7, 50, tzinfo=TAIPEI))
        self.events = []
        self.said = []
        self.s = MedsScheduler(BASE_SETTINGS["meds"], self.clock,
                               lambda kind, level, msg, **d: self.events.append((kind, level, d)),
                               say=self.said.append)

    def kinds(self):
        return [k for k, _, _ in self.events]

    def run_minutes(self, n):
        for _ in range(n):
            self.clock.advance(minutes=1)
            self.s.tick()

    def test_on_time_confirm(self):
        self.run_minutes(11)                        # 到 08:01
        self.assertEqual(self.kinds(), ["meds_remind"])
        self.assertEqual(len(self.said), 1)
        self.assertIn("準時", self.s.confirm("測試"))
        self.run_minutes(60)
        self.assertNotIn("meds_overdue", self.kinds())

    def test_overdue_notified_once(self):
        self.run_minutes(120)                       # 到 09:50，沒人確認
        self.assertEqual(self.kinds().count("meds_overdue"), 1)
        level = [lv for k, lv, _ in self.events if k == "meds_overdue"][0]
        self.assertEqual(level, "warn")
        self.assertIn("延遲", self.s.confirm("測試"))

    def test_nothing_to_confirm(self):
        self.assertEqual(self.s.confirm(), "目前沒有需要確認的藥")

    def test_doses_before_start_are_skipped(self):
        clock = FakeClock(datetime(2026, 9, 1, 15, 0, tzinfo=TAIPEI))
        events = []
        s = MedsScheduler(BASE_SETTINGS["meds"], clock, lambda k, lv, m, **d: events.append(k), say=lambda t: None)
        s.tick()
        self.assertEqual(events, [])                # 08:00、12:30 已過，不補提醒
        self.assertEqual([d["state"] for d in s.today()], ["（啟動前）", "（啟動前）", "還沒到"])

    def test_test_mode_short_timeout(self):
        clock = FakeClock(datetime(2026, 9, 1, 15, 0, tzinfo=TAIPEI))
        events = []
        s = MedsScheduler(BASE_SETTINGS["meds"], clock, lambda k, lv, m, **d: events.append(k),
                          say=lambda t: None, test_mode=True)
        for _ in range(100):
            clock.advance(seconds=1)
            s.tick()
        self.assertEqual(events, ["meds_remind", "meds_overdue"])   # 30 秒提醒、90 秒逾時


if __name__ == "__main__":
    unittest.main()
