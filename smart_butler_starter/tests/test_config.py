"""L1 設定中心（F1、F2）。"""
import unittest

import yaml

from helpers import ROOT, TempDir
from core import config


class TestConfig(unittest.TestCase):
    def test_load_normal(self):
        s = config.load_settings()
        self.assertEqual(s["web"]["host"], "127.0.0.1")
        self.assertEqual(set(s["modules"]), set(config.MODULE_NAMES))

    def test_demo_overrides(self):
        s = config.load_settings(demo=True)
        self.assertEqual(s["system"]["data_dir"], "data/demo")
        self.assertTrue(s["meds"]["test_mode"])

    def test_missing_field(self):
        data = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
        del data["care"]["fall_sec"]
        errors = config.validate(data)
        self.assertIn("缺少欄位 care.fall_sec", errors)

    def test_bad_value(self):
        data = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
        data["web"]["host"] = "0.0.0.0"
        data["daily"]["time"] = "25:00"
        errors = "\n".join(config.validate(data))
        self.assertIn("web.host", errors)
        self.assertIn("daily.time", errors)

    def test_yaml_syntax_error_reports_line(self):
        with TempDir() as tmp:
            p = tmp / "bad.yaml"
            p.write_text("system:\n  name: 管家\n  retention_days: [30\n", encoding="utf-8")
            with self.assertRaises(config.ConfigError) as cm:
                config.load_settings(p)
            self.assertIn("行", cm.exception.errors[0])

    def test_update_keeps_comments(self):
        text = (ROOT / "config" / "settings.yaml").read_text(encoding="utf-8")
        new = config.update_yaml_values(text, {"care.fall_sec": 5, "system.privacy_mode": True})
        self.assertIn("fall_sec: 5             # 橫躺持續幾秒才算跌倒", new)
        self.assertIn("privacy_mode: true", new)
        self.assertEqual(len(text.splitlines()), len(new.splitlines()))
        data = yaml.safe_load(new)
        self.assertEqual(data["care"]["fall_sec"], 5)
        self.assertEqual(data["camera"]["merge_gap_sec"], 3)     # 其他欄位沒被改到

    def test_save_rejects_invalid(self):
        with TempDir() as tmp:
            p = tmp / "settings.yaml"
            p.write_text((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            before = p.read_text(encoding="utf-8")
            errors = config.save_changes({"care.fall_sec": -1}, p)
            self.assertTrue(errors)
            self.assertEqual(p.read_text(encoding="utf-8"), before)     # 有錯就不存
            self.assertEqual(config.save_changes({"care.fall_sec": 4}, p), [])
            self.assertEqual(yaml.safe_load(p.read_text(encoding="utf-8"))["care"]["fall_sec"], 4)

    def test_secret_from_env_file(self):
        with TempDir() as tmp:
            env = tmp / ".env"
            env.write_text("DISCORD_WEBHOOK_TEST=https://example.invalid/hook\nAI_API_KEY=\n", encoding="utf-8")
            self.assertEqual(config.get_secret("DISCORD_WEBHOOK_TEST", env), "https://example.invalid/hook")
            self.assertEqual(config.get_secret("AI_API_KEY", env), "")
            self.assertEqual(config.get_secret("NOT_EXIST_XYZ", env), "")


if __name__ == "__main__":
    unittest.main()
