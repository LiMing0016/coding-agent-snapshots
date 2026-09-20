# standalone3 — 初始工程

Vue 3 + TypeScript 前端、Python + FastAPI 后端。仅含空页面、健康检查与环境测试，不含算法分析、执行轨迹或题目答案。需要 Docker Desktop 的 Linux 容器与 Compose v2。

## 首次构建与启动

```powershell
docker compose -p stand03-prep build
docker compose -p stand03-prep up -d --no-build --wait
```

浏览器打开 http://127.0.0.1:25530，页面应显示“后端连接正常”。后端通过前端 /api 代理访问，不暴露额外宿主端口。这是开发/评测环境，不作为公网生产部署。

## 环境检查

```powershell
docker compose -p stand03-prep run --rm backend python -m pytest -q
docker compose -p stand03-prep run --rm --no-deps frontend npm test
docker compose -p stand03-prep run --rm --no-deps frontend npm run build
```

这些只验证初始工程，不证明题目功能实现。业务代码放 backend/app 与 frontend/src；测试放 backend/tests 与 frontend/src。Python 依赖由 requirements.lock 全量固定；前端用 package-lock.json 和 npm ci；基础镜像按摘要固定。

## A/B 工作区

首次运行前完整复制已验证代码到独立 a/b，初始 HEAD 相同，分支不同。在各自目录执行：

```powershell
# A: 使用独立 PowerShell 会话
$env:WEB_PORT='25531'
docker compose -p stand03-ch01-r001-t01-a up -d --no-build --wait
# B: 在另一个 PowerShell 会话与 b 目录中
$env:WEB_PORT='25532'
docker compose -p stand03-ch01-r001-t01-b up -d --no-build --wait
```

A/B 均复用同一次构建的镜像，项目名隔离网络及依赖卷，源码绑定各自目录；容器内路径一致。不共用可写 node_modules 或宿主 venv。运行测试命令中的 -p 替换为对应项目名。新机器需先从锁文件构建；跨机器重建不声称镜像字节完全相同。

不覆盖正在运行或未归档的工作区。依赖变化必须在下一题开始前统一构建和初始化，不在同题两边各自解析依赖。停止用 docker compose -p 对应项目名 stop，不随意删除数据卷。
