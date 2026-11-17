"""运行于语音候选镜像，验证连接归属和真实播放回执门禁。"""
import asyncio
import unittest
from types import SimpleNamespace

from core.social_test_control import SocialTestControl


class ControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_room_and_turn_identity(self):
        control = SocialTestControl()
        context = {"room_id": "a" * 32, "ready": asyncio.Event(), "played": asyncio.Event(),
                   "turn_id": "2", "tts_stop_sent": False, "task": None}
        conn = SimpleNamespace(social_test_context=context)
        self.assertTrue(await control.route(conn, b"microphone-packet"))
        await control.route(conn, '{"type":"social_test","state":"ready","room_id":"wrong"}')
        self.assertFalse(context["ready"].is_set())
        event = '{"type":"social_test","state":"played","room_id":"' + "a" * 32 + '","turn_id":"2"}'
        await control.route(conn, event)
        self.assertFalse(context["played"].is_set())
        context["tts_stop_sent"] = True
        await control.route(conn, event.replace('"2"', '"4"'))
        self.assertFalse(context["played"].is_set())
        await control.route(conn, event)
        self.assertTrue(context["played"].is_set())

    async def test_normal_conversation_is_not_intercepted(self):
        self.assertFalse(await SocialTestControl().route(SimpleNamespace(), b"normal-packet"))


if __name__ == "__main__":
    unittest.main()
