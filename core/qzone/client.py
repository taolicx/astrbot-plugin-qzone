
from typing import Any

import aiohttp

from astrbot.api import logger

from ..config import PluginConfig
from .constants import (
    HTTP_STATUS_FORBIDDEN,
    HTTP_STATUS_UNAUTHORIZED,
    QZONE_CODE_LOGIN_EXPIRED,
    QZONE_CODE_UNKNOWN,
    QZONE_INTERNAL_HTTP_STATUS_KEY,
    QZONE_INTERNAL_META_KEY,
    QZONE_MSG_PERMISSION_DENIED,
)
from .parser import QzoneParser
from .session import QzoneSession


class QzoneHttpClient:
    def __init__(self, session: QzoneSession, config: PluginConfig):
        self.cfg = config
        self.session = session
        self._session: aiohttp.ClientSession | None = None

    def _get_http_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.cfg.timeout)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
        retry: int = 0,
    ) -> dict[str, Any]:
        ctx = await self.session.get_ctx()
        request_headers = ctx.headers()
        if headers:
            for key, value in headers.items():
                for old_key in list(request_headers):
                    if old_key.lower() == key.lower():
                        request_headers.pop(old_key)
                request_headers[key] = value
        http_session = self._get_http_session()
        async with http_session.request(
            method,
            url,
            params=params,
            data=data,
            headers=request_headers,
            cookies=ctx.cookies(),
            timeout=timeout,
        ) as resp:
            text = await resp.text()

        parsed = QzoneParser.parse_response(text)
        meta = parsed.get(QZONE_INTERNAL_META_KEY)
        if not isinstance(meta, dict):
            meta = {}
            parsed[QZONE_INTERNAL_META_KEY] = meta
        meta[QZONE_INTERNAL_HTTP_STATUS_KEY] = resp.status

        # 仅在明确登录失效时触发重登
        if resp.status == HTTP_STATUS_UNAUTHORIZED or parsed.get(
            "code"
        ) == QZONE_CODE_LOGIN_EXPIRED:
            if retry >= 2:
                raise RuntimeError("登录失效，重试失败")

            logger.warning("登录失效，重新登录中")
            await self.session.login()
            return await self.request(
                method,
                url,
                params=params,
                data=data,
                headers=headers,
                timeout=timeout,
                retry=retry + 1,
            )

        if resp.status == HTTP_STATUS_FORBIDDEN and parsed.get("code") in (
            QZONE_CODE_UNKNOWN,
            None,
        ):
            parsed["code"] = resp.status
            parsed["message"] = QZONE_MSG_PERMISSION_DENIED

        return parsed
