<template>
  <div class="openapi-page">
    <!-- 顶部导航栏 -->
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <div class="mark">VK</div>
          <span>客户运营中台 · 开放平台文档</span>
        </div>
        <a-button type="text" @click="goHome">返回主系统</a-button>
      </div>
    </header>

    <div class="content-wrapper">
      <!-- 左侧目录 -->
      <aside class="sidebar">
        <nav class="toc">
          <div class="toc-group">
            <div class="toc-title">入门</div>
            <a href="#overview" :class="['toc-link', { active: activeSection === 'overview' }]"
              >概述</a
            >
            <a href="#auth" :class="['toc-link', { active: activeSection === 'auth' }]">认证方式</a>
          </div>
          <div class="toc-group">
            <div class="toc-title">接口列表</div>
            <a
              href="#erp-balances"
              :class="['toc-link', { active: activeSection === 'erp-balances' }]"
              >ERP 渠道客户余额查询</a
            >
          </div>
          <div class="toc-group">
            <div class="toc-title">附录</div>
            <a
              href="#error-codes"
              :class="['toc-link', { active: activeSection === 'error-codes' }]"
              >错误码说明</a
            >
          </div>
        </nav>
      </aside>

      <!-- 右侧内容区 -->
      <main class="main-content" @scroll="handleScroll">
        <!-- 概述 -->
        <section id="overview" class="doc-section">
          <h1 class="doc-title">开放平台概述</h1>
          <p class="doc-text">
            客户运营中台开放平台提供标准 RESTful API，允许外部 ERP 系统通过 API-Key
            认证方式查询客户余额等数据。 所有接口均以 JSON 格式返回数据，响应结构统一为：
          </p>
          <pre class="code-block">{{
            `{
  "code": 0,
  "message": "success",
  "data": ...
}`
          }}</pre>

          <h2 class="doc-subtitle">基础信息</h2>
          <table class="doc-table">
            <thead>
              <tr>
                <th>项目</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>API 基础路径</td>
                <td><code>https://customer-staging.jiazoushi.com/api/v1/erp</code></td>
              </tr>
              <tr>
                <td>请求方式</td>
                <td>GET / POST / PUT / DELETE（接口具体说明）</td>
              </tr>
              <tr>
                <td>数据格式</td>
                <td>JSON（<code>Content-Type: application/json</code>）</td>
              </tr>
              <tr>
                <td>字符编码</td>
                <td>UTF-8</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- 认证方式 -->
        <section id="auth" class="doc-section">
          <h1 class="doc-title">认证方式</h1>
          <p class="doc-text">
            开放平台 API 使用 API-Key 进行认证。API-Key 是一串以
            <code>vk_</code> 开头的字符串，由系统管理员在「系统管理 → API-Key」页面申请创建。
          </p>

          <h2 class="doc-subtitle">请求头格式</h2>
          <p class="doc-text">每个请求必须包含 <code>Authorization</code> 请求头，格式如下：</p>
          <pre class="code-block">{{
            `Authorization: Bearer vk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
          }}</pre>

          <h2 class="doc-subtitle">API-Key 状态说明</h2>
          <table class="doc-table">
            <thead>
              <tr>
                <th>状态</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><a-tag color="green">启用中</a-tag></td>
                <td>可正常使用</td>
              </tr>
              <tr>
                <td><a-tag color="red">已停用</a-tag></td>
                <td>无法通过认证，需管理员重新启用</td>
              </tr>
              <tr>
                <td>已过期</td>
                <td>超过设定的过期时间，无法通过认证</td>
              </tr>
              <tr>
                <td>已删除</td>
                <td>已被管理员删除，永久失效</td>
              </tr>
            </tbody>
          </table>

          <div class="alert alert-warning">
            <strong>⚠️ 安全提示</strong>
            <ul>
              <li>API-Key 在创建时仅展示一次完整明文，请妥善保管。</li>
              <li>不要将 API-Key 暴露在前端代码、Git 仓库或日志中。</li>
              <li>如怀疑 Key 泄露，请立即在管理页面停用并重新申请。</li>
            </ul>
          </div>
        </section>

        <!-- ERP 余额查询接口 -->
        <section id="erp-balances" class="doc-section">
          <h1 class="doc-title">ERP 渠道客户余额查询</h1>

          <div class="endpoint-header">
            <span class="method method-get">GET</span>
            <code class="endpoint-path">/api/v1/erp/balances</code>
          </div>

          <p class="doc-text">返回指定 ERP 渠道下所有企业的客户ID、客户名称和当前余额列表。</p>

          <h2 class="doc-subtitle">请求参数</h2>
          <table class="doc-table">
            <thead>
              <tr>
                <th>参数名</th>
                <th>位置</th>
                <th>类型</th>
                <th>必填</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>erp_channel</code></td>
                <td>Query</td>
                <td>string</td>
                <td>是</td>
                <td>ERP 渠道编码，如巧房传 <code>qiaofang</code></td>
              </tr>
              <tr>
                <td><code>Authorization</code></td>
                <td>Header</td>
                <td>string</td>
                <td>是</td>
                <td>认证令牌，格式：<code>Bearer {api_key}</code></td>
              </tr>
            </tbody>
          </table>

          <h2 class="doc-subtitle">请求示例</h2>
          <pre class="code-block">{{
            `curl -X GET \\
  "https://customer-staging.jiazoushi.com/api/v1/erp/balances?erp_channel=qiaofang" \\
  -H "Authorization: Bearer vk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"`
          }}</pre>

          <h2 class="doc-subtitle">响应格式</h2>
          <p class="doc-text">返回 JSON 数组，包含以下字段：</p>
          <table class="doc-table">
            <thead>
              <tr>
                <th>字段名</th>
                <th>类型</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>customer_id</code></td>
                <td>string</td>
                <td>客户在 ERP 系统中的企业 ID（company_id）</td>
              </tr>
              <tr>
                <td><code>customer_name</code></td>
                <td>string</td>
                <td>客户名称（企业全称）</td>
              </tr>
              <tr>
                <td><code>balance</code></td>
                <td>number</td>
                <td>当前可用余额（总金额 - 已用金额，保留两位小数）</td>
              </tr>
            </tbody>
          </table>

          <h2 class="doc-subtitle">响应示例</h2>
          <pre class="code-block">{{
            `{
  "code": 0,
  "message": "success",
  "data": [
    {
      "customer_id": "615",
      "customer_name": "北京金诚阜业房地产经纪有限公司",
      "balance": 100000.00
    },
    {
      "customer_id": "1552",
      "customer_name": "荣城地产",
      "balance": 0.00
    }
  ]
}`
          }}</pre>

          <h2 class="doc-subtitle">渠道编码对照表</h2>
          <p class="doc-text">
            以下为当前系统中已配置的 ERP 渠道编码，与「系统管理 → ERP 系统」页面中的配置保持一致。
          </p>
          <table class="doc-table">
            <thead>
              <tr>
                <th>ERP 系统</th>
                <th>渠道编码</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in erpSystems" :key="item.value">
                <td>{{ item.name }}</td>
                <td>
                  <code>{{ item.value }}</code>
                </td>
              </tr>
              <tr v-if="erpSystems.length === 0">
                <td colspan="2">暂无配置，请先在「系统管理 → ERP 系统」中添加</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- 错误码 -->
        <section id="error-codes" class="doc-section">
          <h1 class="doc-title">错误码说明</h1>
          <p class="doc-text">
            当请求失败时，响应体中的 <code>code</code> 字段为非零值，<code>message</code>
            描述具体错误原因。
          </p>

          <table class="doc-table">
            <thead>
              <tr>
                <th>错误码</th>
                <th>含义</th>
                <th>HTTP 状态</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>0</code></td>
                <td>成功</td>
                <td>200</td>
              </tr>
              <tr>
                <td><code>40004</code></td>
                <td>缺少必要参数</td>
                <td>400</td>
              </tr>
              <tr>
                <td><code>40101</code></td>
                <td>未认证 / 缺少 Token</td>
                <td>401</td>
              </tr>
              <tr>
                <td><code>40104</code></td>
                <td>API-Key 无效或已停用</td>
                <td>401</td>
              </tr>
              <tr>
                <td><code>40105</code></td>
                <td>API-Key 已过期</td>
                <td>401</td>
              </tr>
              <tr>
                <td><code>50000</code></td>
                <td>服务器内部错误</td>
                <td>500</td>
              </tr>
            </tbody>
          </table>

          <h2 class="doc-subtitle">错误响应示例</h2>
          <pre class="code-block">{{
            `{
  "code": 40004,
  "message": "缺少必要参数: erp_channel"
}`
          }}</pre>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getErpSystemsList } from '@/api/erpSystems'
import type { ErpSystem } from '@/types'

const router = useRouter()
const activeSection = ref('overview')
// 默认渠道编码（与迁移脚本 n3o4p5q6r7s8 中的数据一致）
// 当用户未登录时动态加载会失败（401），回退到此静态列表
const FALLBACK_ERP_SYSTEMS: ErpSystem[] = [
  { id: 0, name: '无', value: 'noerp', sort_order: 0 },
  { id: 0, name: '鼎尖', value: 'dingjian', sort_order: 1 },
  { id: 0, name: '易遨', value: 'yiao', sort_order: 2 },
  { id: 0, name: '房信', value: 'fangxin', sort_order: 3 },
  { id: 0, name: '房管家', value: 'fangguanjia', sort_order: 4 },
  { id: 0, name: '好房通', value: 'haofangtong', sort_order: 5 },
  { id: 0, name: '上海梵讯', value: 'shanghaifanxun', sort_order: 6 },
  { id: 0, name: '巧房', value: 'qiaofang', sort_order: 7 },
  { id: 0, name: '房融', value: 'fangrong', sort_order: 8 },
  { id: 0, name: '云享', value: 'yunxiang', sort_order: 9 },
  { id: 0, name: '自研', value: 'self', sort_order: 11 },
  { id: 0, name: '房在线', value: 'fangzaixian', sort_order: 12 },
]
const erpSystems = ref<ErpSystem[]>([...FALLBACK_ERP_SYSTEMS])

const goHome = () => {
  router.push('/')
}

const handleScroll = (e: Event) => {
  const target = e.target as HTMLElement
  const sections = target.querySelectorAll('.doc-section')
  const scrollTop = target.scrollTop

  for (let i = sections.length - 1; i >= 0; i--) {
    const section = sections[i] as HTMLElement
    if (section.offsetTop <= scrollTop + 100) {
      activeSection.value = section.id
      break
    }
  }
}

onMounted(() => {
  // 动态加载 ERP 系统列表，用于渠道编码对照表
  // 未登录时加载会失败（401），回退到静态预设列表
  getErpSystemsList()
    .then((res) => {
      const body = res as unknown as { data: ErpSystem[] }
      const list = body?.data ?? []
      if (Array.isArray(list) && list.length > 0) {
        erpSystems.value = list.sort((a: ErpSystem, b: ErpSystem) => a.sort_order - b.sort_order)
      }
    })
    .catch(() => {
      // 未登录或网络错误时使用静态列表
    })
})
</script>

<style scoped>
.openapi-page {
  min-height: 100vh;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
}

/* ─── 顶部导航栏 ─── */
.topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}

.topbar-inner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  color: white;
  font-weight: 700;
  font-size: 16px;
}

.brand .mark {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b82f6, #06b6d4);
  display: grid;
  place-items: center;
  color: white;
  font-weight: 900;
  font-size: 13px;
  flex-shrink: 0;
}

:deep(.topbar .arco-btn-text) {
  color: #93c5fd;
}

:deep(.topbar .arco-btn-text:hover) {
  color: white;
  background: rgba(255, 255, 255, 0.1);
}

/* ─── 内容布局 ─── */
.content-wrapper {
  display: flex;
  flex: 1;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* ─── 左侧目录 ─── */
.sidebar {
  width: 240px;
  flex-shrink: 0;
  position: sticky;
  top: 56px;
  height: calc(100vh - 56px);
  overflow-y: auto;
  padding: 24px 12px;
  border-right: 1px solid #e2e8f0;
}

.toc-group {
  margin-bottom: 20px;
}

.toc-title {
  padding: 4px 12px;
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.toc-link {
  display: block;
  padding: 6px 12px;
  color: #334155;
  font-size: 13px;
  text-decoration: none;
  border-radius: 8px;
  transition:
    background 0.15s,
    color 0.15s;
  cursor: pointer;
}

.toc-link:hover {
  background: #e2e8f0;
  color: #1e293b;
}

.toc-link.active {
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.12), rgba(6, 182, 212, 0.06));
  color: #2563eb;
  font-weight: 600;
}

/* ─── 右侧内容区 ─── */
.main-content {
  flex: 1;
  padding: 32px 48px;
  overflow-y: auto;
  max-height: calc(100vh - 56px);
}

.doc-section {
  margin-bottom: 48px;
  scroll-margin-top: 80px;
}

.doc-title {
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 16px;
  padding-bottom: 12px;
  border-bottom: 2px solid #e2e8f0;
}

.doc-subtitle {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
  margin: 28px 0 12px;
}

.doc-text {
  font-size: 15px;
  line-height: 1.7;
  color: #334155;
  margin: 0 0 12px;
}

.doc-text code {
  background: #f1f5f9;
  color: #db2777;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* ─── 代码块 ─── */
.code-block {
  background: #1e293b;
  color: #e2e8f0;
  padding: 16px 20px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  overflow-x: auto;
  margin: 12px 0 20px;
  white-space: pre;
}

/* ─── 表格 ─── */
.doc-table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0 20px;
  font-size: 14px;
}

.doc-table th {
  background: #f1f5f9;
  color: #475569;
  font-weight: 700;
  text-align: left;
  padding: 10px 16px;
  border: 1px solid #e2e8f0;
}

.doc-table td {
  padding: 10px 16px;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.doc-table code {
  background: #f1f5f9;
  color: #db2777;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* ─── Endpoint 标题 ─── */
.endpoint-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 20px 0 16px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
}

.method {
  font-size: 12px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 6px;
  font-family: monospace;
}

.method-get {
  background: #dcfce7;
  color: #166534;
}

.endpoint-path {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* ─── 提示框 ─── */
.alert {
  padding: 16px 20px;
  border-radius: 10px;
  margin: 16px 0;
  font-size: 14px;
  line-height: 1.6;
}

.alert-warning {
  background: #fefce8;
  border: 1px solid #fde68a;
  color: #92400e;
}

.alert ul {
  margin: 8px 0 0;
  padding-left: 20px;
}

/* ─── 响应式 ─── */
@media (max-width: 900px) {
  .sidebar {
    display: none;
  }

  .main-content {
    padding: 24px 20px;
  }
}
</style>
