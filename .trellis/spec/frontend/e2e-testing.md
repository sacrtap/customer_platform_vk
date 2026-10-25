# E2E Testing Guidelines

> Playwright E2E patterns for the Vue 3 + Arco Design SPA: isolation, timing,
> and the layout-parent-component trap.

## Scope / Trigger

- 触发：新增/改造 E2E 用例（`frontend/tests/e2e/**.spec.ts`）、排查 E2E 超时、
  引入会触发全屏遮罩的弹窗组件
- 适用于所有 Playwright 用例与会被其触达的前端组件

---

## 基本约定

- 用例文件位于 `frontend/tests/e2e/`；`playwright.config.ts` 硬编码
  `baseURL: 'http://localhost:5173'`，本地跑前需 `npx vite preview --port 5173`
- 登录态由 `global-setup.ts` 注入 `tests/e2e/.auth/admin.json`（storageState）；
  `fixtures.ts` 的 `authenticatedPage` fixture 自动复用它
- 改前端源码后必须 `npm run build` 重建 `dist`——`vite preview` 服务的是 `dist/`，
  不重建跑的是旧产物
- 跑前清 `rm -rf tests/e2e/.auth tests/e2e/test-results`，避免残留 storageState
  污染
- 用 `@smoke` 标签筛快速反馈：`npx playwright test --grep="@smoke"`

---

## 布局父组件弹窗陷阱（关键）

`frontend/src/router/index.ts` 中 `/` 路由组件是 `Dashboard.vue`，`customers` /
`users` / `roles` / `billing/*` 等**全部**业务路由都是它的 **children**。因此
Dashboard 的 `onMounted` 副作用（如系统升级公告请求）在**每一个**需登录页面都会
触发。

Arco `a-modal`（`UpgradeAnnouncementModal` 等）通过 Teleport 挂到 `document.body`，
其 `mask-closable=false` 的全屏遮罩**不随路由切换销毁**，会拦截页面所有指针事件。
一旦该弹窗在目标页弹出，依赖点击的业务用例必然超时——这是 PR #75 E2E 全红的根因。

**推论**：任何在布局父组件（`/` → `Dashboard.vue`）`onMounted` 里发起的、可能
触发全屏遮罩弹窗的异步请求，都会污染所有 children 路由的 E2E。

---

## 抑制全屏遮罩弹窗：预写已读键，而非等弹窗再关

### 方案

在登录后、导航到目标页**之后**立即预写公告的「已读」localStorage 键（按组件的
「用户 × 浏览器」口径），取一个远未来的 ISO UTC 串：

```ts
// frontend/tests/e2e/test-helpers.ts
export async function suppressUpgradeAnnouncement(page: Page): Promise<void> {
  await page.evaluate(() => {
    const raw = localStorage.getItem('user_info')
    /* ...解析 uid... */
    localStorage.setItem(`upgrade_announcement_last_read_${uid}`, '9999-12-31T23:59:59Z')
  })
}
```

`9999-12-31T23:59:59Z` 词法上必然 ≥ 任何真实部署时间，使组件的
`latest > lastRead` 判定为 false → 不弹。

### 时序（成败关键）

`suppressUpgradeAnnouncement` **必须在公告接口返回之前**写键：

- 请求返回并发现 `lastRead` 为空 → 立即弹窗；弹窗出现后写键**无法关闭**当前弹窗
  （Arco modal 的 visible 由组件状态控制，不监听 localStorage 变化）
- 正确顺序：`waitForURL('/')`（导航达成）→ `suppressUpgradeAnnouncement(page)`
  → `waitForLoadState('networkidle')`
- `waitForURL` 达成时 Dashboard 已 `onMounted` 且已发起出站请求（GitHub 匿名请求
  可达数秒），此时立即写键仍赶在请求返回之前
- **切勿**放在 `waitForLoadState('networkidle')` 之后：`networkidle` 本就要等
  该请求结束才达成，此时弹窗早已弹出

### 何不用「等弹窗出现再点关闭」

- 有时序窗口：`beforeEach` 里 `goto('/')` 后 3s 内接口常未返回，`beforeEach` 已
  结束，漏点
- 弹窗已出现时写键也不关闭当前弹窗（见上）
- 慢且不可靠

---

## 自建 context 的用例需自行抑制

`test_responsive.spec.ts` 等用 `browser.newContext({ storageState: { cookies: [],
origins: [] } })` 自建 context 登录，**不吃** global-setup 的 storageState，故必须
在**每个登录点**自行调用 `suppressUpgradeAnnouncement(page)`。复用 storageState 的
用例则从 `global-setup.ts` 预写的键直接受益，无需逐用例处理。

---

## networkidle 与出站请求

`waitForLoadState('networkidle')` 要求 500ms 内无网络活动。当布局父组件的
`onMounted` 发起慢出站请求（如 GitHub 匿名请求 3-4s）时，`networkidle` 会被反复
打断。base 版（无该请求）能秒级达成，引入慢请求后可能拖到数十秒甚至超时。

规避：要么在 `onMounted` 里把非首屏请求延迟到 `window` `load` 事件之后
（见 `Dashboard.vue` 公告段），要么用例侧改用 `waitForSelector('.side')` 等具体
元素等待，不依赖全网络静默。

---

## See Also

- [Component Guidelines](./component-guidelines.md) — Arco modal Teleport 行为、
  visible 父组件持有约定
- [Quality Guidelines](./quality-guidelines.md) — lint/type-check 命令、pre-commit
  陷阱
