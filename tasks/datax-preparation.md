# DataX 容器准备

- 原始项目：https://github.com/LiMing0016/DataX
- 来源提交：db708dae1b6574f41461615e453670a4c3bab421
- 准备分支：`prep/datax-container`
- 本地副本：`E:\goletalab测试\tasks\project02\baseline`

在准备分支根目录执行 `./eval.ps1 -Action up`，启动 PostgreSQL、ClickHouse 并执行查询检查；执行 `./eval.ps1 -Action verify` 可重复验证。镜像已固定 digest，测试凭据仅用于本机合成数据。

2026-09-19：两个数据库的健康检查和 SELECT 1 验证通过。业务应用尚未实现；此分支不是正式初始快照，不是 A/B 结果。题目由用户提供，后续按题目完成开发环境及数据准备后再冻结 base/a/b。

评测代码和最终产物均以 coding-agent-snapshots 为统一远端。原项目不受影响。
