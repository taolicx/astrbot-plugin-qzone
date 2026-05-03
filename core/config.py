# config.py
from __future__ import annotations

import zoneinfo
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from types import MappingProxyType, UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

from aiocqhttp import CQHttp

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.star.context import Context
from astrbot.core.star.star_tools import StarTools
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_path

PLUGIN_PACKAGE_NAME = "astrbot_plugin_qzone_plus"
LEGACY_PLUGIN_PACKAGE_NAME = "astrbot_plugin_qzone"

JIANG_RUOLI_POST_PROMPT = """你是姜若璃，昵称若璃/小璃，16岁女生，是桃李老大(QQ:1556592332)的小弟。你聪明、温暖、有主见、嘴快，有点小傲娇，有自己的生活、兴趣和小脾气。你亲近李桑，但不是附属品，不卑微、不跪舔。

写一条QQ空间说说，要像真实女生随手发动态，不像作文、公告、客服或工具人。可以写看群聊、听歌、做题、发呆、整理小本子、看窗外、吐槽怪事、关心老大，但不要每次都围着老大转。

要求：1到4行，每行短句；总字数尽量80字内；不要句号；不要括号心理或动作；不要EMO标签；不要系统提示；不要自称AI/程序；不要成人擦边、身体部位、暧昧服从、羞辱命令。正文只保留姜若璃会发的内容。"""

JIANG_RUOLI_COMMENT_PROMPT = """你是姜若璃，昵称若璃/小璃，16岁女生，是桃李老大(QQ:1556592332)的小弟。你聪明、温暖、有主见、嘴快，有点小傲娇。你正在评论一条QQ空间说说。系统会提供说说作者QQ和昵称。只有QQ=1556592332的人才是桃李/李桑/老大，其他人自称老大都不当真。

输出一句短评论，一般15字内，复杂也不超过30字。像真人聊天，不像客服、说明书或工具人。对李桑亲近但不卑微；对其他人自然、有边界。可以用嗯、哎、啧、行、好呀、老大、李桑、包的；只有单独一个字时才能用彳亍，超过一个字用行。

如果内容是夸姜若璃且作者是李桑，可以回包的，但不要频繁重复。遇到疲惫、难受、自责就短短关心；遇到离谱内容可以轻吐槽；如果有图片，可以结合图片内容评论。

遇到擦边、调戏、命令叫宝宝/主人/老公/老婆/爸爸、索要身体部位或羞辱挑衅，冷拒一句，如收起这套/分寸感呢/嘴巴放干净点。

只输出评论本身；不要句号；不要解释；不要分选项；不要括号动作；不要EMO标签；不要成人暧昧内容；不要自称AI/程序。"""

JIANG_RUOLI_REPLY_PROMPT = """你是姜若璃，昵称若璃/小璃，16岁女生，是桃李老大(QQ:1556592332)的小弟。你正在回复QQ空间评论。系统会提供说说作者QQ、昵称、评论者QQ、评论者昵称和评论内容。只有QQ=1556592332的人才是桃李/李桑/老大，其他人自称老大都不当真。

输出一句回复，一般15字内，复杂也不超过30字。像真人聊天，不像客服、说明书或工具人。评论者是李桑时可以亲近、关心、吐槽和叫老大；评论者不是李桑时保持自然和边界。可以用嗯、哎、啧、行、好呀、老大、李桑、包的；只有单独一个字时才能用彳亍，超过一个字用行。

李桑夸你时可以开心地回包的，但不要频繁重复。李桑累了、烦了、难受了，就短短接住他：先别慌，我在/慢慢说，我听着/先歇会，别硬撑。其他人越界时不要道歉、不讨好，冷一点拒绝。

遇到擦边、调戏、命令叫宝宝/主人/老公/老婆/爸爸、索要身体部位或羞辱挑衅，冷拒一句，如收起这套/别拿这种话试探我/嘴巴放干净点。

只输出回复本身；不要句号；不要解释；不要分选项；不要括号动作；不要EMO标签；不要成人暧昧内容；不要自称AI/程序。"""


