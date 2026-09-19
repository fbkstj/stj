"""L10 用藥提醒：時間到提醒吃藥；長輩確認後記錄；逾時沒確認就通知家人（注意）。

確認方式：管理介面按「已服藥」、對管家說「我吃了」（對話模組發出 meds_confirm 事件）。
測試：settings.yaml 的 meds.test_mode 設成 true，啟動 30 秒後會多一次「測試用藥」，1 分鐘沒確認就通報。
"""
from __future__ import annotations

from datetime import timedelta

from core.clock import iso, parse_hhmm
from core.module import Module


class MedsScheduler:
    """純邏輯（不開執行緒），方便測試。"""

    def __init__(self, cfg: dict, clock, publish, say=print, test_mode=False):
        self.cfg = cfg
        self.clock = clock
        self.publish = publish
        self.say = say
        self.started = clock.now()
        self.day = None
        self.doses: list[dict] = []
        self.extra: list[dict] = []
        if test_mode:
            self.extra.append({"due": self.started + timedelta(seconds=30), "name": "測試用藥",
                               "say": "測試：該吃藥囉，吃完請說「我吃了」", "timeout_min": 1})

    def _build_day(self, now) -> None:
        self.day = now.date()
        self.doses = []
        for item in self.cfg["schedule"]:
            h, m = parse_hhmm(item["time"])
            due = now.replace(hour=h, minute=m, second=0, microsecond=0)
            self.doses.append({"due": due, "name": item["name"], "say": item.get("say") or f"該吃{item['name']}了",
                               "timeout_min": self.cfg["timeout_min"],
                               "skip": due < self.started})       # 啟動前就過了的，不補提醒
        self.doses += [dict(d) for d in self.extra if d["due"].date() == self.day]
        for d in self.doses:
            d.update(reminded=False, confirmed=None, overdue=False, skip=d.get("skip", False))
        self.doses.sort(key=lambda d: d["due"])

    def tick(self) -> None:
        now = self.clock.now()
        if self.day != now.date():
            self._build_day(now)
        for d in self.doses:
            if d["skip"] or d["confirmed"]:
                continue
            if not d["reminded"] and now >= d["due"]:
                d["reminded"] = True
                self.say(d["say"])
                self.publish("meds_remind", "info", f"提醒吃藥：{d['name']}（{d['due']:%H:%M}）",
                             dose=d["name"], due=iso(d["due"]))
            elif d["reminded"] and not d["overdue"] and now >= d["due"] + timedelta(minutes=d["timeout_min"]):
                d["overdue"] = True
                self.publish("meds_overdue", "warn",
                             f"{d['name']}（{d['due']:%H:%M}）提醒後 {d['timeout_min']:g} 分鐘還沒確認服用，請關心一下",
                             dose=d["name"], due=iso(d["due"]))

    def confirm(self, by: str = "管理介面") -> str:
        now = self.clock.now()
        if self.day != now.date():
            self._build_day(now)
        pending = [d for d in self.doses if d["reminded"] and not d["confirmed"]]
        if not pending:
            return "目前沒有需要確認的藥"
        d = pending[0]
        d["confirmed"] = now
        status = "延遲" if d["overdue"] else "準時"
        self.publish("meds_taken", "info", f"已服藥：{d['name']}（{d['due']:%H:%M}，{status}，由{by}確認）",
                     dose=d["name"], due=iso(d["due"]), status=status, by=by)
        return f"已記錄 {d['name']} 服用（{status}）"

    def today(self) -> list[dict]:
        now = self.clock.now()
        if self.day != now.date():
            self._build_day(now)
        out = []
        for d in self.doses:
            if d["confirmed"]:
                state = "延遲服用" if d["overdue"] else "已服用"
            elif d["overdue"]:
                state = "逾時未確認"
            elif d["reminded"]:
                state = "等待確認"
            elif d["skip"]:
                state = "（啟動前）"
            else:
                state = "還沒到"
            out.append({"time": f"{d['due']:%H:%M}", "name": d["name"], "state": state})
        return out


class MedsModule(Module):
    name = "meds"
    title = "用藥提醒"
    interval = 1.0
    listens = {"meds_confirm": "on_confirm"}     # 對管家說「我吃了」時會收到這個事件

    def setup(self):
        self.scheduler = MedsScheduler(self.cfg, self.clock, self.publish, self.app.say, self.cfg["test_mode"])

    def on_confirm(self, event):
        self.confirm(event.data.get("by", "對話"))

    def step(self):
        self.scheduler.tick()

    def confirm(self, by="管理介面") -> str:
        return self.scheduler.confirm(by)

    def today(self):
        return self.scheduler.today()
