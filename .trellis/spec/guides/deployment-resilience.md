# 部署韧性规范（Deployment Resilience）

> **Purpose**: 让部署链路在任何环节挂起时都能**快速失败**，而不是无限期占用 job、拖垮线上可用性。

---

## 基线问题（2026-11-03）

staging 部署 run [41632883887](https://github.com/sacrtap/customer_platform_vk/actions/runs/41632883887) attempt 1 卡死 30 分钟，站点持续 502，靠人工取消才结束。

无歧义时间线（远端部署日志）：

```
12:18:09  执行 compose stop...
12:18:19  StopSignal SIGTERM failed ... resorting to SIGKILL   ← app/nginx 被强杀
12:18:24  旧容器已停止
12:18:24  [STEP] 从 GHCR 拉取后端镜像
12:18:27  Getting image source signatures
12:18:27  Copying blob × 16（同一秒内全部出现）
12:48:01  ##[error]The operation was canceled.   ← 30 分钟后被外部取消
```

### 根因

`podman pull` 在 **TCP 半开**状态下（连接已建立、服务端不再回数据）**不会退出，无限等待**。三层超时缺失叠加：

1. `deploy.sh` 的 `pull_remote_image` 直接 `podman pull`，无超时无重试
2. `deploy-staging` job 未设 `timeout-minutes`，默认上限 360 分钟
3. **CI 侧重试循环覆盖不到远端挂起**——远端 podman 挂起时 SSH 通道本身是活的（`ServerAliveInterval=60`/`CountMax=10` 在保活），远端命令不返回非零退出码 → 重试机制不触发

### 被排除的假设（避免后续重复排查）

| 假设 | 排除依据 |
|---|---|
| 代码变更引入 | 近期 PR 均未触及 `deploy/`、`deploy.yml`、`requirements.txt`、`Containerfile` |
| 镜像层数暴涨 | 11-02 成功与 11-03 失败同为 16 层、4 层本地缓存重叠；PGDG 18 改动是 10-30 的，11-02 那次已包含并成功 |
| runner / Node 版本 | 日志显示 runner 与 cloudflared 均正常，scp 传完、远端脚本已开跑；卡点在远端服务器内部 |

### 放大的次因：停容器早于拉镜像

`main()` 原顺序是 `stop_containers` → `pull`。镜像拉不动时旧服务已被干掉，502 窗口 = 整个 pull 时长。

---

## 修复后的形态

### 1. 拉取统一走超时 + 重试

`pull_image_with_retry` 被 `pull_remote_image` 与 `ensure_image` 共用：

| 变量 | 默认 | 说明 |
|---|---|---|
| `PULL_TIMEOUT` | `300` | 单次拉取超时（秒） |
| `PULL_MAX_RETRIES` | `3` | 重试次数 |
| `PULL_RETRY_DELAY` | `5` | 重试间隔（秒） |

### 2. `run_with_timeout` 三层降级

`timeout` → `gtimeout` → bash 看门狗。**看门狗是实测踩坑后的结果**，三个坑必须记住：

| 坑 | 现象 | 正解 |
|---|---|---|
| 用「`sleep N` 后 `touch` 标志」判定 | 命令先结束、sleep 后到点，`kill -0` 检查与 `touch` 之间存在调度竞态，**把成功也判成超时**（`ok` 场景 rc=1） | 用命令自身的退出码判定 |
| `trap 'exit 137' KILL` | **shellcheck SC2173 error 级**——SIGKILL 不可捕获，CI 会拦 | 只 `trap TERM`；KILL 由看门狗直接发，退出码 137 同样落入判定 |
| TERM 只发给 subshell | 子进程（`podman pull`）收不到信号，**判定超时后仍白等 30s 且进程残留**（实测单轮 33s） | 命令跑在独立进程组（`set -m` + 后台作业），用 `kill -TERM -- -PID` 一次终止整组 |

终版判定：`143`（128+SIGTERM）/`137`（128+SIGKILL）→ 返回 `124`（timeout 语义）；其余为命令自身退出码。

### 3. 部署顺序：先拉镜像，再停容器

```bash
check_dependencies → check_config → load_env → pre_deploy_check
→ pull（拉不动在这里 exit 1，旧服务仍在运行）
→ stop_containers → run_migrations → start_services → health_check
```

**这是对可用性影响最大的一条**：把 502 窗口从「整个 pull 时长」缩短到「重启容器的十几秒」。

### 4. GitHub Actions job 显式 `timeout-minutes`

默认 360 分钟 = 无限。所有会跑远端命令的 deploy job 都要设（本项目设 20：含两次拉取，各 300s × 3 次重试，正常分钟级完成）。

---

## Pre-Modification Checklist

改 `deploy/` 或 `deploy.yml` 前逐条确认：

- [ ] 新增的远端命令是否可能挂起？→ 必须包 `run_with_timeout` 或 `pull_image_with_retry`
- [ ] job 是否有 `timeout-minutes`？（不许依赖默认 360）
- [ ] 「先拉后停」顺序有没有被改回去？
- [ ] 健康检查的 URL 是否只覆盖**本次真正部署成功**的环境？（曾把 staging 失败误查 production URL）
- [ ] 新加的 bash 是否过 `shellcheck -S error`？（CI 有 `Shell & Workflow Static Checks`）

---

## 验证方式（改动 `deploy.sh` 后必做）

不能只 `bash -n`。要从真实 `deploy.sh` **抽取函数**配 stub 运行时实测三种场景：

```bash
# 只加载日志与拉取相关函数，避免执行 main
eval "$(awk '/^# 用 timeout 包裹命令/,/^# 带超时与重试|^pull_image_with_retry/' deploy/scripts/deploy.sh | grep -vE '^PULL_')"
```

| 场景 | stub 行为 | 期望 |
|---|---|---|
| `fail` | 立即 `exit 1` | 重试 3 次后 `rc=1` |
| `ok` | 立即 `exit 0` | 立即 `rc=0`，耗时 0s |
| `hang` | `sleep 300`（模拟 TCP 半开） | 每轮 `PULL_TIMEOUT` 判超时并重试，**零残留进程** |

本机 macOS 无 `timeout`/`gtimeout`（`/usr/local/bin/timeout` 不存在），正好强制走 bash 看门狗分支——**不要因此跳过 hang 场景**，那正是本次故障形态。

---

## 预期改进（可对照验证）

| 项 | 修复前 | 修复后 |
|---|---|---|
| 远端 pull 挂起 | 无限等待，30 分钟靠人工取消 | 单轮 300s 判超时，3 次重试共约 15 分钟后 `exit 1` |
| 502 窗口 | 整个 pull 时长 | 重启容器的十几秒 |
| job 占用上限 | 360 分钟（默认） | 20 分钟 |
| 本地 hang 单轮实测 | 33s（白等 KILL 窗口） | 3s（进程组一次终止） |

**下次同类故障的排查入口**：先看远端日志里 `Copying blob` 最后一行的时间戳，与 job 被取消时间的差值；再看旧容器 `compose stop` 是否早于 pull。
