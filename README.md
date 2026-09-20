# standalone1 — 初始工程

Vue 3 + TypeScript 前端、Python + FastAPI 后端。仅含空页面、健康检查与环境测试，不含算法分析、执行轨迹或题目答案。需要 Docker Desktop 的 Linux 容器与 Compose v2。

## 首次构建与启动

```powershell
docker compose -p stand01-prep build
docker compose -p stand01-prep up -d --no-build --wait
```

浏览器打开 http://127.0.0.1:25510，页面应显示“后端连接正常”。后端通过前端 /api 代理访问，不暴露额外宿主端口。这是开发/评测环境，不作为公网生产部署。

## 环境检查

```powershell
docker compose -p stand01-prep run --rm backend python -m pytest -q
docker compose -p stand01-prep run --rm --no-deps frontend npm test
docker compose -p stand01-prep run --rm --no-deps frontend npm run build
```

这些只验证初始工程，不证明题目功能实现。业务代码放 backend/app 与 frontend/src；测试放 backend/tests 与 frontend/src。Python 依赖由 requirements.lock 全量固定；前端用 package-lock.json 和 npm ci；基础镜像按摘要固定。

## 操作计数接口 POST /api/analysis/count

请求体为 `{ "n": <十进制字符串>, "program": <程序节点> }`，响应 `{ "count": <十进制字符串> }`。全程任意精度整数运算，结果以字符串返回，不丢失精度。

程序节点（`type` 判别，可任意嵌套，body 不引用外层变量）：

| 节点 | 字段 | 计数含义 |
| --- | --- | --- |
| `op` | 无 | 1 |
| `seq` | `items: 节点[]` | 各子项计数之和（空数组为 0） |
| `repeat` | `times`, `body` | `times × body 计数`；times 为 0..10⁶ 的整数（布尔值拒绝）或字符串 `"n"` |
| `double` | `body` | 倍增执行：值 1,2,4,… 直到不超过 n，共 `⌊log2 n⌋+1` 轮，每轮执行一次 body |
| `triangle` | 无（带 body 等额外字段会被拒绝） | 固定单位体的 1+2+…+n = n(n+1)/2 |

计数全部使用闭形式（乘法/求和公式/位运算），**不按 n 或 times 展开循环**；例如 15 层嵌套 `repeat(times=10⁶)` 立即算出 10⁹⁰。

边界与限制：

- `n`：十进制数字字符串，取值 1..10¹⁸（允许前导 0；`0`、空串、负数、小数、科学计数法均拒绝）。
- `times`：整数 0..10⁶（含端点）或字符串 `"n"`；`true/false`（即使是 int 子类）、浮点、null、其他字符串均拒绝。
- 程序树最多 **200 个节点**、最大深度 **16**（根节点深度为 1）；预算在进入节点时检查（先判对象类型，再查深度，再累计节点数）。
- 拒绝未知字段、缺失字段与类型错误；错误路径为输入树**先序遇到的首个**错误的 JSONPath（如 `$.program.body.items[1].times`）。
- 任何输入错误返回 **HTTP 422** `{ "code": <错误码>, "path": <JSONPath> }`，`code` 取值：`invalid_json`、`type_error`、`missing_field`、`unknown_field`、`invalid_value`、`out_of_range`、`node_limit`、`depth_limit`、`unknown_node`。请求体仅作为数据解释，绝不作为代码执行。

示例：

```bash
curl -s -X POST http://127.0.0.1:25512/api/analysis/count \
  -H 'content-type: application/json' \
  -d '{"n":"8","program":{"type":"double","body":{"type":"op"}}}'
# {"count":"4"}
```

前端“数据结构实验台”页面提供 n 与 program 的编辑面板；封装见 `frontend/src/analysis.ts`（422 时抛出携带 code/path 的 `AnalysisRequestError`）。

## A/B 工作区

首次运行前完整复制已验证代码到独立 a/b，初始 HEAD 相同，分支不同。在各自目录执行：

```powershell
# A: 使用独立 PowerShell 会话
$env:WEB_PORT='25511'
docker compose -p stand01-ch01-r001-t01-a up -d --no-build --wait
# B: 在另一个 PowerShell 会话与 b 目录中
$env:WEB_PORT='25512'
docker compose -p stand01-ch01-r001-t01-b up -d --no-build --wait
```

A/B 均复用同一次构建的镜像，项目名隔离网络及依赖卷，源码绑定各自目录；容器内路径一致。不共用可写 node_modules 或宿主 venv。运行测试命令中的 -p 替换为对应项目名。新机器需先从锁文件构建；跨机器重建不声称镜像字节完全相同。

不覆盖正在运行或未归档的工作区。依赖变化必须在下一题开始前统一构建和初始化，不在同题两边各自解析依赖。停止用 docker compose -p 对应项目名 stop，不随意删除数据卷。
