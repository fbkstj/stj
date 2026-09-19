"""L9 管理介面（F10）：只允許本機、存檔前檢查、各頁可開啟。"""
import unittest

from helpers import ROOT, TempDir, make_app
from core.supervisor import Supervisor
from web.app import create_app


class TestWeb(unittest.TestCase):
    def setUp(self):
        self.tmp_ctx = TempDir()
        self.tmp = self.tmp_ctx.__enter__()
        self.settings_path = self.tmp / "settings.yaml"
        self.settings_path.write_text((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        self.app = make_app(self.tmp, modules={"care": False, "camera": False})
        self.sup = Supervisor(self.app)
        self.sup.load()
        self.sup.start_all()
        self.client = create_app(self.app, self.sup, settings_path=self.settings_path).test_client()

    def tearDown(self):
        self.sup.stop_all()
        self.app.store.close()
        self.tmp_ctx.__exit__(None, None, None)

    def test_pages_open(self):
        for url in ("/", "/chat", "/visits", "/board", "/events", "/settings", "/events.csv"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
        self.assertIn("儀表板", self.client.get("/").get_data(as_text=True))

    def test_other_computer_forbidden(self):
        r = self.client.get("/", environ_base={"REMOTE_ADDR": "192.168.1.20"})
        self.assertEqual(r.status_code, 403)

    def test_invalid_setting_not_saved(self):
        before = self.settings_path.read_text(encoding="utf-8")
        form = {"care.fall_sec": "-5", "system.retention_days": "30", "discord.urgent_repeat_min": "5",
                "care.inactive_min": "60", "camera.merge_gap_sec": "3", "camera.night_start": "23:00",
                "camera.night_end": "05:00", "meds.timeout_min": "30", "daily.time": "20:00",
                "routine.wake_tolerance_min": "90", "discord.dry_run": "on"}
        r = self.client.post("/settings", data=form)
        self.assertIn("沒有存檔", r.get_data(as_text=True))
        self.assertEqual(self.settings_path.read_text(encoding="utf-8"), before)

    def test_env_never_shown(self):
        html = self.client.get("/settings").get_data(as_text=True)
        self.assertNotIn("WEBHOOK", html)
        self.assertNotIn("TOKEN", html)

    def test_chat_board_privacy(self):
        r = self.client.post("/chat", data={"text": "打開客廳燈"})
        self.assertIn("客廳燈", r.get_data(as_text=True))
        self.client.post("/board", data={"author": "女兒", "text": "晚上回家"})
        self.assertIn("晚上回家", self.client.get("/board").get_data(as_text=True))
        self.client.post("/privacy")
        self.assertTrue(self.app.privacy)
        self.assertIn("privacy_mode: true", self.settings_path.read_text(encoding="utf-8"))

    def test_sos_and_ack(self):
        self.client.post("/sos")
        alerts = self.app.notifier.open_alerts()
        self.assertEqual(len(alerts), 1)
        self.client.post(f"/ack/{alerts[0]['id']}")
        self.assertEqual(self.app.notifier.open_alerts(), [])


if __name__ == "__main__":
    unittest.main()
