"""L13 作息異常偵測（F14；T13）：假資料中只有異常日被通報。"""
import sys
import unittest
from datetime import datetime

from helpers import ROOT, BASE_SETTINGS, TempDir, make_app
from core.clock import TAIPEI
from core.store import Store
from modules.routine.analyzer import check
from modules.routine.module import RoutineModule

sys.path.insert(0, str(ROOT / "demo"))
from make_routine_data import generate  # noqa: E402

CFG = BASE_SETTINGS["routine"]


def at(day, hour, minute=0):
    return datetime(2026, 9, day, hour, minute, tzinfo=TAIPEI)


class TestRoutine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_ctx = TempDir()
        cls.tmp = cls.tmp_ctx.__enter__()
        generate(cls.tmp / "routine.db")
        cls.store = Store(cls.tmp / "routine.db")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        cls.tmp_ctx.__exit__(None, None, None)

    def test_not_enough_data(self):
        alerts, note = check(self.store, at(5, 21), CFG)
        self.assertEqual(alerts, [])
        self.assertIn("資料不足", note)

    def test_normal_days_no_alert(self):
        for day in (8, 10):
            for hour in (10, 21):
                alerts, _ = check(self.store, at(day, hour, 30), CFG)
                self.assertEqual(alerts, [], f"9/{day} {hour}:30 誤報：{alerts}")

    def test_abnormal_day_alerts(self):
        morning, _ = check(self.store, at(9, 10, 30), CFG)
        self.assertEqual([k for k, _ in morning], ["wake"])
        night, _ = check(self.store, at(9, 21), CFG)
        self.assertEqual([k for k, _ in night], ["low_12-17"])

    def test_module_notifies_once_per_day(self):
        with TempDir() as tmp:
            generate(tmp / "data" / "aina.db")
            app = make_app(tmp, start=at(9, 10, 30))
            m = RoutineModule(app)
            m.setup()
            self.assertEqual(len(m.run_check()), 1)
            self.assertEqual(len(m.run_check()), 0)          # 同一種異常一天只通報一次
            self.assertEqual(app.store.count(kind="routine_alert", level="warn"), 1)
            app.store.close()


if __name__ == "__main__":
    unittest.main()
