<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_qzone_plus?name=astrbot_plugin_qzone_plus&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# QQ空间增强版

_AstrBot QQ 空间增强插件_

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![Author](https://img.shields.io/badge/作者-taolicx-blue)](https://github.com/taolicx)
[![Version](https://img.shields.io/badge/version-v3.1.2-brightgreen)](https://github.com/taolicx/astrbot-plugin-qzone)

</div>

## 版本信息

- 插件 ID：`astrbot_plugin_qzone_plus`
- 插件名：QQ空间增强版
- 当前版本：`v3.1.2`
- 作者：`taolicx`
- 仓库：[taolicx/astrbot-plugin-qzone](https://github.com/taolicx/astrbot-plugin-qzone)
- 基于官方 `Zhalslar/astrbot_plugin_qzone` 改造

## 重要说明

增强版不是官方原版 `astrbot_plugin_qzone`。

如果安装后还是官方默认，通常是因为你仍在启用原版，或把本仓库克隆到了原版目录名。请停用/删除原版插件目录，再按下面命令安装到增强版目录。

## 安装

```bash
cd /AstrBot/data/plugins
git clone https://github.com/taolicx/astrbot-plugin-qzone astrbot_plugin_qzone_plus
```

然后重启 AstrBot，在插件列表中确认插件 ID 是：

```text
astrbot_plugin_qzone_plus
```

## 增强内容

- 独立插件 ID，不再和官方原版共用配置
- 默认显示名改为 QQ空间增强版
- 作者改为 taolicx
- 启动时强制写入姜若璃人设提示词，避免旧配置继续生效
- `评说说` 会拉取完整详情，评论后能展示说说图片
- 扩展 QQ 空间图片字段解析
- 修复点赞、评论、回复、发布、删除失败时仍提示成功的问题
- 修复删除说说先提示成功再删除的问题
- 修复样式目录在不同插件目录名下找不到的问题
- 补齐直接依赖

## 配置

请前往插件配置面板进行配置。`pillowmd_style_dir` 留空时会自动使用插件内置默认样式。

增强版会在启动时强制写入姜若璃人设提示词。如果你要完全自定义人设，需要改 `core/config.py` 中的 `JIANG_RUOLI_*_PROMPT` 常量。

## 定时调度说明

- `publish_cron` / `comment_cron` 表示任务的基准时间，Cron 表达式格式为：分 时 日 月 周
- `publish_offset` / `comment_offset` 表示围绕基准时间的随机前后浮动范围，单位秒
- 例如：`publish_cron = 30 23 * * *` 且 `publish_offset = 1800`，表示每天会在 `23:00 ~ 24:00` 间随机执行一次自动发说说
- 将偏移设为 `0` 可关闭浮动，严格按 Cron 时间触发

## 命令

| 命令 | 别名 | 权限 | 参数 | 功能 |
|----|----|----|----|----|
| 查看访客 | - | ADMIN | - | 查看 QQ 空间最近访客列表 |
| 看说说 | 查看说说 | ALL | `[@用户] [序号/范围]` | 查看说说 |
| 评说说 | 评论说说、读说说 | ALL | `[@用户] [序号/范围]` | 评论说说，可配置自动点赞 |
| 赞说说 | - | ALL | `[@用户] [序号/范围]` | 点赞说说 |
| 发说说 | - | ADMIN | `<文本> [图片]` | 立即发布说说 |
| 写说说 | 写稿 | ADMIN | `<主题> [图片]` | AI 生成待审核稿件 |
| 删说说 | - | ADMIN | `<序号>` | 删除自己发布的说说 |
| 回评 | 回复评论 | ALL | `<稿件ID> [评论序号]` | 回复评论 |
| 投稿 | - | ALL | `<文本> [图片]` | 投稿 |
| 匿名投稿 | - | ALL | `<文本> [图片]` | 匿名投稿 |
| 看稿 | 查看稿件 | ADMIN | `[稿件ID]` | 查看稿件 |
| 过稿 | 通过稿件、通过投稿 | ADMIN | `<稿件ID>` | 审核并发布稿件 |
| 拒稿 | 拒绝稿件、拒绝投稿 | ADMIN | `<稿件ID> [原因]` | 拒绝稿件 |
| 撤稿 | - | ALL | `<稿件ID>` | 撤回自己的投稿 |

## 序号示例

```text
看说说
看说说 0
看说说 -1
看说说 1~3
看说说 @某人 0
评说说 @某人 0
```

## 鸣谢

- 官方原版：[Zhalslar/astrbot_plugin_qzone](https://github.com/Zhalslar/astrbot_plugin_qzone)
- [CampuxBot](https://github.com/idoknow/CampuxBot)
- [QzoneExporter](https://github.com/wwwpf/QzoneExporter)
