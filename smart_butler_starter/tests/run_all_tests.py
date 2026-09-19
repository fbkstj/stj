"""執行全部自動測試（不需要安裝 pytest；裝了 pytest 也可以直接執行 pytest）。

  python tests/run_all_tests.py
"""
import contextlib
import io
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

NAMES = {
    "test_config": "L1 設定中心", "test_events": "L2 事件與紀錄", "test_notify": "L3 Discord 通報",
    "test_main": "L4 模組管理", "test_care": "L5 長照監護", "test_intent": "L6 對話與家電",
    "test_board": "L7 留言板", "test_camera": "L8 智慧監視器", "test_web": "L9 管理介面",
    "test_meds": "L10 用藥提醒", "test_daily": "L11 平安回報", "test_sos": "L12 一鍵求救",
    "test_routine": "L13 作息異常", "test_health": "L14 系統穩定", "test_security": "T16 金鑰檢查",
}


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    import logging
    logging.disable(logging.CRITICAL)
    loader = unittest.TestLoader()
    total_fail, rows = 0, []
    t0 = time.time()
    for mod, title in NAMES.items():
        suite = loader.loadTestsFromName(mod)
        with contextlib.redirect_stdout(io.StringIO()):          # 測試中「管家說」等輸出不顯示
            result = unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite)
        bad = result.failures + result.errors
        total_fail += len(bad)
        rows.append((title, result.testsRun, len(bad)))
        for case, trace in bad:
            print(f"\n[失敗] {title}：{case.id()}\n{trace}")
    print("\n===== 測試結果 =====")
    for title, n, bad in rows:
        print(f"{'通過' if not bad else '失敗'}  {title:<12} {n - bad}/{n}")
    n_all = sum(n for _, n, _ in rows)
    print(f"合計：通過 {n_all - total_fail} 項，失敗 {total_fail} 項（{time.time() - t0:.0f} 秒）")
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
