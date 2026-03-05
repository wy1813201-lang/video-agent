"""
通用重试工具
支持异步指数退避重试，用于视频/图像/LLM API 的不稳定请求。
"""

import asyncio
from typing import Awaitable, Callable, Optional, Tuple, Type


async def retry_async(
    func: Callable[[], Awaitable],
    *,
    max_attempts: int = 3,
    base_delay_sec: float = 1.0,
    max_delay_sec: float = 20.0,
    retry_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
):
    """
    异步重试包装器（指数退避）。

    Args:
        func: 无参异步函数
        max_attempts: 最大尝试次数
        base_delay_sec: 初始退避秒数
        max_delay_sec: 最大退避秒数
        retry_exceptions: 触发重试的异常类型
        on_retry: 每次重试前的回调 (attempt, error, sleep_sec)
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    attempt = 0
    while True:
        attempt += 1
        try:
            return await func()
        except retry_exceptions as err:
            if attempt >= max_attempts:
                raise
            sleep_sec = min(max_delay_sec, base_delay_sec * (2 ** (attempt - 1)))
            if on_retry:
                try:
                    on_retry(attempt, err, sleep_sec)
                except Exception:
                    pass
            await asyncio.sleep(sleep_sec)

