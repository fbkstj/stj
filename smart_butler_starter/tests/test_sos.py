"""L12 一鍵求救（F13；T12）：三種觸發方式、10 秒內重複只送一次、3 秒內送出。"""
import unittest

from helpers import TempDir, make_app
from core.notify import DryRunTransport
from core.supervisor import MODULE_CLASSES, Supervisor


class TestSos(unittest.TestCase):
    def setUp(self):
        self.tmp_ctx = TempDir()
        tmp = self.tmp_ctx.__enter__()
        self.t = DryRunTransport(echo=False)
        self.app = make_app(tmp, transport=self.t)
        self.sup = Supervisor(self.app, {k: MODULE_CLASSES[k] for k in ("chat", "sos")})
        self.sup.load()
        self.sup.start_all()
        self.sos = self.app.module("sos")

    def tearDown(self):
        self.sup.stop_all()
        self.app.store.close()
        self.tmp_ctx.__exit__(None, None, None)

    def urgent_count(self):
        return self.app.store.count(kind="sos", level="urgent")

    def test_three_triggers(self):
        self.assertTrue(self.sos.trigger("鍵盤"))
        self.app.clock.advance(seconds=11)
        self.assertTrue(self.sos.trigger("管理介面"))
        self.app.clock.advance(seconds=11)
        self.app.module("chat").handle("我跌倒了，救命")
        self.assertEqual(self.urgent_count(), 3)
        sources = [r["data"]["trigger"] for r in self.app.store.query(kind="sos")]
        self.assertEqual(sources, ["鍵盤", "管理介面", "語音"])

    def test_repeat_within_cooldown_sends_once(self):
        for _ in range(5):
            self.sos.trigger("鍵盤")
            self.app.clock.advance(seconds=1)
        self.assertEqual(self.urgent_count(), 1)
        self.assertEqual(len([x for x in self.t.sent if "求救" in x["text"]]), 1)

    def test_latency_under_3_seconds(self):
        self.sos.trigger("鍵盤")
        self.assertLess(self.sos.last_latency_ms, 3000)


if __name__ == "__main__":
    unittest.main()
