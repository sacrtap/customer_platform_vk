# 仪表盘数据获取优化设计

**日期**: 2026-06-29
**状态**: 已批准
**方案**: 性能优先（方案 A）

---

## 1. 背景与问题

### 1.1 当前实现

仪表盘首页（`frontend/src/views/Home.vue`）通过 4 个 API 获取数据：

1. `getDashboardStats()` - 8 项统计数据（客户数、余额、结算单等）
2. `getDashboardChartData({ months: 12 })` - 月度消耗趋势图数据
3. `getPendingTasks()` - 待办事项
4. `getRecentInvoices(10)` - 最近 10 条结算单

### 1.2 存在的问题

| 问题 | 影响 | 严重程度 |
|------|------|----------|
| **串行加载** | 4 个 API 依次调用，总耗时 = 所有 API 耗时之和（~800ms） | 高 |
| **无前端缓存** | 每次进入页面都重新请求，即使数据未变化 | 高 |
| **无分区加载状态** | 无法看出哪个部分正在加载，用户体验差 | 中 |
| **无错误恢复** | 某个 API 失败后无重试机制，整个页面可能白屏 | 中 |
| **无自动刷新** | 数据可能过期但不会自动更新 | 低 |

### 1.3 后端现状

后端已有优化基础：
- 统计查询从 6 次优化到 2 次聚合查询
- Redis 缓存：统计数据 5 分钟，图表数据 15 分钟
- 缓存键设计：`analytics_dashboard_stats`, `analytics_dashboard_chart`

---

## 2. 优化目标

### 2.1 性能目标

| 指标 | 当前值 | 目标值 | 提升幅度 |
|------|--------|--------|----------|
| 首次加载时间 | ~800ms | ~200ms | 75% ↓ |
| 二次加载时间 | ~800ms | ~50ms | 94% ↓ |
| 网络请求数 | 4 次/页面进入 | 0-4 次（智能缓存） | 最多减少 100% |

### 2.2 用户体验目标

- ✅ 分区加载状态：每个区域独立显示 loading
- ✅ 错误隔离：单个区域失败不影响其他区域
- ✅ 降级显示：API 失败时显示缓存数据或友好提示
- ✅ 无感知刷新：数据过期时后台静默更新

---

## 3. 设计方案

### 3.1 整体架构

**优化前（串行）：**
```
页面加载 → loadStats() → loadChartData() → loadTodos() → loadRecentInvoices()
         [200ms]      [300ms]           [150ms]        [150ms]
         总耗时：800ms（串行）
```

**优化后（并行）：**
```
页面加载 → Promise.all([
            loadStats(),      [200ms] ┐
            loadChartData(),  [300ms] ├→ 总耗时：300ms（并行）
            loadTodos(),      [150ms] │
            loadRecentInvoices() [150ms] ┘
          ])
```

### 3.2 核心设计原则

**原则 1：独立数据区域**
- 每个数据区域（统计卡片、图表、待办、结算单）独立加载
- 单个区域失败不影响其他区域
- 每个区域有独立的 loading 状态

**原则 2：分层缓存策略**
```
请求发起 → 检查前端缓存（localStorage）
         ├→ 命中且未过期 → 直接返回（~5ms）
         └→ 未命中或过期 → 发起 API 请求
                           ├→ 成功 → 更新缓存 + 返回数据
                           └→ 失败 → 返回缓存数据（降级）+ 标记过期
```

**原则 3：智能刷新机制**
- 数据 TTL：统计数据 5 分钟，图表 15 分钟，待办/结算单 2 分钟
- 后台刷新：数据过期时先显示缓存，后台静默更新
- 手动刷新：用户点击刷新按钮时强制更新所有数据

### 3.3 数据流设计

```typescript
// 伪代码示例
const loadData = async (forceRefresh = false) => {
  // 1. 并行加载所有数据
  const [stats, chart, todos, invoices] = await Promise.all([
    loadWithCache('stats', getDashboardStats, 5 * 60 * 1000, forceRefresh),
    loadWithCache('chart', getDashboardChartData, 15 * 60 * 1000, forceRefresh),
    loadWithCache('todos', getPendingTasks, 2 * 60 * 1000, forceRefresh),
    loadWithCache('invoices', getRecentInvoices, 2 * 60 * 1000, forceRefresh),
  ])
  
  // 2. 更新各个区域状态
  updateStats(stats)
  updateChart(chart)
  updateTodos(todos)
  updateInvoices(invoices)
}
```

---

## 4. 组件层实现

### 4.1 核心工具函数：`useCachedRequest`

创建一个可复用的 composable，封装缓存 + 并行加载逻辑：

