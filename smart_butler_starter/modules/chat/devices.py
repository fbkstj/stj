"""L6 家電控制：先用「模擬家電」，只記錄狀態並發出事件，不會碰到真的電器。

要接真實智慧插座時，寫一個新類別（例如 TapoPlug），提供同樣的 apply(name, action) 與 state，
再經過家人同意後替換 SimDevices 即可。聊天與意圖辨識的程式都不用改。
"""
from __future__ import annotations

from modules.chat.intent import ACTION_NAMES


class SimDevices:
    def __init__(self, devices: list[dict], publish=None):
        self.devices = {d["name"]: d for d in devices}
        self.publish = publish            # publish(kind, level, message, **data)
        self.state = {name: {"on": False, "level": 100} for name in self.devices}

    def describe(self, name: str) -> str:
        s = self.state[name]
        if not s["on"]:
            return f"{name}目前是關著的"
        extra = f"，強度 {s['level']}%" if self.devices[name].get("type") in ("light", "fan", "tv") else ""
        return f"{name}目前是開著的{extra}"

    def apply(self, name: str, action: str) -> str:
        """執行動作，回傳要回覆長輩的一句話。"""
        s = self.state[name]
        if action == "status":
            return self.describe(name)
        if action == "on":
            s["on"] = True
        elif action == "off":
            s["on"] = False
        elif action == "dim":
            s["on"], s["level"] = True, max(20, s["level"] - 30)
        elif action == "bright":
            s["on"], s["level"] = True, min(100, s["level"] + 30)
        msg = f"{name}已{ACTION_NAMES[action]}（模擬）"
        if self.publish:
            self.publish("device", "info", msg, device=name, action=action, on=s["on"], brightness=s["level"])
        return f"好的，{name}已經{ACTION_NAMES[action]}了"
