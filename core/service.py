import asyncio
import time
from typing import Any

from astrbot.api import logger

from .db import PostDB
from .llm_action import LLMAction
from .model import Comment, Post
from .qzone import QzoneAPI, QzoneParser, QzoneSession
from .qzone.constants import (
    HTTP_STATUS_FORBIDDEN,
    QZONE_CODE_LOGIN_EXPIRED,
    QZONE_CODE_PERMISSION_DENIED,
    QZONE_CODE_PERMISSION_DENIED_LEGACY,
    QZONE_CODE_UNKNOWN,
    QZONE_INTERNAL_HTTP_STATUS_KEY,
    QZONE_INTERNAL_META_KEY,
    QZONE_MSG_EMPTY_RESPONSE,
    QZONE_MSG_INVALID_RESPONSE,
    QZONE_MSG_JSON_PARSE_ERROR,
    QZONE_MSG_NON_OBJECT_RESPONSE,
    QZONE_MSG_PERMISSION_DENIED,
)


class PostService:
    """QQ 空间业务编排层。"""

    def __init__(
        self,
        qzone: QzoneAPI,
        session: QzoneSession,
        db: PostDB,
        llm: LLMAction,
    ):
        self.qzone = qzone
        self.session = session
        self.db = db
        self.llm = llm

    # ============================================================
    # 查询说说
    # ============================================================

    async def query_feeds(
        self,
        *,
        target_id: str | None = None,
        pos: int = 0,
        num: int = 1,
        with_detail: bool = False,
        no_self: bool = False,
        no_commented: bool = False,
    ) -> list[Post]:
        if target_id:
            resp = await self.qzone.get_feeds(target_id, pos=pos, num=num)
            if not resp.ok:
                raise RuntimeError(self._map_feed_error(resp, target_id=target_id))

            msglist = resp.data.get("msglist") or []
            if not msglist:
                raise RuntimeError(f"QQ {target_id} 暂无可见说说")
            posts: list[Post] = QzoneParser.parse_feeds(msglist)
        else:
            posts = await self._query_recent_feeds_with_retry(pos=pos, num=num)
            if not posts:
                raise RuntimeError("动态流暂无可见说说")

        if no_self:
            uin = await self.session.get_uin()
            posts = [p for p in posts if p.uin != uin]

        if with_detail:
            posts = await self._fill_post_detail(posts)
            if not posts:
                raise RuntimeError("获取详情后无有效说说")

        if no_commented:
            posts = await self._filter_not_commented(posts)

        for post in posts:
            await self.db.save(post)

        return posts

    def _should_retry_recent_feed_error(self, resp) -> bool:
        """最近动态流接口偶发抖动时，决定是否值得重试一次。"""
        message = str(resp.message or "").strip().lower()
        code = resp.code
        http_status = self._extract_http_status(resp.raw)

        retryable_messages = {
            QZONE_MSG_EMPTY_RESPONSE,
            QZONE_MSG_INVALID_RESPONSE,
            QZONE_MSG_JSON_PARSE_ERROR,
            QZONE_MSG_NON_OBJECT_RESPONSE,
        }
        login_keywords = ("登录", "login", "expired", "cookie", "skey", "g_tk")
        permission_keywords = (
            "无权",
            "权限",
            "forbidden",
            QZONE_MSG_PERMISSION_DENIED.lower(),
            "access denied",
        )

        if code == QZONE_CODE_LOGIN_EXPIRED or self._contains_any(
            message, login_keywords
        ):
            return True

        if code == QZONE_CODE_UNKNOWN and (
            not message or (resp.message in retryable_messages)
        ):
            return True

        if http_status == HTTP_STATUS_FORBIDDEN or self._contains_any(
            message, permission_keywords
        ):
            return True

        return False

    async def _query_recent_feeds_with_retry(
        self,
        *,
        pos: int,
        num: int,
        retry_times: int = 2,
    ) -> list[Post]:
        """
        最近动态流接口偶发会出现空响应、403 或短暂登录态失效。
        这里只对“自己的最近动态流”做有限次重登重试，避免调度器反复刷异常栈。
        """
        last_error: str | None = None

        for attempt in range(retry_times + 1):
            resp = await self.qzone.get_recent_feeds()
            if resp.ok:
                return QzoneParser.parse_recent_feeds(resp.data)[pos : pos + num]

            last_error = self._map_feed_error(resp)
            if attempt >= retry_times or not self._should_retry_recent_feed_error(resp):
                raise RuntimeError(last_error)

            logger.warning(
                "[PostService] recent feeds query failed, refresh cookie and retry: attempt=%s/%s error=%s",
                attempt + 1,
                retry_times + 1,
                last_error,
            )
            try:
                await self.session.refresh_login()
            except Exception as refresh_exc:
                logger.warning(
                    "[PostService] refresh login failed during recent feeds retry, fallback to invalidate session: error=%s",
                    refresh_exc,
                )
                await self.session.invalidate()
            await asyncio.sleep(min(2.0, 0.5 * (attempt + 1)))

        raise RuntimeError(last_error or "查询动态流失败")

    @staticmethod
    def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _map_feed_error(self, resp, *, target_id: str | None = None) -> str:
        """统一把底层响应映射成对用户和调度器更稳定的业务错误。"""
        message = str(resp.message or "").strip()
        lower_message = message.lower()
        code = resp.code
        http_status = self._extract_http_status(resp.raw)

        permission_keywords = (
            "无权",
            "权限",
            "私密",
            "不可见",
            "拒绝访问",
            "受限",
            "forbidden",
            QZONE_MSG_PERMISSION_DENIED.lower(),
            "access denied",
        )
        login_keywords = ("登录", "失效", "skey", "g_tk", "cookie", "expired")

        if code == QZONE_CODE_LOGIN_EXPIRED or self._contains_any(
            lower_message, login_keywords
        ):
            return "登录状态失效，请重新登录后重试"

        if (
            code in (QZONE_CODE_PERMISSION_DENIED, QZONE_CODE_PERMISSION_DENIED_LEGACY)
            or http_status == HTTP_STATUS_FORBIDDEN
            or self._contains_any(lower_message, permission_keywords)
        ):
            if target_id:
                return f"无权限查看 QQ {target_id} 的说说"
            return "无权限访问动态流"

        if code == QZONE_CODE_UNKNOWN and message == QZONE_MSG_EMPTY_RESPONSE:
            if target_id:
                return f"无权限查看 QQ {target_id} 的说说（接口返回空响应）"
            return "动态接口返回空响应，请稍后重试"

        if code == QZONE_CODE_UNKNOWN and message in (
            QZONE_MSG_INVALID_RESPONSE,
            QZONE_MSG_JSON_PARSE_ERROR,
            QZONE_MSG_NON_OBJECT_RESPONSE,
        ):
            return "动态接口响应格式异常，请稍后重试"

        if message:
            return f"查询说说失败：{message}"
        return f"查询说说失败：code={code}"

    @staticmethod
    def _extract_http_status(raw: dict[str, Any]) -> int | None:
        meta = raw.get(QZONE_INTERNAL_META_KEY)
        if not isinstance(meta, dict):
            return None
        status = meta.get(QZONE_INTERNAL_HTTP_STATUS_KEY)
        return status if isinstance(status, int) else None

    @staticmethod
    def _has_comment_from_uin(post: Post, uin: int) -> bool:
        return any(comment.uin == uin for comment in post.comments)

    async def _has_saved_self_comment(self, post: Post, uin: int) -> bool:
        if not post.tid:
            return False
        saved_post = await self.db.get(post.tid, key="tid")
        return bool(saved_post and self._has_comment_from_uin(saved_post, uin))

    async def _fill_post_detail(self, posts: list[Post]) -> list[Post]:
        result: list[Post] = []

        for post in posts:
            resp = await self.qzone.get_detail(post)
            if not resp.ok or not resp.data:
                logger.warning(f"获取详情失败：{resp.data}")
                continue

            parsed = QzoneParser.parse_feeds([resp.data])
            if not parsed:
                logger.warning(f"解析详情失败：{resp.data}")
                continue

            result.append(parsed[0])

        return result

    async def _filter_not_commented(self, posts: list[Post]) -> list[Post]:
        result: list[Post] = []
        uin = await self.session.get_uin()

        for post in posts:
            if self._has_comment_from_uin(post, uin):
                continue
            if await self._has_saved_self_comment(post, uin):
                continue

            # 如果当前对象还没展开评论详情，就补一次 detail 再判断。
            if not post.comments:
                resp = await self.qzone.get_detail(post)
                if not resp.ok or not resp.data:
                    continue
                parsed = QzoneParser.parse_feeds([resp.data])
                if not parsed:
                    continue
                post = parsed[0]

            if self._has_comment_from_uin(post, uin):
                continue

            result.append(post)

        return result

    # ============================================================
    # 对外业务接口
    # ============================================================

    async def view_visitor(self) -> str:
        """查看访客。"""
        resp = await self.qzone.get_visitor()
        if not resp.ok:
            raise RuntimeError(f"获取访客异常：{resp.data}")
        if not resp.data:
            raise RuntimeError("无访客记录")
        return QzoneParser.parse_visitors(resp.data)

    async def like_posts(self, post: Post):
        """点赞帖子。"""
        if not post.tid:
            raise ValueError("帖子 tid 为空")
        await self.qzone.like(post)
        logger.info(f"已点赞 -> {post.name}")

    async def comment_posts(self, post: Post):
        """评论帖子。"""
        if not post.tid:
            raise ValueError("帖子 tid 为空")

        content = await self.llm.generate_comment(post)
        if not content:
            raise ValueError("生成评论内容为空")

        await self.qzone.comment(post, content)

        uin = await self.session.get_uin()
        name = await self.session.get_nickname()
        post.comments.append(
            Comment(
                uin=uin,
                nickname=name,
                content=content,
                create_time=int(time.time()),
                tid=0,
                parent_tid=None,
            )
        )
        await self.db.save(post)
        logger.info(f"已评论 -> {post.name}")

    async def reply_comment(self, post: Post, index: int):
        """回复评论，自动排除自己的评论。"""
        if not post.tid:
            raise ValueError("帖子 tid 为空")

        uin = await self.session.get_uin()
        other_comments = [comment for comment in post.comments if comment.uin != uin]
        total = len(other_comments)

        if total == 0:
            raise ValueError("没有可回复的评论")
        if not (-total <= index < total):
            raise ValueError(f"索引越界，当前仅有 {total} 条可回复评论")

        comment = other_comments[index]
        content = await self.llm.generate_reply(post, comment)
        if not content:
            raise ValueError("生成回复内容为空")

        resp = await self.qzone.reply(post, comment, content)
        if not resp.ok:
            raise RuntimeError(resp.message)

        name = await self.session.get_nickname()
        post.comments.append(
            Comment(
                uin=uin,
                nickname=name,
                content=content,
                create_time=int(time.time()),
                parent_tid=comment.tid,
            )
        )
        await self.db.save(post)

    async def publish_post(
        self,
        *,
        post: Post | None = None,
        text: str | None = None,
        images: list | None = None,
    ) -> Post:
        """发布说说，支持传完整 Post 或仅传 text/images。"""
        if post is None and not text and not images:
            raise ValueError("post、text、images 不能同时为空")

        if post is None:
            uin = await self.session.get_uin()
            name = await self.session.get_nickname()
            post = Post(
                uin=uin,
                name=name,
                text=text or "",
                images=images or [],
            )

        resp = await self.qzone.publish(post)
        if not resp.ok:
            raise RuntimeError(f"发布说说失败：{resp.data}")

        post.tid = resp.data.get("tid")
        post.status = "approved"
        post.create_time = resp.data.get("now", post.create_time)
        await self.db.save(post)
        return post

    async def delete_post(self, post: Post):
        """删除说说。"""
        if not post.tid:
            raise ValueError("帖子 tid 为空")
        await self.qzone.delete(post.tid)
        if post.id:
            await self.db.delete(post.id)
