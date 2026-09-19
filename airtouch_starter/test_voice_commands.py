"""測試語音指令解析：不用麥克風，把 voice_test_phrases.csv 裡的句子逐一解析，比對是否正確。

CSV 欄位：text（句子）、expected_action（預期動作，空白代表「應該聽不懂」）、
expected_arg（秒數、格數，或「歌名|是否換歌(1/0)」）。
新增語音指令時，先在 CSV 加上測試句子，再修改 voice_commands.py，直到全部通過。

用法：python test_voice_commands.py
      python test_voice_commands.py 我的測試句.csv
"""
import csv
import os
import sys

import voice_commands

HERE = os.path.dirname(os.path.abspath(__file__))


def arg_text(cmd):
    if not cmd or cmd["arg"] is None:
        return ""
    if isinstance(cmd["arg"], dict):
        return f"{cmd['arg']['query']}|{int(cmd['arg']['close_current'])}"
    return str(cmd["arg"])


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "voice_test_phrases.csv")
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    passed = 0
    for r in rows:
        cmd = voice_commands.parse(r["text"])
        action = cmd["action"] if cmd else ""
        ok = action == r["expected_action"] and (not r["expected_arg"] or arg_text(cmd) == r["expected_arg"])
        passed += ok
        mark = "通過" if ok else "失敗"
        print(f"{mark}  {r['text']:<16} → {action or '（聽不懂）'} {arg_text(cmd)}"
              + ("" if ok else f"   （預期 {r['expected_action'] or '聽不懂'} {r['expected_arg']}）"))
    print(f"\n通過 {passed}/{len(rows)}（{passed / len(rows):.0%}）")
    sys.exit(0 if passed == len(rows) else 1)


if __name__ == "__main__":
    main()
