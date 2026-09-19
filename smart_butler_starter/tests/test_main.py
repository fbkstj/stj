"""L4 主程式與模組管理（F5；T1～T3）。"""
import time
import unittest

from helpers import TempDir, make_app
from core.module import Module
from core.supervisor import Supervisor


class Ticker(Module):
    name = "ticker"
    title = "計數模組"
    interval = 0.01

    def setup(self):
        self.count = 0

    def step(self):
        self.count += 1


class Crasher(Module):
    name = "crasher"
    title = "會當掉的模組"
    interval = 0.01

    def step(self):
        raise RuntimeError("故意當掉")


def wait_until(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


class TestSupervisor(unittest.TestCase):
    def test_switch_off_module_not_loaded(self):
        with TempDir() as tmp:
            app = make_app(tmp, modules={"chat": False, "care": False, "camera": False})
            names = Supervisor(app).load()
            self.assertNotIn("chat", names)
            self.assertIn("meds", names)
            self.assertEqual(len(names), 5)

    def test_crash_restart_and_isolation(self):
        with TempDir() as tmp:
            app = make_app(tmp)
            sup = Supervisor(app, {"ticker": Ticker, "crasher": Crasher})
            sup.load()
            sup.start_all()
            self.assertTrue(wait_until(lambda: app.modules["crasher"].error is not None))
            first = app.modules["crasher"]
            sup.check_modules()
            self.assertIsNot(app.modules["crasher"], first)            # 換成新的物件重新啟動
            warns = app.store.query(kind="module_health", level="warn")
            self.assertEqual(len(warns), 1)
            ticker = app.modules["ticker"]
            before = ticker.count
            self.assertTrue(wait_until(lambda: ticker.count > before + 5))   # 另一個模組照常運作
            self.assertTrue(ticker.health()[0])
            sup.stop_all()

    def test_give_up_after_three_restarts(self):
        with TempDir() as tmp:
            app = make_app(tmp)
            sup = Supervisor(app, {"crasher": Crasher})
            sup.load()
            sup.start_all()
            for _ in range(4):
                wait_until(lambda: app.modules["crasher"].error is not None)
                sup.check_modules()
            self.assertIn("crasher", sup.gave_up)
            self.assertEqual(len(app.store.query(kind="module_health", level="urgent")), 1)
            sup.stop_all()

    def test_events_go_to_current_instance_only(self):
        with TempDir() as tmp:
            from core.events import Event
            app = make_app(tmp)

            class Listener(Ticker):
                name = "listener"
                listens = {"ping": "on_ping"}
                got = []

                def on_ping(self, event):
                    Listener.got.append(id(self))
            sup = Supervisor(app, {"listener": Listener})
            sup.load()
            sup.start_all()
            old = app.modules["listener"]
            old.error = "模擬當掉"
            sup.check_modules()                                         # 重啟，換新物件
            app.bus.publish(Event("test", "ping", "info", "ping"))
            self.assertEqual(Listener.got, [id(app.modules["listener"])])    # 只有新物件收到一次
            sup.stop_all()


if __name__ == "__main__":
    unittest.main()