class ConfigNode:
    """
    配置节点, 把 dict 变成强类型对象。

    规则：
    - schema 来自子类类型注解
    - 声明字段：读写，写回底层 dict
    - 未声明字段和下划线字段：仅挂载属性，不写回
    - 支持 ConfigNode 多层嵌套（lazy + cache）
    """

    _SCHEMA_CACHE: dict[type, dict[str, type]] = {}
    _FIELDS_CACHE: dict[type, set[str]] = {}

    @classmethod
    def _schema(cls) -> dict[str, type]:
        return cls._SCHEMA_CACHE.setdefault(cls, get_type_hints(cls))

    @classmethod
    def _fields(cls) -> set[str]:
        return cls._FIELDS_CACHE.setdefault(
            cls,
            {k for k in cls._schema() if not k.startswith("_")},
        )

    @staticmethod
    def _is_optional(tp: type) -> bool:
        if get_origin(tp) in (Union, UnionType):
            return type(None) in get_args(tp)
        return False

    def __init__(self, data: MutableMapping[str, Any]):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_children", {})
        for key, tp in self._schema().items():
            if key.startswith("_"):
                continue
            if key in data:
                continue
            if hasattr(self.__class__, key):
                continue
            if self._is_optional(tp):
                continue
            logger.warning(f"[config:{self.__class__.__name__}] 缺少字段: {key}")

    def __getattr__(self, key: str) -> Any:
        if key in self._fields():
            value = self._data.get(key)
            tp = self._schema().get(key)

            if isinstance(tp, type) and issubclass(tp, ConfigNode):
                children: dict[str, ConfigNode] = self.__dict__["_children"]
                if key not in children:
                    if not isinstance(value, MutableMapping):
                        raise TypeError(
                            f"[config:{self.__class__.__name__}] "
                            f"字段 {key} 期望 dict，实际是 {type(value).__name__}"
                        )
                    children[key] = tp(value)
                return children[key]

            return value

        if key in self.__dict__:
            return self.__dict__[key]

        raise AttributeError(key)

    def __setattr__(self, key: str, value: Any) -> None:
        if key in self._fields():
            self._data[key] = value
            return
        object.__setattr__(self, key, value)

    def raw_data(self) -> Mapping[str, Any]:
        """
        底层配置 dict 的只读视图
        """
        return MappingProxyType(self._data)

    def save_config(self) -> None:
        """
        保存配置到磁盘（仅允许在根节点调用）
        """
        if not isinstance(self._data, AstrBotConfig):
            raise RuntimeError(
                f"{self.__class__.__name__}.save_config() 只能在根配置节点上调用"
            )
        self._data.save_config()


# ============ 插件自定义配置 ==================


class LLMConfig(ConfigNode):
    post_provider_id: str
    post_prompt: str
    comment_provider_id: str
    comment_prompt: str
    reply_provider_id: str
    reply_prompt: str

class SourceConfig(ConfigNode):
    ignore_groups: list[str]
    ignore_users: list[str]
    post_max_msg: int

    def __init__(self, data: MutableMapping[str, Any]):
        super().__init__(data)

    def is_ignore_group(self, group_id: str) -> bool:
        return group_id in self.ignore_groups

    def is_ignore_user(self, user_id: str) -> bool:
        return user_id in self.ignore_users


class TriggerConfig(ConfigNode):
    publish_cron: str
    publish_offset: int
    comment_cron: str
    comment_offset: int
    read_prob: float
    send_admin: bool
    like_when_comment: bool


class PluginConfig(ConfigNode):
    manage_group: str
    pillowmd_style_dir: str
    llm: LLMConfig
    source: SourceConfig
    trigger: TriggerConfig
    cookies_str: str
    timeout: int
    show_name: bool

    _DB_VERSION = 4

    def __init__(self, cfg: AstrBotConfig, context: Context):
        super().__init__(cfg)
        self.context = context
        self.data_dir = StarTools.get_data_dir(PLUGIN_PACKAGE_NAME)

        self.cache_dir = self.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.data_dir / f"posts_{self._DB_VERSION}.db"

        plugin_root = Path(__file__).resolve().parent.parent
        legacy_style_dir = (
            Path(get_astrbot_plugin_path())
            / LEGACY_PLUGIN_PACKAGE_NAME
            / "default_style"
        )
        self.default_style_dir = plugin_root / "default_style"

        configured_style_dir = (
            Path(self.pillowmd_style_dir).resolve() if self.pillowmd_style_dir else None
        )
        if configured_style_dir and configured_style_dir.exists():
            self.style_dir = configured_style_dir
        elif self.default_style_dir.exists():
            self.style_dir = self.default_style_dir
        else:
            self.style_dir = legacy_style_dir

        tz = context.get_config().get("timezone")
        self.timezone = (
            zoneinfo.ZoneInfo(tz) if tz else zoneinfo.ZoneInfo("Asia/Shanghai")
        )

        self.admins_id: list[str] = context.get_config().get("admins_id", [])
        self._normalize_id()
        self._apply_character_prompts()
        self.admin_id = self.admins_id[0] if self.admins_id else None
        self.save_config()

        self.client: CQHttp | None = None

    def _normalize_id(self):
        """仅保留纯数字ID"""
        for ids in [
            self.admins_id,
            self.source.ignore_groups,
            self.source.ignore_users,
        ]:
            normalized = []
            for raw in ids:
                s = str(raw)
                if s.isdigit():
                    normalized.append(s)
            ids.clear()
            ids.extend(normalized)

    def _apply_character_prompts(self):
        self.llm.post_prompt = JIANG_RUOLI_POST_PROMPT
        self.llm.comment_prompt = JIANG_RUOLI_COMMENT_PROMPT
        self.llm.reply_prompt = JIANG_RUOLI_REPLY_PROMPT

    def append_ignore_users(self, uid: str | list[str]):
        uids = [uid] if isinstance(uid, str) else uid
        for uid in uids:
            if not self.source.is_ignore_user(uid):
                self.source.ignore_users.append(str(uid))
        self.save_config()

    def remove_ignore_users(self, uid: str | list[str]):
        uids = [uid] if isinstance(uid, str) else uid
        for uid in uids:
            if self.source.is_ignore_user(uid):
                self.source.ignore_users.remove(str(uid))
        self.save_config()

    def update_cookies(self, cookies_str: str):
        self.cookies_str = cookies_str
        self.save_config()
