"""T16 金鑰檢查：全專案找不到 Webhook、Token、API 金鑰的明碼（.env 除外）。"""
import re
import unittest

from helpers import ROOT

PATTERNS = {
    "Discord Webhook 網址": re.compile(r"discord(?:app)?\.com/api/webhooks/\d+/[\w-]{20,}"),
    "Discord Bot Token": re.compile(r"[MNO][\w-]{23,25}\.[\w-]{6}\.[\w-]{27,}"),
    "Anthropic API 金鑰": re.compile(r"sk-ant-[\w-]{20,}"),
    "其他 API 金鑰": re.compile(r"(?i)(api[_-]?key|token|secret)\s*[=:]\s*['\"][A-Za-z0-9_\-]{24,}['\"]"),
}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "data"}
EXTS = {".py", ".yaml", ".yml", ".md", ".txt", ".html", ".css", ".js", ".json", ".jsonl", ".bat", ".ps1", ".example", ".csv"}


def scan():
    found = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name == ".env" or SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() not in EXTS and path.name != ".env.example":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pat in PATTERNS.items():
            if path.name == "test_security.py":
                continue
            for m in pat.finditer(text):
                line = text[:m.start()].count("\n") + 1
                found.append(f"{path.relative_to(ROOT)} 第 {line} 行：疑似 {name}")
    return found


class TestSecrets(unittest.TestCase):
    def test_no_plaintext_secrets(self):
        found = scan()
        self.assertEqual(found, [], "\n".join(found))

    def test_env_is_ignored(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env", text.splitlines())


if __name__ == "__main__":
    unittest.main()
