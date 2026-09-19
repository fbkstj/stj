"""L4 模組基底類別：每個模組都有 start()、stop()、health()，主程式才能用同一套方式管理。

寫新模組時，繼承 Module，改寫這幾個方法就好：
  setup()     啟動時做一次（開影片、建資料表）
  step()      每隔 interval 秒執行一次（主要工作）
  teardown()  停止時做一次（關影片）
  check()     回傳 (是否正常, 原因)，例如攝影機讀不到畫面就回傳 (False, "讀不到畫面")

要處理別的模組發出的事件，寫在 listens，例如 listens = {"meds_confirm": "on_confirm"}。
不要在模組裡自己呼叫 bus.subscribe：模組當掉重啟後，舊的訂閱還會留著，同一件事會被處理兩次。
"""
from __future__ import annotations

import logging
import threading
import traceback

from core.events import Event


class Module:
    name = "base"
    title = "模組"
    interval = 1.0          # step() 之間間隔幾秒
    listens: dict = {}      # 要收的事件：{"事件類型": "方法名稱"}，由主程式統一訂閱

    def __init__(self, app):
        self.app = app
        self.settings = app.settings
        self.clock = app.clock
        self.log = logging.getLogger(self.name)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None
        self.last_step = None       # 最近一次 step() 完成的時間（monotonic 秒）

    # ---- 子類別改寫 ----
    def setup(self) -> None: ...
    def step(self) -> None: ...
    def teardown(self) -> None: ...
    def check(self) -> tuple[bool, str]:
        return True, "正常"

    # ---- 共用 ----
    @property
    def cfg(self) -> dict:
        return self.settings.get(self.name, {})

    def publish(self, kind: str, level: str, message: str, attachment=None, **data) -> Event:
        return self.app.bus.publish(Event(self.name, kind, level, message, attachment, data))

    def start(self) -> None:
        self._stop.clear()
        self.error = None
        self.setup()
        self._thread = threading.Thread(target=self._run, name=f"module-{self.name}", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self.step()
                self.last_step = self.clock.monotonic()
                self._stop.wait(self.interval)
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self.log.error("模組當掉：%s\n%s", self.error, traceback.format_exc())

    def stop(self, timeout: float = 5) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout)
        try:
            self.teardown()
        except Exception as e:
            self.log.warning("停止時出錯：%s", e)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def health(self) -> tuple[bool, str]:
        if self.error:
            return False, f"已當掉（{self.error}）"
        if not self.running:
            return False, "沒有在執行"
        try:
            return self.check()
        except Exception as e:
            return False, f"健康檢查出錯：{e}"
