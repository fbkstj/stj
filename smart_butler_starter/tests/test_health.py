"""L14 系統穩定（F15；T14）：健康檢查只在狀態改變時通報；過期截圖自動刪除。"""
import os
import time
import unittest

from helpers import TempDir, make_app
from core.health import HealthMonitor, cleanup


class TestHealth(unittest.TestCase):
    def test_warn_on_change_info_on_recover(self):
        with TempDir() as tmp:
            app = make_app(tmp)
            net = {"ok": True}
            hm = HealthMonitor(app, net_check=lambda: (net["ok"], "模擬"), disk_check=lambda p, g: (True, "足夠"))
            hm.run()
            net["ok"] = False
            hm.run()
            hm.run()                                   # 仍然斷線：不重複通報
            net["ok"] = True
            hm.run()
            rows = app.store.query(kind="health")
            self.assertEqual([r["level"] for r in rows], ["warn", "info"])
            self.assertIn("網路", rows[0]["message"])

    def test_cleanup_old_snapshots(self):
        with TempDir() as tmp:
            app = make_app(tmp, system={"retention_days": 1})
            app.snapshot_dir.mkdir(parents=True)
            old, new = app.snapshot_dir / "old.jpg", app.snapshot_dir / "new.jpg"
            old.write_bytes(b"x")
            new.write_bytes(b"x")
            two_days_ago = time.time() - 2 * 86400
            os.utime(old, (two_days_ago, two_days_ago))
            app.clock.set(app.clock.now().fromtimestamp(time.time(), app.clock.now().tzinfo))
            removed = cleanup(app)
            self.assertEqual(removed["截圖"], 1)
            self.assertFalse(old.exists())
            self.assertTrue(new.exists())


if __name__ == "__main__":
    unittest.main()
