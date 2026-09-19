"""L7 留言板雙向同步（F8；T7）：不重複、不迴圈、重啟不重送。"""
import unittest

from helpers import FailingTransport, TempDir, make_app
from modules.board.board import Board


class TestBoard(unittest.TestCase):
    def test_web_post_synced_once_and_echo_ignored(self):
        with TempDir() as tmp:
            app = make_app(tmp)
            sent = []

            def send(channel, text):
                sent.append(text)
                return "9001"
            board = Board(app.store, app.clock, send=send)
            board.post("女兒", "媽，記得吃飯")
            self.assertEqual(len(sent), 1)
            # Bot 讀到剛剛送出的那則（同一個編號）→ 不可以再存一次
            self.assertFalse(board.receive("9001", "女兒", "💬 女兒：媽，記得吃飯"))
            self.assertEqual(len(board.list()), 1)

    def test_discord_message_once(self):
        with TempDir() as tmp:
            app = make_app(tmp)
            board = Board(app.store, app.clock, send=lambda c, t: "x")
            self.assertTrue(board.receive("5001", "兒子", "週末回家"))
            self.assertFalse(board.receive("5001", "兒子", "週末回家"))   # 同一則讀到兩次
            self.assertFalse(board.receive("5002", "Webhook", "機器人訊息", from_webhook=True))
            self.assertEqual(len(board.list()), 1)

    def test_restart_does_not_resend(self):
        with TempDir() as tmp:
            app = make_app(tmp)
            sent = []
            Board(app.store, app.clock, send=lambda c, t: sent.append(t) or f"id{len(sent)}").post("A", "第一則")
            board2 = Board(app.store, app.clock, send=lambda c, t: sent.append(t) or f"id{len(sent)}")  # 模擬重新啟動
            self.assertEqual(board2.sync_pending(), 0)
            self.assertEqual(len(sent), 1)

    def test_offline_post_waits_then_syncs(self):
        with TempDir() as tmp:
            app = make_app(tmp)
            t = FailingTransport()
            board = Board(app.store, app.clock, send=lambda c, text: t.send(c, text))
            board.post("A", "斷網時留言")
            self.assertIsNone(board.list()[0]["discord_id"])
            t.online = True
            self.assertEqual(board.sync_pending(), 1)
            self.assertIsNotNone(board.list()[0]["discord_id"])

    def test_empty_message_rejected(self):
        with TempDir() as tmp:
            app = make_app(tmp)
            with self.assertRaises(ValueError):
                Board(app.store, app.clock).post("A", "   ")


if __name__ == "__main__":
    unittest.main()