```typescript
// composables/useCachedRequest.ts
interface CacheEntry<T> {
  data: T
  timestamp: number
}

export function useCachedRequest<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttl: number // 毫秒
) {
  const userStore = useUserStore()
  const userId = userStore.userInfo?.id || 'anonymous'
  const cacheKey = `dashboard_${key}_${userId}`
  
  const getCache = (): T | null => {
    const raw = localStorage.getItem(cacheKey)
    if (!raw) return null
    const entry: CacheEntry<T> = JSON.parse(raw)
    if (Date.now() - entry.timestamp > ttl) return null
    return entry.data
  }

  const setCache = (data: T) => {
    localStorage.setItem(cacheKey, JSON.stringify({
      data,
      timestamp: Date.now()
    }))
  }

  const getStaleCache = (): T | null => {
    const raw = localStorage.getItem(cacheKey)
    if (!raw) return null
    try {
      const entry: CacheEntry<T> = JSON.parse(raw)
      return entry.data // 返回过期数据作为降级
    } catch {
      return null
    }
  }

  const execute = async (forceRefresh = false): Promise<T> => {
    // 1. 检查缓存
    if (!forceRefresh) {
      const cached = getCache()
      if (cached) return cached
    }

    // 2. 发起请求
    try {
      const data = await fetcher()
      setCache(data)
      return data
    } catch (error) {
      // 3. 请求失败，尝试返回过期缓存
      const staleCache = getStaleCache()
      if (staleCache) {
        Message.warning('数据更新失败，显示的是缓存数据')
        return staleCache
      }
      throw error
    }
  }

  return { execute }
}
```

### 4.2 Home.vue 改造

**当前实现问题：**
```typescript
// 串行加载，总耗时 = 所有 API 之和
onMounted(() => {
  loadStats()      // 200ms
  loadChartData()  // 300ms
  loadTodos()      // 150ms
  loadRecentInvoices() // 150ms
  // 总计：800ms
})
```

**优化后实现：**
```typescript
// 1. 初始化缓存请求器
const statsRequest = useCachedRequest('stats', getDashboardStats, 5 * 60 * 1000)
const chartRequest = useCachedRequest('chart', getDashboardChartData, 15 * 60 * 1000)
const todosRequest = useCachedRequest('todos', getPendingTasks, 2 * 60 * 1000)
const invoicesRequest = useCachedRequest('invoices', () => getRecentInvoices(10), 2 * 60 * 1000)

// 2. 独立的加载状态
const statsLoading = ref(false)
const chartLoading = ref(false)
const todosLoading = ref(false)
const invoicesLoading = ref(false)

// 3. 并行加载
const loadAllData = async (forceRefresh = false) => {
  await Promise.all([
    loadStats(forceRefresh),
    loadChartData(forceRefresh),
    loadTodos(forceRefresh),
    loadRecentInvoices(forceRefresh),
  ])
}

const loadStats = async (forceRefresh = false) => {
  statsLoading.value = true
  try {
    const data = await statsRequest.execute(forceRefresh)
    Object.assign(stats, data)
  } catch (error) {
    console.error('加载统计失败:', error)
    Message.error('加载统计数据失败')
  } finally {
    statsLoading.value = false
  }
}

// 其他 load 函数类似...

onMounted(() => {
  loadAllData()
  window.addEventListener('resize', handleResize)
})
```

### 4.3 模板层改造

**当前问题：** 整体 loading，无法看出哪个区域在加载

**优化后：**
```vue
<template>
  <div class="home-page">
    <!-- 统计卡片 - 独立 loading -->
    <div class="stats-grid">
      <a-spin :loading="statsLoading">
        <StatCard title="客户总数" :value="formatNumber(stats.totalCustomers)" />
        <!-- 其他卡片 -->
      </a-spin>
    </div>
    
    <!-- 内容网格 - 分区 loading -->
    <div class="dashboard-grid">
      <!-- 图表区域 -->
      <div class="card">
        <div class="card-header">
          <h3>月度消耗趋势</h3>
        </div>
        <a-spin :loading="chartLoading">
          <div ref="chartRef" class="chart-container"></div>
        </a-spin>
      </div>
      
      <!-- 待办区域 -->
      <div class="card">
        <div class="card-header">
          <h3>待办事项</h3>
        </div>
        <a-spin :loading="todosLoading">
          <div class="todo-list">...</div>
        </a-spin>
      </div>
      
      <!-- 结算单区域 -->
      <div class="card full-width">
        <div class="card-header">
          <h3>最近结算单</h3>
        </div>
        <a-spin :loading="invoicesLoading">
          <table>...</table>
        </a-spin>
      </div>
    </div>
  </div>
</template>
```

### 4.4 刷新按钮改造

**当前实现：**
```typescript
const refreshData = async () => {
  loading.value = true
  try {
    await Promise.all([loadStats(), loadChartData(), loadTodos(), loadRecentInvoices()])
    Message.success('数据已刷新')
  } finally {
    loading.value = false
  }
}
```

