"""L6 對話：家電指令交給 intent.py；求救、吃藥等關鍵話語發出事件；其他閒聊交給 AI。

AI 金鑰放在 .env 的 AI_API_KEY（Claude API）。沒有金鑰或沒安裝 anthropic 套件時，
管家仍然可以控制家電、確認吃藥、求救，只是不能閒聊。
"""
from __future__ import annotations

import logging

from modules.chat.devices import SimDevices
from modules.chat.intent import parse

log = logging.getLogger("chat")

SYSTEM_PROMPT = (
    "你是居家智慧管家「阿娜」，陪伴台灣的長輩聊天。一律用繁體中文、口語、親切，"
    "每次回答 1～3 句、不超過 60 個字。不要提供醫療診斷；身體不舒服時請對方說「救命」或聯絡家人。"
    "家電控制由系統處理，你不用假裝已經開關家電。請直接開始回答，不要鋪陳。"
)
MEDS_WORDS = ["吃了", "吃過藥", "吃藥了", "藥吃了", "吃完藥"]
SAFE_WORDS = ["我平安", "我沒事"]
CANCEL_WORDS = ["不要", "不用", "取消", "算了", "不"]


class AIClient:
    """呼叫 Claude API。任何錯誤都回傳 None，由呼叫端改用備用回答。"""

    def __init__(self, api_key: str, model: str):
        self.model = model
        self.client = None
        if not api_key:
            return
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key, timeout=20.0, max_retries=1)
        except ImportError:
            log.info("沒有安裝 anthropic 套件，閒聊功能關閉")

    @property
    def ready(self) -> bool:
        return self.client is not None

    def reply(self, history: list[dict]) -> str | None:
        if not self.client:
            return None
        import anthropic
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=history[-10:],
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default"},
            )
        except anthropic.AuthenticationError:
            log.warning("AI 金鑰無效，請檢查 .env 的 AI_API_KEY")
            return None
        except anthropic.RateLimitError:
            log.warning("AI 使用量超過限制，稍後再試")
            return None
        except anthropic.APIStatusError as e:
            log.warning("AI 服務回應錯誤 %s", e.status_code)
            return None
        except anthropic.APIConnectionError:
            log.warning("連不上 AI 服務（網路？）")
            return None
        if resp.stop_reason == "refusal":
            return "這個問題我沒辦法回答，我們聊聊別的好嗎？"
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text or None


class ChatSession:
    def __init__(self, settings: dict, publish, ai: AIClient | None = None, privacy=lambda: False):
        c = settings["chat"]
        self.confirm_words = c["confirm_words"]
        self.sos_keywords = settings["sos"]["keywords"]
        self.publish = publish
        self.devices = SimDevices(c["devices"], publish)
        self.ai = ai
        self.privacy = privacy
        self.pending = None          # 等待二次確認的 Intent
        self.history: list[dict] = []

    def handle(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "我在這裡，請說。"
        self.publish("chat", "info", "（隱私模式，不記錄內容）" if self.privacy() else f"長輩說：{text}")
        reply = self._reply(text)
        if not self.privacy():
            self.publish("chat", "info", f"管家回：{reply}")
        return reply

    def _reply(self, text: str) -> str:
        # 1. 危險設備的二次確認
        if self.pending:
            intent, self.pending = self.pending, None
            if any(w in text for w in CANCEL_WORDS):
                return f"好，{intent.device}先不動。"
            if any(w in text for w in self.confirm_words):
                return self.devices.apply(intent.device, intent.action)
            return f"沒有收到確認，{intent.device}先不動。"
        # 2. 求救（最優先）
        hit = next((k for k in self.sos_keywords if k in text), None)
        if hit:
            self.publish("sos_request", "info", f"對話中說出求救關鍵字「{hit}」", trigger="語音", keyword=hit)
            return "我已經通知家人了！請盡量待在原地，不要亂動。"
        # 3. 吃藥確認、報平安
        if any(w in text for w in MEDS_WORDS):
            self.publish("meds_confirm", "info", "長輩說已經吃藥", by="對話")
            return "好的，我記下來了，你好棒！"
        if any(w in text for w in SAFE_WORDS):
            self.publish("safe_confirm", "info", "長輩回報平安", by="對話")
            return "太好了，我會告訴家人你平安。"
        # 4. 家電指令
        intent = parse(text, list(self.devices.devices.values()))
        if intent.device and intent.action:
            if intent.dangerous and intent.action in ("on", "bright"):
                self.pending = intent
                return f"{intent.device}會發熱，確定要打開嗎？請說「確定」。"
            return self.devices.apply(intent.device, intent.action)
        if intent.device or intent.action:
            return intent.reason
        # 5. 閒聊交給 AI
        self.history.append({"role": "user", "content": text})
        answer = self.ai.reply(self.history) if self.ai else None
        if answer is None:
            self.history.pop()
            return "我現在只能幫你開關家電、記錄吃藥，或幫你通知家人喔。"
        self.history.append({"role": "assistant", "content": answer})
        return answer
