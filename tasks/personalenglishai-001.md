# personalenglishai-001：隔离评测准备记录

状态：代码隔离已准备；未出题、未运行 A/B，运行环境尚未配置与验证。

## 来源与快照

- 原始项目：https://github.com/LiMing0016/personalenglishai
- 固定来源提交：`e605312fb785c863fafa7c563beee50534e0b712`
- 评测初始提交：`4f930b71e78613340d7351f1e1b3aa4dad6da649`
- [初始代码快照](https://github.com/LiMing0016/coding-agent-snapshots/commit/4f930b71e78613340d7351f1e1b3aa4dad6da649)

评测初始提交是独立根提交，代码树与来源提交完全一致。原项目旧提交被 GitHub 检测到包含密钥，故没有将旧历史引入评测分支，也没有改写原项目。请勿将原项目旧分支或标签推送到本仓库。

## 工作区与分支

本地根目录：`F:\goletalab测试\9月\evaluation-workspaces`

| 用途 | 子目录 | 分支 |
| --- | --- | --- |
| 初始基线 | `personalenglishai-001-base` | `codex/personalenglishai-001-base` |
| A 运行 | `personalenglishai-001-a` | `codex/personalenglishai-001-a` |
| B 运行 | `personalenglishai-001-b` | `codex/personalenglishai-001-b` |

三者均为独立目录和独立 Git 仓库；`origin` 均只指向 `https://github.com/LiMing0016/coding-agent-snapshots.git`。A/B 初始指向同一个评测初始提交，尚无产物提交。

## 首次跑题前仍需完成

1. 确定实际题目、完整提示词和人工验收标准。
2. 根据题目需要准备依赖与测试环境；当前没有安装依赖或启动应用。
3. 使用隔离的测试数据库、Redis、存储目录和端口，不连接正式业务数据；A/B 的可写状态也应隔离且初值一致。
4. 确认模型、Harness、版本和配置一致；秘密仅保存在本地，不进入公开提交。
5. 如果准备过程修改了受版本控制的代码或配置，需要重新保存共同初始快照，并同步 A/B，再开始两次运行。
6. 运行后分别提交、推送最终产物，记录真实的 A/B 最终 commit 链接。不要把当前相同的占位分支当作已完成的产物。

快照仓库的 GitHub Actions 已关闭，防止从源项目带入的 workflow 自动运行。原始项目的 Actions 设置没有修改。