**优化后：**
```typescript
const refreshData = async () => {
  loading.value = true
  try {
    // 强制刷新，忽略缓存
    await loadAllData(true)
    Message.success('数据已刷新')
  } catch (error) {
    Message.error('部分数据刷新失败')
  } finally {
    loading.value = false
  }
}
```

---

## 5. 错误处理与边界情况

### 5.1 错误隔离策略

**核心原则：** 单个区域失败不影响其他区域

```typescript
const loadStats = async (forceRefresh = false) => {
  statsLoading.value = true
  try {
    const data = await statsRequest.execute(forceRefresh)
    Object.assign(stats, data)
  } catch (error) {
    console.error('加载统计失败:', error)
    // 不抛出错误，允许其他区域继续加载
    Message.error('加载统计数据失败')
  } finally {
    statsLoading.value = false
  }
}
```

### 5.2 降级显示策略

**场景 1：API 失败但有缓存**
```typescript
const execute = async (forceRefresh = false): Promise<T> => {
  // 1. 检查缓存
  if (!forceRefresh) {
    const cached = getCache()
    if (cached) return cached
  }
  
  // 2. 发起请求
  try {
    const data = await fetcher()
    setCache(data)
    return data
  } catch (error) {
    // 3. 请求失败，尝试返回过期缓存
    const staleCache = getStaleCache()
    if (staleCache) {
      Message.warning('数据更新失败，显示的是缓存数据')
      return staleCache
    }
    throw error
  }
}
```

**场景 2：完全无缓存且 API 失败**
- 显示友好的错误提示
- 显示重试按钮
- 其他区域正常显示

```vue
<template>
  <div v-if="statsError" class="error-state">
    <div class="error-icon">⚠️</div>
    <div class="error-message">加载统计数据失败</div>
    <a-button @click="loadStats(true)">重试</a-button>
  </div>
  <a-spin v-else :loading="statsLoading">
    <!-- 正常内容 -->
  </a-spin>
</template>
```

### 5.3 边界情况处理

**边界 1：localStorage 不可用**
```typescript
const isLocalStorageAvailable = () => {
  try {
    const test = '__test__'
    localStorage.setItem(test, test)
    localStorage.removeItem(test)
    return true
  } catch {
    return false
  }
}

// 降级方案：禁用缓存
if (!isLocalStorageAvailable()) {
  console.warn('localStorage 不可用，禁用缓存')
  // 直接调用 API，不缓存
}
```

**边界 2：缓存数据损坏**
```typescript
const getCache = (): T | null => {
  try {
    const raw = localStorage.getItem(cacheKey)
    if (!raw) return null
    const entry: CacheEntry<T> = JSON.parse(raw)
    // 验证数据结构
    if (!entry.data || !entry.timestamp) return null
    if (Date.now() - entry.timestamp > ttl) return null
    return entry.data
  } catch (error) {
    console.error('缓存数据损坏:', error)
    localStorage.removeItem(cacheKey)
    return null
  }
}
```

**边界 3：多标签页冲突**
```typescript
// 监听 storage 事件，同步其他标签页的缓存更新
window.addEventListener('storage', (e) => {
  if (e.key?.startsWith('dashboard_')) {
    // 其他标签页更新了缓存，可以选择重新加载
    console.log('检测到其他标签页更新缓存')
  }
})
```

**边界 4：内存泄漏防护**
```typescript
let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  loadAllData()
  window.addEventListener('resize', handleResize)
  window.addEventListener('storage', handleStorageChange)
  
  // 每 5 分钟检查缓存过期
  refreshTimer = setInterval(() => {
    loadAllData(false)
  }, 5 * 60 * 1000)
})

onUnmounted(() => {
  // 清理定时器
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  // 清理事件监听
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('storage', handleStorageChange)
  // 销毁图表实例
  chartInstance?.dispose()
})
```

### 5.4 性能监控

```typescript
const trackPerformance = (label: string, startTime: number) => {
  const duration = Date.now() - startTime
  console.log(`[Dashboard] ${label}: ${duration}ms`)
  
  // 可选：上报到监控系统
  // analytics.track('dashboard_load', { label, duration })
}

const loadStats = async (forceRefresh = false) => {
  const startTime = Date.now()
  statsLoading.value = true
  try {
    const data = await statsRequest.execute(forceRefresh)
    Object.assign(stats, data)
    trackPerformance('stats_load', startTime)
  } catch (error) {
    console.error('加载统计失败:', error)
    Message.error('加载统计数据失败')
  } finally {
    statsLoading.value = false
  }
}
```

---

## 6. 影响范围分析

### 6.1 文件改动清单

