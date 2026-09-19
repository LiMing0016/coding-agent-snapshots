# 串行 A/B 基线恢复工具

同一道题先 A 后 B；不同项目可同时运行。只管理配置指定的独立 stateDir，不操作原项目。需要 Python 3.10+、Git、Docker Compose v2；Windows 推荐 PowerShell 7。整目录复制即可分发，无第三方 Python 依赖。

## 先准备配置

复制 examples 中对应 JSON 到本地管理目录，修改 source、ref、stateDir、id、端口及项目自身的回调/前端 API 地址。source 必须是本地已提交 Git 仓库；ref 必须能解析到准确提交。配置文件不得放在 stateDir 或模型工作区内。每道题使用不同 stateDir、id、宿主端口，不要复用示例编号。

source 只用于克隆，不被修改。工具运行目录固定为 stateDir/work。模型每次只打开这个目录，不把状态、证据、快照目录加入工作区。此工具不提供操作系统权限沙箱；有全盘权限的模型仍可能访问其他目录。

`S` 就是 freeze 保存的基线：固定提交、完整工作目录、容器镜像和初始数据卷的组合。它不是 main 分支；restore-b 不会从持续变化的 main 恢复。正式运行前，将配置中的初始提交推送到独立 base 分支并记录永久提交链接。

## 操作流程

以下 CONFIG.json 是你已经填写的配置，prompt.txt 是你自己出的完整题目。

```powershell
./ab.ps1 init --config CONFIG.json
./ab.ps1 start --config CONFIG.json
# 在新建的 work 环境准备合成账号、数据库和文件数据，验证所选题目可运行。
# 若修改了受 Git 跟踪的文件，应先在准备仓库提交并用新的 ref、新的 stateDir 重新 init。
./ab.ps1 freeze --config CONFIG.json --prompt prompt.txt
./ab.ps1 start --config CONFIG.json
# 新建 A 会话，只打开 stateDir/work，发送 snapshot/prompt.txt 的原文。
```

freeze 会停止容器，备份完整工作目录（含 .git 和被忽略的运行文件）与所有挂载命名卷，记录 SHA256 和实际镜像 ID。备份期间不要编辑工作目录或启动容器。冻结后不会自动启动 A，便于核对宿主配置。

模型完成 A 后，先提交并推送：在 work 中运行 `git add`、`git commit`，再 `git push -u origin HEAD`。不要 squash。没有代码变化时可以直接推送当前分支，不强制制造提交。保存轨迹、实际运行录屏，然后：

```powershell
./ab.ps1 finish-a --config CONFIG.json --session A的会话ID --trace A.jsonl --recording A.mp4
./ab.ps1 restore-b --config CONFIG.json
./ab.ps1 start --config CONFIG.json
# 新建 B 会话，同一个工作目录、相同 Prompt，不继承 A 会话。
```

finish-a 核验 A 工作树干净、初始提交是祖先、远端对应分支与 A HEAD 完全相同，复制非空证据文件。它无法判断录屏是否真实完整、SessionID 是否正确或运行时是否实际使用指定 Prompt，需要操作者核对。

restore-b 验证备份与证据摘要，移除本工具的旧容器/网络（不删卷），将整个 A 工作区保留为 preserved-a-work，再恢复到相同 work 路径；B 使用从基线档案恢复的新卷。A 原卷、目录、远端分支及证据均保留。只恢复代码/数据，不自动开始 B 会话。

B 完成后同样提交、push、保存 SessionID/轨迹/录屏。当前脚本的自动证据收集针对 A 恢复门槛；B 结果按交付表另行留存。

```powershell
./ab.ps1 status --config CONFIG.json
./ab.ps1 stop --config CONFIG.json
```

## 并行不同项目

分别使用两个配置执行上述命令即可。示例 PEAI 使用 23300/28081/28012，DataX 使用 25432/28123。容器项目名含 id 与状态目录摘要，网络/数据卷隔离；同一配置有互斥锁，拒绝并发修改。Docker 会拒绝已被占用的端口。更换端口时还必须更换项目自己的 API/回调地址（environment），不是只改端口映射。

## 保证范围与限制

- 恢复基线代码、被忽略的本地文件、命名卷，以及相同镜像 ID、端口、容器内服务名与环境变量；A/B 的物理卷名不同，数据初值一致。
- 仅支持默认 Compose profile、普通本地卷及 work 内绑定。外部卷、匿名卷、宿主网络、特权模式、额外构建上下文、符号链接/junction 等会拒绝。按题目启用额外服务时，先创建不带可选 profile 的专用 Compose 再初始化。
- 不能恢复浏览器存储、Codex/Claude 用户目录、插件、技能、模型端状态、宿主全局安装或数据库外部服务。开跑前人工核对相同客户端版本、权限、模型配置；浏览器用相同干净配置，暂停自动更新。不同项目争用硬件仍可能影响耗时。
- start 冻结前可能下载依赖；冻结后复用本机已存在镜像 ID，不支持直接把 stateDir 移到另一台电脑重跑。分发的是脚本和配置模板；每台电脑须各自准备基线。
- 冻结后 start 不重新构建镜像。题目代码若被打包在镜像内而非源码绑定目录，需给 A/B 提供相同的构建验证命令；本工具的 start 只负责恢复初始环境。
- stateDir 可能含密钥/数据/完整轨迹，必须保存在本机，不上传 GitHub。备份空间至少覆盖源码运行目录、所有依赖/数据卷及 A 保留副本。
- runtime.json 和快照不要手改。异常中断会保留数据并拒绝继续（restoring-b 或锁文件），不要盲目重试/删状态；先检查进程和保存的快照。恢复失败没有自动回滚，但 A 原始数据不会被删除。
- 工具不自动删除任何快照或卷，不使用 reset --hard、clean、volume prune 或 down -v。

## 测试

```powershell
python -m unittest -v test_baseline.py
python integration_test.py
```

集成测试只使用临时 Git 仓库、测试凭据与独立 Docker 资源，验证完整恢复及两个项目同时运行。结束停止测试容器并保留测试档案，不触碰正式数据。
