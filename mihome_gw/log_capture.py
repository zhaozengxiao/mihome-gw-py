"""环形日志缓冲区: 捕捉日志供 WebUI 展示."""

import logging
from collections import deque


class RingBufferHandler(logging.Handler):
    """保留最近 N 条日志的内存处理器."""

    def __init__(self, capacity: int = 200):
        super().__init__()
        self.buffer: deque[logging.LogRecord] = deque(maxlen=capacity)
        self.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        ))

    def emit(self, record: logging.LogRecord):
        self.buffer.append(record)

    def tail(self, n: int = 50) -> list[str]:
        """返回最近 N 条格式化后的日志字符串."""
        return [
            self.format(r) for r in list(self.buffer)[-n:]
        ]

    def grep(self, keyword: str, n: int = 50) -> list[str]:
        """按关键词过滤最近日志."""
        return [
            self.format(r) for r in list(self.buffer)[-200:]
            if keyword.lower() in self.format(r).lower()
        ][-n:]


# 单例
_handler: RingBufferHandler | None = None


def install(capacity: int = 200):
    """安装到根 logger."""
    global _handler
    if _handler is None:
        _handler = RingBufferHandler(capacity)
        logging.getLogger().addHandler(_handler)


def get_logs(n: int = 50) -> list[str]:
    """获取最近 N 条日志."""
    if _handler:
        return _handler.tail(n)
    return []


def grep_logs(keyword: str, n: int = 50) -> list[str]:
    """搜索日志."""
    if _handler:
        return _handler.grep(keyword, n)
    return []