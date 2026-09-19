"""L8 智慧監視器（F9、F16；T8、T9）：示範影片有 3 次來訪；隱私模式不存截圖。"""
import unittest
from datetime import datetime, timedelta

from helpers import TempDir, ensure_demo_media, make_app
from core.clock import TAIPEI
from modules.camera.module import CameraModule
from modules.camera.visits import VisitTracker, in_night, visits


def run_camera(app):
    cam = CameraModule(app)
    cam.setup()
    while not cam.finished:
        cam.step()                   # 不開執行緒，直接一張一張處理（很快）
    cam.teardown()
    return cam


class TestVisitRules(unittest.TestCase):
    def test_merge_short_gap(self):
        tr = VisitTracker(merge_gap_sec=3, min_visit_sec=1)
        box = (0, 0, 40, 180)
        done = []
        for i in range(100):
            t = i * 0.1
            present = not (3 <= t < 4.5)            # 中間消失 1.5 秒
            v = tr.update(t, box if present else None)
            if v:
                done.append(v)
        done.append(tr.close())
        self.assertEqual(len([d for d in done if d]), 1)

    def test_night_window(self):
        d = datetime(2026, 9, 1, tzinfo=TAIPEI)
        self.assertTrue(in_night(d.replace(hour=23, minute=30), "23:00", "05:00"))
        self.assertTrue(in_night(d.replace(hour=2), "23:00", "05:00"))
        self.assertFalse(in_night(d.replace(hour=14), "23:00", "05:00"))


class TestCameraVideo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_demo_media()

    def test_three_visits_with_snapshots(self):
        with TempDir() as tmp:
            app = make_app(tmp, start=datetime(2026, 9, 1, 14, 0, tzinfo=TAIPEI))
            run_camera(app)
            start = datetime(2026, 9, 1, 13, 0, tzinfo=TAIPEI)
            rows = visits(app.store, start, start + timedelta(hours=2))
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(r["snapshot"] for r in rows))
            self.assertEqual(len(list(app.snapshot_dir.glob("visit_*.jpg"))), 3)
            self.assertEqual([r["night"] for r in rows], [0, 0, 0])
            self.assertEqual(app.store.count(kind="visit", level="info"), 3)

    def test_privacy_mode_saves_no_image(self):
        with TempDir() as tmp:
            app = make_app(tmp, start=datetime(2026, 9, 1, 23, 30, tzinfo=TAIPEI), system={"privacy_mode": True})
            run_camera(app)
            rows = visits(app.store, "2026-09-01T00:00:00+08:00", "2026-09-03T00:00:00+08:00")
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(r["snapshot"] is None for r in rows))
            self.assertFalse(app.snapshot_dir.exists() and any(app.snapshot_dir.iterdir()))
            self.assertEqual(app.store.count(kind="visit", level="warn"), 3)     # 深夜來訪改發「注意」


if __name__ == "__main__":
    unittest.main()
