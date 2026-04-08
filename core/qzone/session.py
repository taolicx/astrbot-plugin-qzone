# qzone_session.py

import asyncio
from http.cookies import SimpleCookie

from astrbot.api import logger

from ..config import PluginConfig
from .model import QzoneContext


class QzoneSession:
    """QQ 空间登录上下文管理。"""

    DOMAIN = "user.qzone.qq.com"

    def __init__(self, config: PluginConfig):
        self.cfg = config
        self._ctx: QzoneContext | None = None
        self._lock = asyncio.Lock()

    async def get_ctx(self) -> QzoneContext:
        async with self._lock:
            if not self._ctx:
                self._ctx = await self.login(self.cfg.cookies_str)
            return self._ctx

    async def get_uin(self) -> int:
        ctx = await self.get_ctx()
        return ctx.uin

    async def get_nickname(self) -> str:
        ctx = await self.get_ctx()
        uin = str(ctx.uin)
        if not self.cfg.client:
            return uin
        try:
            info = await self.cfg.client.get_login_info()
            return info.get("nickname") or uin
        except Exception:
            return uin

    async def invalidate(self) -> None:
        async with self._lock:
            self._ctx = None

    async def refresh_cookies(self) -> str:
        """从机器人客户端重新抓取最新的 QZone cookies。"""
        if not self.cfg.client:
            raise RuntimeError("CQHttp 实例不存在，无法自动获取 Cookie")

        cookies_str = (await self.cfg.client.get_cookies(domain=self.DOMAIN)).get(
            "cookies"
        )
        if not cookies_str:
            raise RuntimeError("获取 Cookie 失败")

        self.cfg.update_cookies(cookies_str)
        logger.info("已从机器人客户端刷新 QQ 空间 Cookie")
        return cookies_str

    async def refresh_login(self) -> QzoneContext:
        """
        强制刷新 cookie 后重新登录。
        用于动态流空响应、权限抖动、登录失效等需要自恢复的路径。
        """
        async with self._lock:
            cookies_str = await self.refresh_cookies()
            self._ctx = self._build_ctx(cookies_str)
            logger.info(f"登录成功，uin={self._ctx.uin}")
            return self._ctx

    def _build_ctx(self, cookies_str: str) -> QzoneContext:
        cookies = {k: v.value for k, v in SimpleCookie(cookies_str).items()}
        uin = int(cookies.get("uin", "0")[1:])
        if not uin:
            raise RuntimeError("Cookie 中缺少合法 uin")

        return QzoneContext(
            uin=uin,
            skey=cookies.get("skey", ""),
            p_skey=cookies.get("p_skey", ""),
        )

    async def login(self, cookies_str: str | None = None) -> QzoneContext:
        logger.info("正在登录 QQ 空间")

        if not cookies_str:
            cookies_str = await self.refresh_cookies()

        self._ctx = self._build_ctx(cookies_str)
        logger.info(f"登录成功，uin={self._ctx.uin}")
        return self._ctx
