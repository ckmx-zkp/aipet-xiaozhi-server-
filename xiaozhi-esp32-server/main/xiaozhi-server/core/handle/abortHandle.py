import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
TAG = __name__


async def handleAbortMessage(conn: "ConnectionHandler"):
    conn.logger.bind(tag=TAG).info("Abort message received")
    # 退出流程已经决定关连接。打断只用于插话，不能把这次退出取消掉。
    if conn.close_after_chat:
        conn.logger.bind(tag=TAG).info("忽略打断，会话正在退出")
        return
    # 设置成打断状态，会自动打断llm、tts任务
    conn.close_after_chat = False
    conn.client_abort = True
    conn.cancel_active_turn()
    conn.clear_queues()
    # 打断客户端说话状态
    await conn.websocket.send(
        json.dumps({"type": "tts", "state": "stop", "session_id": conn.session_id})
    )
    conn.clearSpeakStatus()
    conn.logger.bind(tag=TAG).info("Abort message received-end")