| 文件 | 改动类型 | 改动量 | 说明 |
|------|----------|--------|------|
| `frontend/src/composables/useCachedRequest.ts` | 新增 | ~80 行 | 缓存请求工具函数 |
| `frontend/src/views/Home.vue` | 修改 | ~150 行 | 并行加载 + 分区状态 + 错误处理 |
| `frontend/src/views/Home.vue` (template) | 修改 | ~50 行 | 分区 loading 状态展示 |

**总改动量：** 约 280 行代码

### 6.2 依赖关系

**新增依赖：** 无（仅使用原生 localStorage）

**受影响模块：**
- ✅ 仪表盘首页（`Home.vue`）
- ❌ 其他分析页面（不受影响）
- ❌ 后端 API（无需改动）

### 6.3 向后兼容性

- ✅ 完全向后兼容，不改变 API 接口
- ✅ 缓存失效时自动降级到直接请求
- ✅ 不影响其他页面的数据获取逻辑

---

## 7. 测试策略

### 7.1 功能测试

| 测试场景 | 预期结果 | 测试方法 |
|----------|----------|----------|
| 首次加载 | 从 API 获取数据，存入缓存 | 清空 localStorage，访问首页 |
| 二次加载 | 从缓存读取，不发起请求 | 访问首页后刷新页面 |
| 缓存过期 | 后台刷新，先显示缓存 | 等待 TTL 过期后访问 |
| 强制刷新 | 忽略缓存，重新请求 | 点击刷新按钮 |
| API 失败 | 显示错误提示，其他区域正常 | 模拟网络错误 |
| localStorage 不可用 | 禁用缓存，直接请求 | 浏览器禁用 localStorage |

### 7.2 性能测试

| 测试指标 | 目标值 | 测试工具 |
|----------|--------|----------|
| 首次加载时间 | < 300ms | Chrome DevTools Network |
| 二次加载时间 | < 100ms | Chrome DevTools Network |
| Lighthouse 性能分 | > 90 | Lighthouse |

### 7.3 兼容性测试

| 浏览器 | 版本 | 测试结果 |
|--------|------|----------|
| Chrome | 90+ | 待测试 |
| Firefox | 88+ | 待测试 |
| Safari | 14+ | 待测试 |
| Edge | 90+ | 待测试 |

---

## 8. 风险与缓解

### 8.1 风险识别

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| localStorage 容量不足 | 低 | 中 | 捕获异常，降级为直接请求 |
| 缓存数据损坏 | 低 | 中 | JSON 解析异常时清除缓存 |
| 多标签页冲突 | 中 | 低 | 监听 storage 事件，可选同步 |
| 浏览器兼容性 | 低 | 高 | 使用 polyfill 或降级方案 |

### 8.2 回滚方案

如果优化后出现问题，可以快速回滚：
1. 保留原有序行加载代码（注释）
2. 通过配置开关控制是否启用缓存
3. 一键回退到原始实现

---

## 9. 后续优化方向

### 9.1 短期优化（本次实现）

- ✅ 并行加载
- ✅ 前端缓存
- ✅ 分区加载状态
- ✅ 错误隔离与降级

### 9.2 中期优化（未来迭代）

- **WebSocket 实时推送** - 数据变化时主动推送，减少轮询
- **请求去重** - 多个组件请求同一数据时合并
- **预加载** - 预测用户行为，提前加载可能需要的数据

### 9.3 长期优化（未来规划）

- **Service Worker** - 离线缓存，提升弱网体验
- **GraphQL** - 按需查询，减少数据传输
- **边缘计算** - CDN 节点缓存，降低延迟

---

## 10. 验收标准

### 10.1 功能验收

- [ ] 首次加载从 API 获取数据
- [ ] 二次加载从缓存读取
- [ ] 缓存过期后自动刷新
- [ ] 强制刷新忽略缓存
- [ ] 单个 API 失败不影响其他区域
- [ ] localStorage 不可用时降级为直接请求

### 10.2 性能验收

- [ ] 首次加载时间 < 300ms
- [ ] 二次加载时间 < 100ms
- [ ] Lighthouse 性能分 > 90

### 10.3 兼容性验收

- [ ] Chrome 90+ 正常运行
- [ ] Firefox 88+ 正常运行
- [ ] Safari 14+ 正常运行
- [ ] Edge 90+ 正常运行

---

## 附录

### A. 相关文档

- [后端缓存实现](backend/app/cache/base.py)
- [分析服务实现](backend/app/services/analytics.py)
- [前端 API 定义](frontend/src/api/analytics.ts)

### B. 术语表

| 术语 | 定义 |
|------|------|
| TTL | Time To Live，缓存过期时间 |
| 降级 | 当主功能不可用时，使用备选方案 |
| 并行加载 | 多个请求同时发起，而非依次等待 |

### C. 参考资料

- [Vue 3 Composition API](https://vuejs.org/guide/extras/composition-api-faq.html)
- [Web Storage API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API)
- [Promise.all()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/all)
