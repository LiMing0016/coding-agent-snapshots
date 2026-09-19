# 可分发 A/B 基线工具

目标：每个题目串行 A/B；不同项目可在同机并行；恢复不删除 A 数据，不改原项目。

实现：Python 标准库调用 Git/Docker Compose，PowerShell 包装。每个配置指定 source、ref、compose、stateDir、id、ports、environment。工具只操作 stateDir 内自建 work，项目名包含状态路径摘要，显式拒绝外部卷、固定资源名、工作区外绑定及符号链接。配置与状态都必须位于被测 work 之外。

流程：init 克隆准确提交并生成隔离 Compose；start 准备环境；freeze 停止容器，备份全工作区及全部已挂载命名卷，记录镜像 ID、配置摘要、Prompt；start 启动 A；finish-a 验证干净 Git、起点祖先、远端分支准确 SHA，保留轨迹录屏；restore-b 再检查 A 已保存并验证备份摘要，停止/移除工具容器但保留所有卷，重命名 A 工作区，从冻结副本恢复相同 work 路径，为 B 创建新卷并解包；start 启动 B。

不自动 git reset/clean，不删除卷，不推送代码，不改变宿主全局配置。不保证浏览器、模型服务或宿主用户目录状态，必须人工恢复/核对。目录与卷备份含本地数据，不提交公开仓库。

验证：先写约束/生命周期测试，再实现；隔离 Docker 小型样例验证 A 写入与 B 回滚、被忽略文件恢复、证据留存、原卷不变、两个项目资源分离。分发前检查 git diff 与扫描工具目录。
