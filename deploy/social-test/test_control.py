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

    async def test_dual_turns_are_bound_to_real_connections(self):
        import threading
        sent, spoken, receipts = [], [], []
        class Logger:
            def bind(self, **kwargs): return self
            def info(self, *args): pass
        class PairControl(SocialTestControl):
            async def send(self, conn, ctx, state, **extra):
                sent.append((conn.device_id, state))
                if state == "start": ctx["ready"].set()
            async def speak(self, conn, ctx, turn):
                spoken.append((conn.device_id, turn["turn_id"]))
                ctx["played"].set()
            async def backend(self, method, suffix="", payload=None):
                receipts.append(payload)
                index = len(receipts)
                return make_room(index)
        def make_room(index):
            return {"room_id": "a"*32, "status": "finished" if index == 8 else "active",
                "next_turn": None if index == 8 else {"turn_id": str(index+1),
                    "speaker": "peer" if index % 2 == 0 else "real",
                    "device_uid": "peer-device" if index % 2 == 0 else "real-device"}}
        actors = {role: SimpleNamespace(device_id=role+"-device", stop_event=threading.Event(),
            logger=Logger(), cancel_active_turn=lambda: None, social_test_context=True)
            for role in ("peer", "real")}
        contexts = {role: {"room_id": "a"*32, "ready": asyncio.Event(),
            "played": asyncio.Event(), "turn_id": None, "tts_stop_sent": False}
            for role in actors}
        await PairControl().run_pair(actors, contexts, make_room(0))
        self.assertEqual([uid for uid, _ in spoken], ["peer-device", "real-device"]*4)
        self.assertTrue(all(item["result"] == "played" for item in receipts))
        self.assertTrue(all(item["actor_device_uid"] == uid
            for item, (uid, _) in zip(receipts, spoken)))
        self.assertEqual(sum(state == "end" for _, state in sent), 2)
        self.assertTrue(all(c.social_test_context is None for c in actors.values()))

    async def test_tts_factory_waits_for_import_even_if_module_is_cached(self):
        from unittest.mock import patch
        with patch("config.logger.setup_logging", return_value=SimpleNamespace()):
            from core.utils import tts
        loaded = SimpleNamespace(TTSProvider=lambda: "ready")
        with patch.object(tts.os.path, "exists", return_value=True), patch.object(
                tts.importlib, "import_module", return_value=loaded) as importer:
            with patch.dict("sys.modules", {"core.providers.tts.fake": SimpleNamespace()}):
                self.assertEqual(tts.create_instance("fake"), "ready")
                importer.assert_called_once_with("core.providers.tts.fake")

    async def test_ble_two_authenticated_joins_match_once(self):
        import threading
        class Conn:
            pass
        class Logger:
            def bind(self, **kwargs): return self
            def info(self, *args): pass
            def warning(self, *args): pass
        class JoinControl(SocialTestControl):
            def __init__(self): super().__init__(); self.matches = []
            async def start_pair(self, uid, peer): self.matches.append((uid, peer))
        control = JoinControl()
        uids = ["d8:85:ac:bb:b0:80", "d8:85:ac:ba:85:d0"]
        peers = []
        for uid in uids:
            c = Conn(); c.device_id=uid; c.tts=object(); c.need_bind=False
            c.stop_event=threading.Event(); c.client_is_speaking=False
            c.bind_completed_event=asyncio.Event(); c.bind_completed_event.set()
            c.logger=Logger(); peers.append(c)
        await control.join_ble(peers[0], "1234abcd")
        self.assertEqual(control.matches, [])
        await control.join_ble(peers[1], "1234abcd")
        self.assertEqual(control.matches, [tuple(uids)])
        await control.join_ble(peers[0], "1234abcd")
        self.assertEqual(len(control.matches), 1)

    async def test_ble_join_rejects_unknown_device(self):
        from unittest.mock import patch
        control = SocialTestControl()
        with patch.dict("os.environ", {"SOCIAL_TEST_ENABLED": "true"}):
            await control.route(SimpleNamespace(device_id="untrusted"),
                '{"type":"social_test","state":"join","invite_id":"1234abcd"}')
            await asyncio.sleep(0)
        self.assertEqual(control.ble_invites, {})

    async def test_normal_conversation_is_not_intercepted(self):
        self.assertFalse(await SocialTestControl().route(SimpleNamespace(), b"normal-packet"))


if __name__ == "__main__":
    unittest.main()
