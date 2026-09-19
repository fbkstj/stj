"""L5 長照監護（F6；T4）：用示範影片測試，不開攝影機。"""
import csv
import unittest

from helpers import ROOT, ensure_demo_media
from modules.care.module import analyze_video
from modules.care.monitor import CareMonitor, posture

VIDEO = ROOT / "demo" / "care_demo.mp4"


class TestCareRules(unittest.TestCase):
    def test_posture(self):
        self.assertEqual(posture((0, 0, 40, 180)), "upright")
        self.assertEqual(posture((0, 0, 180, 40)), "lying")
        self.assertEqual(posture((0, 0, 100, 100)), "bent")
        self.assertEqual(posture(None), "none")

    def test_short_lying_is_not_fall(self):
        m = CareMonitor(fall_sec=3)
        out = []
        for i in range(20):
            out += m.update(i * 0.1, (0, 0, 40, 180))                  # 站著 2 秒
        for i in range(20):
            out += m.update(2 + i * 0.1, (0, 100, 180, 40))            # 躺 2 秒（未滿 3 秒）
        self.assertNotIn("fall", [k for k, _, _ in out])

    def test_lying_without_standing_first_is_not_fall(self):
        m = CareMonitor(fall_sec=3)
        out = []
        for i in range(100):
            out += m.update(i * 0.1, (0, 100, 180, 40))                 # 一開始就躺著（例如在床上）
        self.assertNotIn("fall", [k for k, _, _ in out])


class TestCareVideo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_demo_media()
        cls.found = analyze_video(VIDEO, fall_sec=3, inactive_min=0.2)
        with open(ROOT / "demo" / "care_demo_truth.csv", encoding="utf-8-sig") as f:
            cls.truth = {r["event"]: float(r["start_sec"]) for r in csv.DictReader(f)}

    def events(self, kind):
        return [t for t, k, _, _ in self.found if k == kind]

    def test_fall_detected_once(self):
        falls = self.events("fall")
        self.assertEqual(len(falls), 1)
        delay = falls[0] - self.truth["fall"]
        self.assertTrue(3 <= delay <= 5, f"跌倒後 {delay:.1f} 秒才通報")

    def test_no_false_alarm_when_bending_or_sitting(self):
        self.assertTrue(all(t >= self.truth["fall"] for t in self.events("fall")))

    def test_inactive_detected_once(self):
        inactive = self.events("inactive")
        self.assertEqual(len(inactive), 1)
        self.assertGreaterEqual(inactive[0], self.truth["inactive"] + 12)

    def test_longer_fall_sec_misses_short_lying(self):
        found = analyze_video(VIDEO, fall_sec=12, inactive_min=0.2)
        self.assertEqual([k for _, k, _, _ in found if k == "fall"], [])   # 只躺 10 秒，門檻 12 秒就漏報


if __name__ == "__main__":
    unittest.main()
