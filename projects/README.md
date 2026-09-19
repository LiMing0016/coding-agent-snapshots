# 统一评测入口

| 项目 | 远端分支 | 当前状态 |
| --- | --- | --- |
| Personal English AI | `codex/personalenglishai-001-base`、`codex/personalenglishai-001-a`、`codex/personalenglishai-001-b` | 保留已有安全快照及占位分支，尚未正式运行 |
| DataX | `prep/datax-container` | 基础设施准备，不是已冻结的题目或 A/B 产物 |

每道题由用户出题。确定题目并验证环境后，再保存共同初始提交，建立项目名和题号对应的 base/a/b 分支。正式提交统一使用本仓库的完整 SHA commit 链接。

## Personal English AI 的两个准备版本

已有远端快照来源为 e605312fb785c863fafa7c563beee50534e0b712，详见原任务记录。本次 E 盘容器实验副本来源为 92ee39b9c242bb9a6806b4dfe98520b6629588f0；两者不是同一个代码版本，不能把本次容器验证结果直接当作已有远端快照的验证结果。

原项目旧历史曾检测到密钥，不能推送本次实验副本的完整历史。下一步应审查当前代码树、构造不携带旧历史的安全准备快照，并重新验证容器环境。此步骤尚未完成。已有 A/B 分支不覆盖、不改写。

## 仓库边界

原始 personalenglishai 与 DataX 仓库继续独立开发。统一仓库仅保存评测准备与快照；不同项目的分支不相互合并。两个旧的空 eval 仓库暂时保留，不再使用，未删除。
