# omp LSP 在 monorepo 子工程下的配置经验

> 沉淀自补齐 omp LSP 覆盖的过程：为 `backend/`（Python）与 `frontend/`（Vue+TS）两个子工程配置 `.omp/lsp.json`，使定义跳转 / hover / symbols / diagnostics 全链路可用。

---

## 背景

仓库根是 monorepo cwd，真正的工程根在子目录：
- Python 工程：`backend/`（`pyproject.toml`、`.venv/`、`pyrightconfig.json`）
- 前端工程：`frontend/`（`package.json`、`eslint.config.js`、`node_modules/`）

omp 的 LSP 机制（源码：`@oh-my-pi/pi-coding-agent/src/lsp/config.ts`、`client.ts`）有两处 cwd-only 行为直接决定配置写法，**不读源码极易踩坑**。

---

## Gotcha 1：rootMarkers 与 binary 解析均为 cwd-only（不递归子目录）

`hasRootMarkers(cwd, markers)` 只在 cwd 顶层 `readdir` 一次，**不递归子目录**。`resolveCommandFromLocalRoot` 也只查 `cwd/<binDir>/<command>`。

因此子工程根的 marker（`backend/pyproject.toml`、`frontend/package.json`、`frontend/eslint.config.js`）在仓库根 cwd **全部不命中**。

**修复**：统一用 `.git` 作 rootMarker（仓库根必有），binary 走 `$PATH` 或绝对路径。

```jsonc
// .omp/lsp.json
"pyright": { "rootMarkers": [".git"] },
"ruff":    { "rootMarkers": [".git"] },
"typescript-language-server": { "rootMarkers": [".git"] },
"vue-language-server":        { "rootMarkers": [".git"] },
"eslint":  { "rootMarkers": [".git"] }
```

> 禁用 clangd：仓库根有 `Makefile` 会命中 clangd 默认 rootMarker，但本仓库无 C/C++ 代码，需显式 `"clangd": { "disabled": true }`。

---

## Gotcha 2：binary 不在 omp 进程 PATH → loadConfig 静默过滤

`loadConfig` 末尾对每个 server 执行：
```ts
const resolved = resolveCommand(config.command, cwd);
if (!resolved) continue;   // ← 静默丢弃，无日志
```

`resolveCommand` = local bin（cwd-only）→ `$which(command)`（用 `process.env.PATH`）。

**症状**：server 从不出现在 `lsp status`，对该语言的操作（如 `definition`）落到同 fileTypes 的其它 server，返回 `-32601 Unknown request`。

本仓库实证：
- `pyright-langserver` 装在 `~/.local/bin`，omp 主进程 PATH 含 nvm bin（eslint/ts-ls 能起来）但**不含 `~/.local/bin`** → pyright 被过滤 → `.py` 的 `definition` 全被 ruff 接管（ruff server 不实现 definition）→ `-32601`。
- ruff 在 `~/.pyenv/shims`，同样可能不在 omp PATH。

**修复**：在 server 条目显式给绝对路径 `command`，绕过 PATH 不确定性。

```jsonc
"pyright": { "command": "/Users/sacrtap/.local/bin/pyright-langserver", "rootMarkers": [".git"] },
"ruff":    { "command": "/Users/sacrtap/.pyenv/shims/ruff", "rootMarkers": [".git"] }
```

> 排查命令：`lsp status` 若某 server 从不出现，先 `which <binary>` 确认 binary 在 omp 进程 PATH；不在则给绝对路径 `command`。

---

## Gotcha 3：eslint ls 的 settings 必须包在 `""` 键下

eslint-language-server 用 `connection.workspace.getConfiguration({ section: '' })` 拉配置。omp 的 `handleConfigurationRequest` 应答：
```ts
return client.config.settings?.[section] ?? null;   // section === ""
```

若 settings 写成扁平结构（`{ "validate": "on", ... }`），`settings[""]` 为 `undefined` → 返回 `null` → eslint 在 `reading 'workingDirectory'` 处崩溃：
```
LSP error -32603: Request textDocument/diagnostic failed
  with message: Cannot read properties of null (reading 'workingDirectory')
```

**修复**：settings 必须放在 `""` 键下：

