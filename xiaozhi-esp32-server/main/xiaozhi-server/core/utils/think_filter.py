"""流式 <think> 标签过滤器。

LLM 流式输出中，<think> / </think> 标签可能被拆到多个 chunk
（如 "<thi" + "nk>"），单 chunk 的 `in` 匹配会失效，导致思考内容
泄漏进 TTS。本类维护跨 chunk 的状态机，保证任意拆分方式下输出
与整体过滤一致：思考内容零泄漏、正文零丢失。
"""

OPEN_TAG = "<think>"
CLOSE_TAG = "</think>"


def _tag_prefix_tail(text, tag):
    """返回 text 尾部属于 tag 前缀的最长残片（不含完整 tag）。"""
    max_len = min(len(text), len(tag) - 1)
    for length in range(max_len, 0, -1):
        if tag.startswith(text[-length:]):
            return text[-length:]
    return ""


class ThinkTagFilter:
    """跨 chunk 过滤 <think>...</think> 内容，只输出可见正文。"""

    def __init__(self):
        self._in_think = False
        self._buffer = ""

    def feed(self, text):
        """喂入一个 chunk，返回本 chunk 确认可输出的可见文本。"""
        if not text:
            return ""
        buf = self._buffer + text
        out = []
        while buf:
            if self._in_think:
                idx = buf.find(CLOSE_TAG)
                if idx < 0:
                    # 整段都是思考内容，只暂扣可能的闭合标签残片
                    self._buffer = _tag_prefix_tail(buf, CLOSE_TAG)
                    return "".join(out)
                buf = buf[idx + len(CLOSE_TAG):]
                self._in_think = False
            else:
                idx = buf.find(OPEN_TAG)
                if idx < 0:
                    # 尾部可能是被拆开的标签残片，暂扣待下次拼接
                    tail = _tag_prefix_tail(buf, OPEN_TAG)
                    out.append(buf[: len(buf) - len(tail)])
                    self._buffer = tail
                    return "".join(out)
                out.append(buf[:idx])
                buf = buf[idx + len(OPEN_TAG):]
                self._in_think = True
        self._buffer = ""
        return "".join(out)

    def flush(self):
        """流结束时调用，吐出缓冲中未拼成标签的残余文本。"""
        if self._in_think:
            # 思考未闭合，残余全部视为思考内容丢弃
            self._buffer = ""
            return ""
        out = self._buffer
        self._buffer = ""
        return out
