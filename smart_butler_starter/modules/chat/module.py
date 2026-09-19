"""L6 AI 對話與家電控制模組。主程式中由管理介面的「和管家說話」使用；
單獨在終端機對話：python -m modules.chat"""
from __future__ import annotations

from core.config import get_secret
from core.module import Module
from modules.chat.chat import AIClient, ChatSession


class ChatModule(Module):
    name = "chat"
    title = "AI 對話與家電"
    interval = 1.0

    def setup(self):
        ai = AIClient(get_secret("AI_API_KEY"), self.cfg["ai_model"])
        self.session = ChatSession(self.settings, self.publish, ai, privacy=lambda: self.app.privacy)

    def handle(self, text: str) -> str:
        return self.session.handle(text)

    def check(self):
        return True, "正常（AI 閒聊" + ("已啟用）" if self.session.ai.ready else "未啟用，只處理家電與關鍵字）")
