# Personal English AI 独立容器准备快照

- 来源代码版本：92ee39b9c242bb9a6806b4dfe98520b6629588f0
- 准备分支：prep/personalenglishai-container
- 准备提交：214f0e16357fd436a5f26369308b3ae7c6e6537c
- [完整快照](https://github.com/LiMing0016/coding-agent-snapshots/commit/214f0e16357fd436a5f26369308b3ae7c6e6537c)
- 本地目录：E:/goletalab测试/tasks/project01/safe-baseline

该分支只有一个根提交，未导入原项目旧历史。已排除本机配置、浏览器调试记录、上传资料、历史归档、工作流及输出文件。文档密码示例改用明确占位文本。

Gitleaks 8.30.1 扫描代码树和准备提交通过；仅对确切的业务 rubric 标识设置限定豁免。扫描不能保证识别所有秘密；如旧密钥仍有效，仍需在服务商处撤销或轮换。

启动：在该分支根目录执行 ./eval.ps1 -Action up；复查：./eval.ps1 -Action verify。AI/OCR 不在验证范围，真实 AI Key 不会继承，未实现本地 AI 模拟接口。

本次启动复用已有评测数据卷和依赖缓存，不是空数据卷重跑。正式出题后仍须补充相应测试数据与业务验收，再冻结共同初始提交并建立 A/B。原有 personalenglishai-001 基线及 A/B 占位分支保持不变。
2026-09-19 验证：从 safe-baseline 启动成功，前端 HTTP、后端 /api/ping、MySQL users 表查询、Redis PING 全部通过。
