"""L6 意圖辨識與對話（F7；T6）：至少 20 句中文指令。"""
import unittest

from helpers import BASE_SETTINGS
from modules.chat.chat import ChatSession
from modules.chat.intent import parse

DEVICES = BASE_SETTINGS["chat"]["devices"]

# (句子, 預期裝置, 預期動作)；裝置為 None 代表不是家電指令或聽不懂
CASES = [
    ("打開客廳燈", "客廳燈", "on"),
    ("幫我開一下客廳的燈", "客廳燈", "on"),
    ("把客廳燈關掉", "客廳燈", "off"),
    ("客廳暗一點", "客廳燈", "dim"),
    ("客廳的燈調亮一點", "客廳燈", "bright"),
    ("大燈關起來", "客廳燈", "off"),
    ("房間燈打開", "臥室燈", "on"),
    ("臥室的燈關掉喔", "臥室燈", "off"),
    ("請開電風扇", "電風扇", "on"),
    ("風扇關掉啦", "電風扇", "off"),
    ("冷氣打開", "冷氣", "on"),
    ("把空調關閉", "冷氣", "off"),
    ("電視有沒有開", "電視", "status"),
    ("幫我關電視", "電視", "off"),
    ("電視小聲一點", "電視", "dim"),
    ("打開電暖器", "電暖器", "on"),
    ("暖氣關掉", "電暖器", "off"),
    ("幫我煮水壺開起來", "電熱水壺", "on"),
    ("熱水壺關掉", "電熱水壺", "off"),
    ("今天天氣真好", None, None),
    ("我孫子明天要來", None, None),
    ("燈打開", None, "on"),                     # 沒說哪個房間：要反問
]


class TestIntent(unittest.TestCase):
    def test_cases(self):
        wrong = []
        for text, device, action in CASES:
            it = parse(text, DEVICES)
            if (it.device, it.action) != (device, action):
                wrong.append(f"{text} → {it.device}/{it.action}（應為 {device}/{action}）")
        self.assertEqual(wrong, [], "\n".join(wrong))
        self.assertGreaterEqual(len(CASES), 20)

    def test_dangerous_flag(self):
        self.assertTrue(parse("打開電暖器", DEVICES).dangerous)
        self.assertFalse(parse("打開客廳燈", DEVICES).dangerous)


class TestChatSession(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.chat = ChatSession(BASE_SETTINGS, lambda kind, level, msg, **d: self.events.append((kind, level, msg, d)))

    def kinds(self):
        return [e[0] for e in self.events]

    def test_device_control_records_event(self):
        reply = self.chat.handle("打開客廳燈")
        self.assertIn("客廳燈", reply)
        self.assertTrue(self.chat.devices.state["客廳燈"]["on"])
        self.assertIn("device", self.kinds())

    def test_dangerous_needs_confirmation(self):
        reply = self.chat.handle("打開電暖器")
        self.assertIn("確定", reply)
        self.assertFalse(self.chat.devices.state["電暖器"]["on"])
        self.chat.handle("確定")
        self.assertTrue(self.chat.devices.state["電暖器"]["on"])

    def test_dangerous_cancel(self):
        self.chat.handle("打開電熱水壺")
        self.chat.handle("不要好了")
        self.assertFalse(self.chat.devices.state["電熱水壺"]["on"])

    def test_keywords(self):
        self.chat.handle("救命啊")
        self.chat.handle("我吃藥了")
        self.assertIn("sos_request", self.kinds())
        self.assertIn("meds_confirm", self.kinds())

    def test_no_ai_fallback(self):
        reply = self.chat.handle("今天天氣真好")
        self.assertIn("家電", reply)


if __name__ == "__main__":
    unittest.main()