```jsonc
"eslint": {
  "rootMarkers": [".git"],
  "settings": {
    "": {                                  // ← 必须包在 "" 键下
      "validate": "on",
      "run": "onType",
      "nodePath": "frontend/node_modules", // cwd 是仓库根，从根解析不到 eslint 库
      "workingDirectory": { "mode": "location" },
      "experimental": { "useFlatConfig": true }
    }
  }
}
```

要点：
- `nodePath` 指向 `frontend/node_modules`：eslint ls fork 子进程解析 eslint 库时设为 NODE_PATH，从仓库根解析不到。
- `workingDirectory.mode: "location"` + `useFlatConfig: true`：让 ls 从文件路径向上找 `frontend/eslint.config.js`，锁定 frontend 为工作目录。

---

## Convention：vue-language-server 锁 2.x + 显式 tsdk

`@vue/language-server` 3.x 起改为**由客户端转发 `tsserver/request`**，omp 的 LSP client 未实现该转发 → 3.x 下 vue 文件的 TS 能力不可用。

**修复**：锁 2.x（`npm i -g @vue/language-server@2.2.12`），并在 `initOptions` 传 tsdk（2.x 需客户端经 `initializationOptions.typescript.tsdk` 指定 TS SDK，走自建 ts project）：

```jsonc
"vue-language-server": {
  "rootMarkers": [".git"],
  "initOptions": {
    "typescript": { "tsdk": "frontend/node_modules/typescript/lib" },
    "vue": { "hybridMode": false }
  }
}
```

> `hybridMode: false` 走 vue ls 自建 ts project；3.x 的 `hybridMode: true` 依赖客户端转发，不可用。

---

## Gotcha 4：改配置后必须 reload；杀 mux 持有的 client 会损坏 mux

- 改 `.omp/lsp.json` 后必须 `{"action":"reload","file":"*"}` 才重读（`configCache` 按 cwd 缓存）。
- **切勿 `kill` 掉 mux 已持有的 LSP client 进程**：mux 内部仍认为 client 活着，后续请求静默挂死直到超时（`Operation aborted`，且无日志）。误杀后需重启 lsp mux daemon：
  ```bash
  pkill -f "__omp_worker_lsp_mux"; pkill -f "lsp_mux"
  # 下一次 lsp 调用会自动重建 mux
  ```

---

## 验证清单（全绿即 LSP 覆盖完整）

| Server | symbols | definition（跨文件） | hover | diagnostics |
|--------|:---:|:---:|:---:|:---:|
| typescript-language-server | ✓ | ✓ `customers.ts:2 PricePolicy` → `types/index.ts:80` | ✓ interface | ✓ |
| vue-language-server | ✓ template/script/style | ✓ `PageHeader.vue:16 eyebrow` → defineProps | — | — |
| eslint | — | — | — | ✓ `OK`（用含违规的临时文件复测检出 `no-explicit-any`） |
| pyright | ✓ | ✓ `main.py:17 settings` → `config.py:97` | ✓ `(variable) settings: Settings` | ✓ hint |
| ruff | — | — | — | ✓（与 pyright 在同次 diagnostics 里共存） |

> eslint 诊断对 `customers.ts` 返回 `OK` 是因为该文件无违规；要确认链路真能检出，临时写 `const x: any = 1;` 复测后删除。

---

## Checklist

- [ ] monorepo 子工程下，所有 LSP server 的 `rootMarkers` 统一用 `[".git"]`（cwd-only 不递归子目录）
- [ ] `lsp status` 从不出现的 server：`which <binary>` 确认不在 omp PATH → 给绝对路径 `command`
- [ ] `-32601 Unknown request` 意味着目标 server 被过滤、请求落到同 fileTypes 的 linter → 检查 `command` 解析
- [ ] eslint settings 必须包在 `""` 键下（`Cannot read properties of null (reading 'workingDirectory')` 即未包）
- [ ] eslint 的 `nodePath` 指向 `frontend/node_modules`、`workingDirectory.mode: "location"` + `useFlatConfig: true`
- [ ] vue-language-server 锁 2.x + `initOptions.typescript.tsdk`，`hybridMode: false`
- [ ] 无 C/C++ 代码时 `"clangd": { "disabled": true }`
- [ ] 改 `.omp/lsp.json` 后 `{"action":"reload","file":"*"}`
- [ ] 勿 kill mux 持有的 LSP client；误杀后 `pkill -f __omp_worker_lsp_mux` 重建
