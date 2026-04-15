<template>
  <div class="customer-detail-page">
    <a-spin :loading="loading" size="large">
      <div class="page-header">
        <div class="header-title">
          <a-button type="text" @click="goBack">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                fill-rule="evenodd"
                d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z"
              />
            </svg>
          </a-button>
          <h1>{{ customer.name || '客户详情' }}</h1>
        </div>
        <div class="header-actions">
          <a-button @click="openEditModal">编辑</a-button>
          <a-button type="primary" :loading="keyCustomerLoading" @click="toggleKeyCustomer">
            {{ customer.is_key_customer ? '取消重点' : '设为重点' }}
          </a-button>
        </div>
      </div>

      <div class="tabs-section">
        <a-tabs v-model="activeTab" @change="handleTabChange">
          <a-tab-pane key="basic" title="基础信息">
            <div class="info-grid">
              <!-- 第 1 行 -->
              <div class="info-item">
                <span class="label">客户名称</span>
                <span class="value">{{ customer.name }}</span>
              </div>
              <div class="info-item">
                <span class="label">公司 ID</span>
                <span class="value">{{ customer.company_id }}</span>
              </div>
              <!-- 第 2 行 -->
              <div class="info-item">
                <span class="label">账号类型</span>
                <span class="value">
                  <a-tag>{{ customer.account_type || '-' }}</a-tag>
                </span>
              </div>
              <div class="info-item">
                <span class="label">行业类型</span>
                <span class="value">
                  <a-tag>{{ customer.industry || '-' }}</a-tag>
                </span>
              </div>
              <!-- 第 3 行 -->
              <div class="info-item">
                <span class="label">客户等级</span>
                <span class="value">
                  <a-tag>{{ customer.customer_level || '-' }}</a-tag>
                </span>
              </div>
              <div class="info-item">
                <span class="label">重点客户</span>
                <span class="value">
                  <a-tag :color="customer.is_key_customer ? 'red' : 'gray'">
                    {{ customer.is_key_customer ? '是' : '否' }}
                  </a-tag>
                </span>
              </div>
              <!-- 第 4 行 -->
              <div class="info-item">
                <span class="label">结算方式</span>
                <span class="value">
                  <a-tag :color="customer.settlement_type === 'prepaid' ? 'green' : 'blue'">
                    {{ customer.settlement_type === 'prepaid' ? '预付费' : '后付费' }}
                  </a-tag>
                </span>
              </div>
              <div class="info-item">
                <span class="label">结算周期</span>
                <span class="value">{{ customer.settlement_cycle || '-' }}</span>
              </div>
              <!-- 第 5 行 -->
              <div class="info-item">
                <span class="label">邮箱</span>
                <span class="value">{{ customer.email || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="label">所属 ERP</span>
                <span class="value">
                  <a-tag v-if="customer.erp_system">{{ customer.erp_system }}</a-tag>
                  <span v-else>-</span>
                </span>
              </div>
              <!-- 第 6 行 -->
              <div class="info-item">
                <span class="label">合作状态</span>
                <span class="value">
                  <a-tag :color="cooperationStatusColor">
                    {{ cooperationStatusText }}
                  </a-tag>
                </span>
              </div>
              <div class="info-item">
                <span class="label">销售负责人</span>
                <span class="value">
                  {{ salesManagerName || '-' }}
                </span>
              </div>
              <!-- 第 7 行 -->
              <div class="info-item">
                <span class="label">是否结算</span>
                <span class="value">
                  <a-tag :color="customer.is_settlement_enabled ? 'green' : 'gray'">
                    {{ customer.is_settlement_enabled ? '是' : '否' }}
                  </a-tag>
                </span>
              </div>
              <div class="info-item">
                <span class="label">是否停用</span>
                <span class="value">
                  <a-tag :color="customer.is_disabled ? 'red' : 'gray'">
                    {{ customer.is_disabled ? '是' : '否' }}
                  </a-tag>
                </span>
              </div>
              <!-- 第 8 行 -->
              <div class="info-item">
                <span class="label">首次回款时间</span>
                <span class="value">{{ customer.first_payment_date || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="label">接入时间</span>
                <span class="value">{{ customer.onboarding_date || '-' }}</span>
              </div>
              <!-- 第 9 行 -->
              <div class="info-item">
                <span class="label">备注</span>
                <span class="value">
                  <span v-if="customer.notes" class="notes-text">{{ customer.notes }}</span>
                  <span v-else>-</span>
                </span>
              </div>
              <div class="info-item">
                <span class="label">创建时间</span>
                <span class="value">{{ formatDateTime(customer.created_at) }}</span>
              </div>
              <!-- 第 10 行 - 占满整行 -->
              <div class="info-item full-width">
                <span class="label">客户标签</span>
                <span class="value">
                  <div class="tags-container">
                    <a-tag
                      v-for="tag in customerTags"
                      :key="tag.id"
                      color="arcoblue"
                      closable
                      @close="removeTag(tag.id)"
                    >
                      {{ tag.name }}
                    </a-tag>
                    <a-button type="text" size="small" @click="openTagSelector">
                      <template #icon>
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="16"
                          height="16"
                          fill="currentColor"
                          viewBox="0 0 16 16"
                        >
                          <path
                            d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"
                          />
                        </svg>
                      </template>
                      添加标签
                    </a-button>
                  </div>
                </span>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="profile" title="画像信息">
            <div class="profile-tab-content">
              <!-- 核心指标区 -->
              <div class="metrics-grid">
                <div v-if="profileLoading" class="metric-card loading">
                  <SkeletonCard height="72px" />
                </div>
                <div v-else class="metric-card primary">
                  <span class="metric-label">规模等级</span>
                  <span class="metric-value">{{ profile.scale_level || '-' }}</span>
                </div>
                
                <div v-if="profileLoading" class="metric-card loading">
                  <SkeletonCard height="72px" />
                </div>
                <div v-else class="metric-card success">
                  <span class="metric-label">消费等级</span>
                  <span class="metric-value">{{ consumeLevelDisplay }}</span>
                </div>

                <div v-if="profileLoading" class="metric-card loading">
                  <SkeletonCard height="72px" />
                </div>
                <div v-else class="metric-card warning">
                  <span class="metric-label">预估年消费</span>
                  <span class="metric-value">{{ profile.estimated_annual_spend ? formatCurrency(Number(profile.estimated_annual_spend)) : '-' }}</span>
                </div>
              </div>

              <!-- 扩展指标区 -->
              <div class="metrics-grid metrics-grid-extended">
                <div v-if="profileLoading" class="metric-card loading">
                  <SkeletonCard height="72px" />
                </div>
                <div v-else class="metric-card">
                  <span class="metric-label">月均拍摄量（实际）</span>
                  <span class="metric-value">{{ profile.monthly_avg_shots ?? '-' }}</span>
                </div>

                <div v-if="profileLoading" class="metric-card loading">
                  <SkeletonCard height="72px" />
                </div>
                <div v-else class="metric-card">
                  <span class="metric-label">月均拍摄量（测算）</span>
                  <span class="metric-value">{{ profile.monthly_avg_shots_estimated ?? '-' }}</span>
                </div>

                <div v-if="profileLoading" class="metric-card loading">
                  <SkeletonCard height="72px" />
                </div>
                <div v-else class="metric-card">
                  <span class="metric-label">25年实际消费</span>
                  <span class="metric-value">{{ profile.actual_annual_spend_2025 ? formatCurrency(Number(profile.actual_annual_spend_2025)) : '-' }}</span>
                </div>
              </div>

              <!-- 图表区域 -->
              <div class="charts-grid">
                <div class="chart-panel">
                  <h4 class="chart-title">健康度评分</h4>
                  <p class="chart-description">综合评估客户健康状况</p>
                  <div v-if="healthScoreLoading" class="chart-loading">
                    <a-spin size="large" />
                  </div>
                  <div v-else class="chart-content">
                    <HealthGauge
                      v-if="healthScore && shouldRenderChart('health')"
                      :score="healthScore.score"
                      :level="healthScore.level"
                    />
                  </div>
                </div>
                
                <div class="chart-panel">
                  <h4 class="chart-title">消费等级进度</h4>
                  <p class="chart-description">当前消费等级升级进度</p>
                  <div class="chart-content">
                    <ConsumeLevelProgress
                      v-if="shouldRenderChart('consume')"
                      :current-level="profile.consume_level || 'C1'"
                      :current-amount="balance.used_total"
                    />
                  </div>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="balance" title="余额信息">
            <div v-if="balanceLoading" class="balance-cards">
              <SkeletonCard v-for="i in 4" :key="i" height="110px" />
            </div>
            <div v-else class="balance-cards">
              <div class="balance-card">
                <div class="balance-label">总余额</div>
                <div class="balance-value">{{ formatCurrency(balance.total_amount) }}</div>
              </div>
              <div class="balance-card">
                <div class="balance-label">实充余额</div>
                <div class="balance-value real">{{ formatCurrency(balance.real_amount) }}</div>
              </div>
              <div class="balance-card">
                <div class="balance-label">赠送余额</div>
                <div class="balance-value bonus">{{ formatCurrency(balance.bonus_amount) }}</div>
              </div>
              <div class="balance-card">
                <div class="balance-label">已消耗</div>
                <div class="balance-value">{{ formatCurrency(balance.used_total) }}</div>
              </div>
            </div>

            <!-- 余额趋势图 - 性能优化: 延迟加载 -->
            <div class="balance-trend-section">
              <BalanceTrendChart
                v-if="shouldRenderChart('balanceTrend')"
                :trend="balanceTrend"
                :loading="balanceTrendLoading"
              />
            </div>
          </a-tab-pane>

          <a-tab-pane key="invoices" title="结算单">
            <a-table :columns="invoiceColumns" :data="invoices" :pagination="false" row-key="id">
              <template #status="{ record }">
                <span :class="['status-badge', getStatusClass(record.status)]">
                  <span class="status-dot"></span>
                  {{ getStatusText(record.status) }}
                </span>
              </template>
              <template #amount="{ record }">
                {{ formatCurrency(record.final_amount || record.total_amount) }}
              </template>
              <template #action="{ record }">
                <a-button type="primary" size="small" @click="viewInvoice(record)">查看</a-button>
              </template>
              <template #empty>
                <EmptyState title="暂无结算单数据" description="当前客户暂无结算单" />
              </template>
            </a-table>
          </a-tab-pane>

          <a-tab-pane key="usage" title="用量数据">
            <!-- 用量分布图 - 性能优化: 延迟加载 -->
            <div class="usage-distribution-section">
              <UsageDistributionChart
                v-if="shouldRenderChart('usageDistribution')"
                :distribution="usageDistribution"
                :total-quantity="totalUsageQuantity"
                :loading="usageLoading"
              />
            </div>

            <!-- 用量数据表格 -->
            <div class="usage-table-section">
              <a-table
                :columns="usageColumns"
                :data="usageData"
                :loading="usageLoading"
                :pagination="usagePagination"
                row-key="id"
                @page-change="handleUsagePageChange"
              >
                <template #deviceType="{ record }">
                  <a-tag>{{ record.device_type }}</a-tag>
                </template>
                <template #quantity="{ record }">
                  {{ formatNumber(record.quantity || 0) }}
                </template>
                <template #empty>
                  <EmptyState title="暂无用量数据" description="当前客户暂无用量记录" />
                </template>
              </a-table>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>

      <!-- 编辑客户对话框 -->
      <a-modal
        v-model:visible="editModalVisible"
        title="编辑客户"
        :width="modalWidth"
        :confirm-loading="editLoading"
        @ok="handleEditSubmit"
        @cancel="handleEditCancel"
      >
        <a-form
          ref="editFormRef"
          :model="editForm"
          :rules="editFormRules"
          layout="vertical"
          validate-trigger="['blur', 'change']"
        >
          <div class="edit-form-grid">
            <!-- 第一列：基础信息 -->
            <div class="edit-form-column">
              <div class="column-title">基础信息</div>

              <a-form-item field="name" label="客户名称" required>
                <a-input v-model="editForm.name" placeholder="请输入客户名称" />
              </a-form-item>

              <a-form-item field="company_id" label="公司 ID" required>
                <a-input v-model="editForm.company_id" placeholder="请输入公司 ID" />
              </a-form-item>

              <a-form-item field="account_type" label="账号类型">
                <a-select v-model="editForm.account_type" placeholder="请选择账号类型" allow-clear>
                  <a-option value="正式账号">正式账号</a-option>
                  <a-option value="测试账号">测试账号</a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="industry" label="行业类型">
                <a-select v-model="editForm.industry" placeholder="请选择行业类型" allow-clear>
                  <a-option value="A">A 类</a-option>
                  <a-option value="B">B 类</a-option>
                  <a-option value="C">C 类</a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="customer_level" label="客户等级">
                <a-select v-model="editForm.customer_level" placeholder="请选择客户等级" allow-clear>
                  <a-option value="KA">KA</a-option>
                  <a-option value="A">A</a-option>
                  <a-option value="B">B</a-option>
                  <a-option value="C">C</a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="email" label="邮箱">
                <a-input v-model="editForm.email" placeholder="请输入邮箱" />
              </a-form-item>
            </div>

            <!-- 第二列：结算与业务 -->
            <div class="edit-form-column">
              <div class="column-title">结算与业务</div>

              <a-form-item field="settlement_type" label="结算方式" required>
                <a-select v-model="editForm.settlement_type" placeholder="请选择结算方式">
                  <a-option value="prepaid">预付费</a-option>
                  <a-option value="postpaid">后付费</a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="settlement_cycle" label="结算周期">
                <a-select v-model="editForm.settlement_cycle" placeholder="请选择结算周期" allow-clear>
                  <a-option value="日结">日结</a-option>
                  <a-option value="周结">周结</a-option>
                  <a-option value="月结">月结</a-option>
                  <a-option value="季结">季结</a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="cooperation_status" label="合作状态">
                <a-select v-model="editForm.cooperation_status" placeholder="请选择合作状态" allow-clear>
                  <a-option value="active">合作中</a-option>
                  <a-option value="suspended">暂停</a-option>
                  <a-option value="terminated">终止</a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="erp_system" label="所属 ERP">
                <a-input v-model="editForm.erp_system" placeholder="请输入所属 ERP 系统" allow-clear />
              </a-form-item>

              <a-form-item field="manager_id" label="运营经理">
                <a-select
                  v-model="editForm.manager_id"
                  placeholder="请选择运营经理"
                  allow-clear
                  :loading="managersLoading"
                >
                  <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
                    {{ manager.real_name || manager.username }}
                  </a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="sales_manager_id" label="销售负责人">
                <a-select
                  v-model="editForm.sales_manager_id"
                  placeholder="请选择销售负责人"
                  allow-clear
                  :loading="managersLoading"
                >
                  <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
                    {{ manager.real_name || manager.username }}
                  </a-option>
                </a-select>
              </a-form-item>
            </div>

            <!-- 第三列：画像与状态 -->
            <div class="edit-form-column">
              <div class="column-title">画像与状态</div>

              <a-form-item field="scale_level" label="规模等级">
                <a-select v-model="editForm.scale_level" placeholder="请选择规模等级" allow-clear>
                  <a-option value="100">100人</a-option>
                  <a-option value="500">500人</a-option>
                  <a-option value="1000">1000人</a-option>
                  <a-option value="2000">2000人</a-option>
                  <a-option value="5000">5000人</a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="consume_level" label="消费等级">
                <a-select v-model="editForm.consume_level" placeholder="请选择消费等级" allow-clear>
                  <a-option value="S">S</a-option>
                  <a-option value="A">A</a-option>
                  <a-option value="B">B</a-option>
                  <a-option value="C">C</a-option>
                  <a-option value="D">D</a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="first_payment_date" label="首次回款时间">
                <a-date-picker
                  v-model="editForm.first_payment_date"
                  placeholder="请选择首次回款时间"
                  style="width: 100%"
                  allow-clear
                  value-format="YYYY-MM-DD"
                />
              </a-form-item>

              <a-form-item field="onboarding_date" label="接入时间">
                <a-date-picker
                  v-model="editForm.onboarding_date"
                  placeholder="请选择接入时间"
                  style="width: 100%"
                  allow-clear
                  value-format="YYYY-MM-DD"
                />
              </a-form-item>

              <a-form-item field="is_key_customer" label="重点客户">
                <a-switch v-model="editForm.is_key_customer" />
              </a-form-item>

              <a-form-item field="is_settlement_enabled" label="是否结算">
                <a-switch v-model="editForm.is_settlement_enabled" />
              </a-form-item>

              <a-form-item field="is_disabled" label="是否停用">
                <a-switch v-model="editForm.is_disabled" />
              </a-form-item>
            </div>

            <!-- 备注区域 - 横跨三列 -->
            <div class="edit-form-note">
              <a-form-item field="notes" label="备注">
                <a-textarea
                  v-model="editForm.notes"
                  placeholder="请输入备注信息"
                  :auto-size="{ minRows: 2, maxRows: 4 }"
                  allow-clear
                />
              </a-form-item>
            </div>
          </div>
        </a-form>
      </a-modal>

      <!-- 标签选择器对话框 -->
      <a-modal
        v-model:visible="tagSelectorVisible"
        title="添加标签"
        :confirm-loading="tagSelectorLoading"
        width="500px"
        @ok="handleAddTag"
        @cancel="tagSelectorVisible = false"
      >
        <a-form layout="vertical">
          <a-form-item label="选择标签" required>
            <a-select
              v-model="selectedTagIds"
              placeholder="请选择标签"
              multiple
              allow-clear
              :loading="allTagsLoading"
            >
              <a-option v-for="tag in availableTags" :key="tag.id" :value="tag.id">
                {{ tag.name }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-form>
      </a-modal>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, onUnmounted, watch } from 'vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getCustomer, updateCustomer, getProfile, updateProfile } from '@/api/customers'
import {
  getCustomerBalance,
  getInvoices,
  type Invoice,
  getBalanceTrend,
  type BalanceTrendItem,
} from '@/api/billing'
import { getTags, getCustomerTags, addCustomerTag, removeCustomerTag } from '@/api/tags'
import { getDailyUsage, type DailyUsage } from '@/api/usage'
import { getManagers } from '@/api/users'
import { getCustomerHealthScore, type CustomerHealthScore } from '@/api/analytics'
import type { Customer, CustomerProfile, Balance, Tag, User } from '@/types'
import { formatCurrency, formatDateTime, formatNumber } from '@/utils/formatters'
import EmptyState from '@/components/EmptyState.vue'
import SkeletonCard from '@/components/SkeletonCard.vue'
import HealthGauge from '@/components/charts/HealthGauge.vue'
import ConsumeLevelProgress from '@/components/charts/ConsumeLevelProgress.vue'
import BalanceTrendChart from '@/components/charts/BalanceTrendChart.vue'
import UsageDistributionChart from '@/components/charts/UsageDistributionChart.vue'
import { useCustomerStore } from '@/stores/customer'

const route = useRoute()
const router = useRouter()
const customerStore = useCustomerStore()

// 编辑表单 ref
const editFormRef = ref<FormInstance>()

// 弹窗响应式宽度
const modalWidth = computed(() => {
  if (typeof window === 'undefined') return '1100px'
  const width = window.innerWidth
  if (width >= 1400) return '1100px'
  if (width >= 768) return '800px'
  return '100%'
})

// 性能优化: 已加载的标签页数据
const loadedTabs = ref<Set<string>>(new Set(['basic']))

// 性能优化: 图表渲染状态（延迟加载）
const chartRenderState = ref<Record<string, boolean>>({})

// 延迟加载定时器
let tabLoadTimer: ReturnType<typeof setTimeout> | null = null

// 性能优化: 检查是否应该渲染图表
const shouldRenderChart = (chartId: string): boolean => {
  return chartRenderState.value[chartId] ?? false
}

// 性能优化: 标记图表为可渲染
const markChartForRender = (chartId: string): void => {
  chartRenderState.value[chartId] = true
}

// 性能优化: Tab 切换处理 - 按需加载数据
const handleTabChange = (tabKey: string): void => {
  if (!loadedTabs.value.has(tabKey)) {
    loadedTabs.value.add(tabKey)
    
    // 延迟加载图表，避免标签页切换卡顿
    if (tabLoadTimer) {
      clearTimeout(tabLoadTimer)
    }
    
    tabLoadTimer = setTimeout(() => {
      if (tabKey === 'profile') {
        markChartForRender('health')
        markChartForRender('consume')
      } else if (tabKey === 'balance') {
        markChartForRender('balanceTrend')
      } else if (tabKey === 'usage') {
        markChartForRender('usageDistribution')
      }
    }, 100)
  }
}

// 返回上一页
const goBack = () => {
  router.back()
}

// 编辑表单类型
interface EditForm {
  name: string
  company_id: string
  email: string
  account_type?: string
  industry?: string
  customer_level?: string
  settlement_type?: string
  settlement_cycle?: string
  is_key_customer?: boolean
  manager_id?: number
  // 新增字段
  erp_system?: string
  first_payment_date?: string
  onboarding_date?: string
  sales_manager_id?: number
  cooperation_status?: string
  is_settlement_enabled?: boolean
  is_disabled?: boolean
  notes?: string
  // 规模等级和消费等级（来自 CustomerProfile）
  scale_level?: string
  consume_level?: string
}

// 状态
const loading = ref(false)
const keyCustomerLoading = ref(false)
const editLoading = ref(false)
const editModalVisible = ref(false)
const activeTab = ref('basic')
const profileLoading = ref(true)
const balanceLoading = ref(true)

// 数据
const customerId = ref<number>(0)
const customer = ref<Customer>({
  id: 0,
  company_id: '',
  name: '',
  account_type: null,
  industry: null,
  customer_level: null,
  price_policy: null,
  manager_id: null,
  settlement_cycle: null,
  settlement_type: null,
  is_key_customer: false,
  email: null,
  created_at: '',
  updated_at: '',
  erp_system: null,
  first_payment_date: null,
  onboarding_date: null,
  sales_manager_id: null,
  cooperation_status: null,
  is_settlement_enabled: null,
  is_disabled: null,
  notes: null,
})

const profile = ref<CustomerProfile>({
  id: 0,
  customer_id: 0,
  scale_level: null,
  consume_level: null,
  industry: null,
  is_real_estate: false,
  description: null,
  created_at: '',
  updated_at: '',
  monthly_avg_shots: null,
  monthly_avg_shots_estimated: null,
  estimated_annual_spend: null,
  actual_annual_spend_2025: null,
})

const balance = ref<Balance>({
  id: 0,
  customer_id: 0,
  total_amount: 0,
  real_amount: 0,
  bonus_amount: 0,
  used_total: 0,
  used_real: 0,
  used_bonus: 0,
  created_at: '',
  updated_at: '',
})

// 健康度数据
const healthScoreLoading = ref(true)
const healthScore = ref<CustomerHealthScore | null>(null)

// 余额趋势数据
const balanceTrendLoading = ref(true)
const balanceTrend = ref<BalanceTrendItem[]>([])

// 用量分布数据（模拟）
const usageDistribution = ref<Array<{ device_type: string; quantity: number; percentage: number }>>(
  []
)
const totalUsageQuantity = ref(0)

const invoices = ref<Invoice[]>([])
const customerTags = ref<Tag[]>([])
const allTags = ref<Tag[]>([])
const allTagsLoading = ref(false)
const tagSelectorVisible = ref(false)
const tagSelectorLoading = ref(false)
const selectedTagIds = ref<number[]>([])

const managersLoading = ref(false)
const managers = ref<User[]>([])

const loadManagers = async () => {
  // 性能优化: 检查缓存
  if (customerStore.hasCachedManagers()) {
    managers.value = customerStore.getCachedManagers() || []
    return
  }

  managersLoading.value = true
  try {
    const res = await getManagers()
    const managersList = res.data?.list || res.data || []
    managers.value = managersList
    // 性能优化: 缓存数据
    customerStore.cacheManagersData(managersList)
  } catch (error) {
    console.error('加载运营经理失败:', error)
  } finally {
    managersLoading.value = false
  }
}

// 用量数据
const usageLoading = ref(false)
const usageData = ref<DailyUsage[]>([])
const usagePagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
})

const usageColumns = [
  { title: '日期', dataIndex: 'usage_date' },
  { title: '设备类型', slotName: 'deviceType' },
  { title: '层级类型', dataIndex: 'layer_type' },
  { title: '用量', slotName: 'quantity' },
  { title: '同步时间', dataIndex: 'synced_at' },
]

const invoiceColumns = [
  { title: '结算单号', dataIndex: 'invoice_no' },
  { title: '周期开始', dataIndex: 'period_start' },
  { title: '周期结束', dataIndex: 'period_end' },
  { title: '金额', slotName: 'amount' },
  { title: '状态', slotName: 'status' },
  { title: '创建时间', dataIndex: 'created_at' },
  { title: '操作', slotName: 'action' },
]

// 编辑表单
const editForm = ref<EditForm>({
  name: '',
  company_id: '',
  email: '',
  account_type: undefined,
  industry: undefined,
  customer_level: undefined,
  settlement_type: undefined,
  settlement_cycle: undefined,
  is_key_customer: false,
  manager_id: undefined,
  // 新增字段
  erp_system: undefined,
  first_payment_date: undefined,
  onboarding_date: undefined,
  sales_manager_id: undefined,
  cooperation_status: undefined,
  is_settlement_enabled: true,
  is_disabled: false,
  notes: undefined,
  // 规模等级和消费等级（来自 CustomerProfile）
  scale_level: undefined,
  consume_level: undefined,
})

// 编辑表单验证规则
const editFormRules = {
  company_id: [
    { required: true, message: '公司 ID 不能为空', trigger: ['blur', 'change'] },
  ],
  name: [
    { required: true, message: '客户名称不能为空', trigger: ['blur', 'change'] },
    { maxLength: 200, message: '客户名称不能超过 200 个字符', trigger: ['blur', 'change'] },
  ],
  email: [
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] },
  ],
  settlement_type: [
    { required: true, message: '请选择结算方式', trigger: ['blur', 'change'] },
  ],
}

// 加载数据 - 优化版：支持 Pinia 缓存和并行加载
const loadCustomerData = async () => {
  const id = Number(route.params.id)
  customerId.value = id

  // 性能优化: 检查是否有缓存数据
  if (customerStore.hasCachedCustomer(id)) {
    const cached = customerStore.getCachedCustomer(id)!
    customer.value = cached.customer
    profile.value = cached.profile
    balance.value = cached.balance
    invoices.value = cached.invoices
    healthScore.value = cached.healthScore
    balanceTrend.value = cached.balanceTrend
    
    loading.value = false
    profileLoading.value = false
    balanceLoading.value = false
    healthScoreLoading.value = false
    balanceTrendLoading.value = false
    
    // 模拟用量分布数据
    usageDistribution.value = [
      { device_type: 'iOS', quantity: 45000, percentage: 45 },
      { device_type: 'Android', quantity: 35000, percentage: 35 },
      { device_type: 'Web', quantity: 15000, percentage: 15 },
      { device_type: 'H5', quantity: 5000, percentage: 5 },
    ]
    totalUsageQuantity.value = 100000
    return
  }

  loading.value = true
  
  // 性能优化: 分阶段加载数据 - 先加载关键数据
  try {
    // 第一阶段: 加载基础信息（快速显示）
    const [customerRes, profileRes, balanceRes] = await Promise.all([
      getCustomer(id),
      getProfile(id),
      getCustomerBalance(id),
    ])

    customer.value = customerRes.data
    profile.value = profileRes.data || {
      id: 0,
      customer_id: id,
      scale_level: null,
      consume_level: null,
      industry: null,
      is_real_estate: false,
      description: null,
      created_at: '',
      updated_at: '',
    }
    balance.value = {
      ...balanceRes.data,
      id: 0,
      customer_id: id,
    }

    // 第一阶段数据加载完成，立即更新加载状态
    profileLoading.value = false
    balanceLoading.value = false

    // 第二阶段: 加载其他数据（后台加载）
    const [invoicesRes, healthRes, balanceTrendRes] = await Promise.all([
      getInvoices({ customer_id: id, page_size: 100 }),
      getCustomerHealthScore(id).catch(() => ({
        data: { customer_id: id, score: 75, level: '健康', factors: [] },
      })),
      getBalanceTrend(id, 6).catch(() => ({ data: [] })),
    ])

    invoices.value = invoicesRes.data?.list || invoicesRes.data?.items || []
    healthScore.value = healthRes.data
    balanceTrend.value = balanceTrendRes.data || []
    healthScoreLoading.value = false
    balanceTrendLoading.value = false

    // 模拟用量分布数据
    usageDistribution.value = [
      { device_type: 'iOS', quantity: 45000, percentage: 45 },
      { device_type: 'Android', quantity: 35000, percentage: 35 },
      { device_type: 'Web', quantity: 15000, percentage: 15 },
      { device_type: 'H5', quantity: 5000, percentage: 5 },
    ]
    totalUsageQuantity.value = 100000

    // 性能优化: 缓存所有数据
    customerStore.cacheCustomerData(id, {
      customer: customer.value,
      profile: profile.value,
      balance: balance.value,
      invoices: invoices.value,
      healthScore: healthScore.value,
      balanceTrend: balanceTrend.value,
    })
  } catch (error) {
    Message.error('加载客户数据失败')
    console.error('加载客户数据失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取状态样式类
const getStatusClass = (status: string) => {
  const statusMap: Record<string, string> = {
    draft: 'warning',
    submitted: 'warning',
    confirmed: 'success',
    paid: 'success',
    completed: 'success',
  }
  return statusMap[status] || 'warning'
}

// 获取状态文本
const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    draft: '草稿',
    submitted: '已提交',
    confirmed: '已确认',
    paid: '已付款',
    completed: '已完成',
  }
  return statusMap[status] || status
}

// 打开编辑对话框
const openEditModal = () => {
  // 防护检查：确保 profile 数据已加载
  if (profileLoading.value || !profile.value || profile.value.id === 0) {
    Message.warning('客户画像数据加载中，请稍后编辑')
    return
  }
  
  editForm.value = {
    name: customer.value.name || '',
    company_id: customer.value.company_id || '',
    email: customer.value.email || '',
    account_type: customer.value.account_type || undefined,
    industry: customer.value.industry || undefined,
    customer_level: customer.value.customer_level || undefined,
    settlement_type: customer.value.settlement_type || undefined,
    settlement_cycle: customer.value.settlement_cycle || undefined,
    is_key_customer: customer.value.is_key_customer || false,
    manager_id: customer.value.manager_id || undefined,
    // 新增字段
    erp_system: customer.value.erp_system || undefined,
    first_payment_date: customer.value.first_payment_date || undefined,
    onboarding_date: customer.value.onboarding_date || undefined,
    sales_manager_id: customer.value.sales_manager_id || undefined,
    cooperation_status: customer.value.cooperation_status || undefined,
    is_settlement_enabled: customer.value.is_settlement_enabled ?? true,
    is_disabled: customer.value.is_disabled ?? false,
    notes: customer.value.notes || undefined,
    // 规模等级和消费等级（来自 CustomerProfile）
    scale_level: profile.value.scale_level || undefined,
    consume_level: profile.value.consume_level || undefined,
  }
  editModalVisible.value = true
}

// 提交编辑
const handleEditSubmit = async () => {
  // 1. 客户端表单验证
  try {
    await editFormRef.value?.validate()
  } catch {
    return false
  }

  // 2. 日期格式校验
  if (editForm.value.first_payment_date) {
    const paymentDate = new Date(editForm.value.first_payment_date)
    const today = new Date()
    today.setHours(23, 59, 59, 999)
    if (paymentDate > today) {
      Message.error('首次回款时间不能超过今天')
      return false
    }
  }

  if (editForm.value.onboarding_date) {
    const onboardingDate = new Date(editForm.value.onboarding_date)
    const today = new Date()
    today.setHours(23, 59, 59, 999)
    if (onboardingDate > today) {
      Message.error('接入时间不能超过今天')
      return false
    }
  }

  // 3. 首次回款时间不能早于接入时间
  if (editForm.value.first_payment_date && editForm.value.onboarding_date) {
    const paymentDate = new Date(editForm.value.first_payment_date)
    const onboardingDate = new Date(editForm.value.onboarding_date)
    if (paymentDate < onboardingDate) {
      Message.error('首次回款时间不能早于接入时间')
      return false
    }
  }

  editLoading.value = true
  try {
    // 并行更新 Customer 和 CustomerProfile
    // 注意：Promise.all 任一失败会进入 catch 块，两个更新都是幂等的可重试操作
    await Promise.all([
      updateCustomer(customerId.value, {
        company_id: editForm.value.company_id,
        name: editForm.value.name,
        email: editForm.value.email || undefined,
        account_type: editForm.value.account_type || undefined,
        industry: editForm.value.industry || undefined,
        customer_level: editForm.value.customer_level || undefined,
        settlement_type: editForm.value.settlement_type,
        settlement_cycle: editForm.value.settlement_cycle || undefined,
        is_key_customer: editForm.value.is_key_customer,
        manager_id: editForm.value.manager_id || undefined,
        erp_system: editForm.value.erp_system || undefined,
        first_payment_date: editForm.value.first_payment_date || undefined,
        onboarding_date: editForm.value.onboarding_date || undefined,
        sales_manager_id: editForm.value.sales_manager_id || undefined,
        cooperation_status: editForm.value.cooperation_status || undefined,
        is_settlement_enabled: editForm.value.is_settlement_enabled,
        is_disabled: editForm.value.is_disabled,
        notes: editForm.value.notes || undefined,
      }),
      updateProfile(customerId.value, {
        scale_level: editForm.value.scale_level || undefined,
        consume_level: editForm.value.consume_level || undefined,
      }),
    ])
    Message.success('更新成功')
    editModalVisible.value = false
    // 性能优化: 更新后清除缓存
    customerStore.invalidateCustomerCache(customerId.value)
    await loadCustomerData()
    return true
  } catch (error: unknown) {
    // 处理服务端 company_id 排重错误
    const err = error as { message?: string; response?: { data?: { message?: string } } }
    if (err.response?.data?.message) {
      Message.error(err.response.data.message)
    } else if (err.message?.includes('公司 ID')) {
      Message.error(err.message)
    } else {
      Message.error('更新失败')
    }
    console.error('更新失败:', error)
    return false
  } finally {
    editLoading.value = false
  }
}

const handleEditCancel = () => {
  editModalVisible.value = false
  editFormRef.value?.resetFields()
}

// 切换重点客户
const toggleKeyCustomer = async () => {
  keyCustomerLoading.value = true
  try {
    await updateCustomer(customerId.value, {
      is_key_customer: !customer.value.is_key_customer,
    })
    Message.success(customer.value.is_key_customer ? '已取消重点客户' : '已设为重点客户')
    customer.value.is_key_customer = !customer.value.is_key_customer
    // 性能优化: 更新 store 缓存
    customerStore.updateCachedCustomerPart(customerId.value, 'customer', customer.value)
  } catch (error) {
    Message.error('操作失败')
    console.error('切换重点客户失败:', error)
  } finally {
    keyCustomerLoading.value = false
  }
}

// 查看结算单
const viewInvoice = (record: Invoice) => {
  Message.info(`查看结算单：${record.invoice_no}`)
}

// ========== 标签管理 ==========

// 加载客户标签
const loadCustomerTags = async () => {
  // 性能优化: 检查缓存
  const cachedTags = customerStore.getCachedTags(customerId.value)
  if (cachedTags && customerStore.hasCachedTags(customerId.value)) {
    customerTags.value = cachedTags.customerTags
    allTags.value = cachedTags.allTags
    return
  }

  try {
    const [customerTagsRes, allTagsRes] = await Promise.all([
      getCustomerTags(customerId.value),
      getTags({ type: 'customer', page_size: 100 }),
    ])
    customerTags.value = customerTagsRes.data || []
    allTags.value = allTagsRes.data?.list || []
    // 性能优化: 缓存数据
    customerStore.cacheTagsData(customerId.value, {
      customerTags: customerTags.value,
      allTags: allTags.value,
    })
  } catch (error) {
    console.error('加载客户标签失败:', error)
  }
}

// 加载所有可用的客户标签（保留用于标签选择器打开时刷新）
const loadAllTags = async () => {
  allTagsLoading.value = true
  try {
    const res = await getTags({ type: 'customer', page_size: 100 })
    allTags.value = res.data?.list || []
  } catch (error) {
    console.error('加载标签列表失败:', error)
  } finally {
    allTagsLoading.value = false
  }
}

// 计算可用标签（已添加的标签不显示）
const availableTags = computed(() => {
  const addedIds = new Set(customerTags.value.map((t) => t.id))
  return allTags.value.filter((t) => !addedIds.has(t.id))
})

// 合作状态展示
const cooperationStatusColor = computed(() => {
  const status = customer.value.cooperation_status
  if (status === 'active') return 'green'
  if (status === 'suspended') return 'orange'
  if (status === 'terminated') return 'red'
  return 'gray'
})

const cooperationStatusText = computed(() => {
  const status = customer.value.cooperation_status
  const map: Record<string, string> = {
    active: '合作中',
    suspended: '暂停',
    terminated: '终止',
  }
  return map[status || ''] || '-'
})

// 消费等级显示映射
const CONSUME_LEVEL_MAP: Record<string, string> = {
  S: 'S - 100万',
  A: 'A - 50万',
  B: 'B - 25万',
  C: 'C - 12万',
  D: 'D - 6万',
}

// 消费等级显示文本
const consumeLevelDisplay = computed(() => {
  const level = profile.value.consume_level
  if (!level) return '-'
  return CONSUME_LEVEL_MAP[level] || level
})

// 销售负责人名称（从 managers 列表中查找）
const salesManagerName = computed(() => {
  if (!customer.value.sales_manager_id) return null
  const manager = managers.value.find((m) => m.id === customer.value.sales_manager_id)
  return manager ? manager.real_name || manager.username : null
})

// 打开标签选择器
const openTagSelector = async () => {
  selectedTagIds.value = []
  await loadAllTags()
  tagSelectorVisible.value = true
}

// 添加标签
const handleAddTag = async () => {
  if (selectedTagIds.value.length === 0) {
    Message.warning('请选择要添加的标签')
    return
  }

  tagSelectorLoading.value = true
  try {
    for (const tagId of selectedTagIds.value) {
      await addCustomerTag(customerId.value, tagId)
    }
    Message.success('标签添加成功')
    tagSelectorVisible.value = false
    // 性能优化: 更新后清除缓存并重新加载
    customerStore.invalidateTagsCache(customerId.value)
    await loadCustomerTags()
  } catch (error) {
    Message.error((error as Error).message || '添加标签失败')
  } finally {
    tagSelectorLoading.value = false
  }
}

// 移除标签
const removeTag = async (tagId: number) => {
  try {
    await removeCustomerTag(customerId.value, tagId)
    Message.success('标签移除成功')
    // 性能优化：更新后清除缓存并重新加载
    customerStore.invalidateTagsCache(customerId.value)
    await loadCustomerTags()
  } catch (error) {
    Message.error((error as Error).message || '移除标签失败')
  }
}

// 加载用量数据
const loadUsageData = async () => {
  usageLoading.value = true
  try {
    const res = await getDailyUsage({
      customer_id: customerId.value,
      page: usagePagination.current,
      page_size: usagePagination.pageSize,
    })
    usageData.value = res.data?.list || []
    usagePagination.total = res.data?.total || 0
  } catch (error) {
    console.error('加载用量数据失败:', error)
  } finally {
    usageLoading.value = false
  }
}

const handleUsagePageChange = (page: number) => {
  usagePagination.current = page
  loadUsageData()
}

onMounted(() => {
  loadCustomerData()
  loadCustomerTags()
  loadUsageData()
  loadManagers()
  window.addEventListener('resize', handleResize)
})

// 弹窗宽度响应式更新
const handleResize = () => {
  // 触发 modalWidth computed 重新计算
  window.dispatchEvent(new Event('resize'))
}

// 性能优化: 路由变化时重置状态（防止复用组件时状态残留）
watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId !== oldId) {
      activeTab.value = 'basic'
      loadedTabs.value = new Set(['basic'])
      chartRenderState.value = {}
      if (tabLoadTimer) {
        clearTimeout(tabLoadTimer)
        tabLoadTimer = null
      }
      loadCustomerData()
      loadCustomerTags()
      loadUsageData()
    }
  }
)

// 性能优化: 组件卸载时清理定时器和事件监听器，防止内存泄漏
onUnmounted(() => {
  if (tabLoadTimer) {
    clearTimeout(tabLoadTimer)
    tabLoadTimer = null
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.customer-detail-page {
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-6: #646a73;
  --neutral-10: #1d2330;
  --primary-1: #e8f3ff;
  --primary-6: #0369a1;
  --success-bg: #e8ffea;
  --success-color: #22c55e;
  --warning-bg: #fff7e8;
  --warning-color: #f59e0b;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 12px;

  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);

  /* 修复容器宽度溢出问题 - 不允许横向滚动 */
  width: 100%;
  overflow-x: hidden;
  box-sizing: border-box;
}

/* Arco Spin 组件宽度约束 */
:deep(.arco-spin) {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

:deep(.arco-spin-nested-loading) {
  width: 100%;
  max-width: 100%;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-10);
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.tabs-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  padding: 32px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* 双列信息网格 - 基础信息面板 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0;
  padding: 8px 0;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.info-item {
  display: flex;
  flex-direction: column;
  padding: 14px 16px;
  border-bottom: 1px solid var(--neutral-2);
  transition: background-color var(--transition-fast);
}

.info-item:hover {
  background-color: var(--neutral-1);
}

.info-item .label {
  font-size: 13px;
  font-weight: 600;
  color: var(--neutral-6);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 6px;
}

.info-item .value {
  font-size: 14px;
  color: var(--neutral-10);
  font-weight: 500;
  line-height: 1.5;
}

/* 客户标签占满整行 */
.info-item.full-width {
  grid-column: 1 / -1;
}

/* 客户标签区域 */
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tags-container :deep(.arco-btn-text) {
  height: 28px;
  padding: 0 12px;
  border-radius: 6px;
  transition: all var(--transition-fast);
  border: 1px dashed var(--neutral-6);
  background: transparent;
  color: var(--neutral-6);
  font-size: 13px;
}

.tags-container :deep(.arco-btn-text:hover) {
  border-color: var(--primary-6);
  background: var(--primary-1);
  color: var(--primary-6);
}

/* 响应式适配 - 平板及中等屏幕 */
@media (min-width: 375px) and (max-width: 768px) {
  .info-grid {
    grid-template-columns: 1fr;
  }

  .info-item .label {
    font-size: 12px;
  }

  .info-item .value {
    font-size: 14px;
  }
}

/* 余额卡片 - 自适应 Grid 布局 */
.balance-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-lg, 24px);
  padding: var(--space-lg, 24px) var(--space-md, 16px);
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

/* 4 张卡片最佳布局 */
@media (min-width: 1400px) {
  .balance-cards {
    grid-template-columns: repeat(4, 1fr);
  }
}

/* 响应式适配 */
@media (max-width: 1199px) and (min-width: 768px) {
  .balance-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 767px) {
  .balance-cards {
    grid-template-columns: 1fr;
  }
}

.balance-card {
  background: linear-gradient(135deg, #ffffff 0%, var(--neutral-1) 100%);
  padding: var(--space-lg, 20px) var(--space-md, 16px);
  border-radius: var(--radius-lg, 12px);
  text-align: center;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm, 0 2px 4px rgba(0, 0, 0, 0.04));
  transition: all var(--transition-base, 250ms) cubic-bezier(0.34, 1.56, 0.64, 1);
  min-height: 110px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.balance-card::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(3, 105, 161, 0.1) 0%, transparent 70%);
  opacity: 0;
  transition: opacity var(--transition-base, 250ms) ease-out;
  pointer-events: none;
}

.balance-card::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--primary-6), #0ea5e9, var(--primary-6));
  transform: scaleX(0);
  transition: transform var(--transition-base, 250ms) ease-out;
  border-radius: var(--radius-lg, 12px) var(--radius-lg, 12px) 0 0;
}

.balance-card:hover {
  transform: translateY(-6px) scale(1.02);
  box-shadow: 0 20px 40px rgba(3, 105, 161, 0.2), 0 8px 16px rgba(0, 0, 0, 0.1);
  border-color: var(--primary-6);
  background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%);
}

.balance-card:hover::before {
  opacity: 1;
}

.balance-card:hover::after {
  transform: scaleX(1);
}
.balance-label {
  font-size: 13px;
  color: var(--neutral-6);
  margin-bottom: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.balance-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--neutral-10);
  line-height: 1.2;
}

.balance-value.real {
  color: var(--primary-6);
}

.balance-value.bonus {
  color: var(--success-color);
}
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}
.status-badge.success {
  background: var(--success-bg);
  color: var(--success-color);
}
.status-badge.warning {
  background: var(--warning-bg);
  color: var(--warning-color);
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

/* ========== 画像信息页面优化样式 ========== */

/* 画像信息整体包装器 */
.profile-tab-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 核心指标网格 - 3 列布局 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

/* 核心指标卡片 */
.metric-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-radius: 12px;
  min-height: 72px;
  background: #ffffff;
  border: 1px solid var(--neutral-2);
  transition: all 200ms ease;
  position: relative;
  overflow: hidden;
}

/* 加载状态 */
.metric-card.loading {
  background: var(--neutral-1);
  border-color: transparent;
  pointer-events: none;
}

.metric-card.loading :deep(.skeleton-card) {
  opacity: 0.6;
}

/* 主色指标卡片 - 规模等级 */
.metric-card.primary {
  background: linear-gradient(135deg, #0369A1 0%, #0EA5E9 100%);
  border-color: transparent;
  color: #ffffff;
}

.metric-card.primary .metric-label {
  color: rgba(255, 255, 255, 0.85);
}

.metric-card.primary .metric-value {
  color: #ffffff;
  font-size: 20px;
  font-weight: 700;
}

.metric-card.primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(3, 105, 161, 0.25);
}

/* 成功色指标卡片 - 消费等级 */
.metric-card.success {
  background: linear-gradient(135deg, #059669 0%, #10B981 100%);
  border-color: transparent;
  color: #ffffff;
}

.metric-card.success .metric-label {
  color: rgba(255, 255, 255, 0.85);
}

.metric-card.success .metric-value {
  color: #ffffff;
  font-size: 20px;
  font-weight: 700;
}

.metric-card.success:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(5, 150, 105, 0.25);
}

/* 警告色指标卡片 - 预估年消费 */
.metric-card.warning {
  background: linear-gradient(135deg, #D97706 0%, #F59E0B 100%);
  border-color: transparent;
  color: #ffffff;
}

.metric-card.warning .metric-label {
  color: rgba(255, 255, 255, 0.85);
}

.metric-card.warning .metric-value {
  color: #ffffff;
  font-size: 20px;
  font-weight: 700;
}

.metric-card.warning:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(217, 119, 6, 0.25);
}

/* 普通指标卡片 */
.metric-card .metric-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--neutral-5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.metric-card .metric-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--neutral-10);
  line-height: 1.2;
}

/* 指标卡片 Hover 效果 - 简化版 */
.metric-card:not(.primary):not(.success):not(.warning):not(.loading):hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: var(--primary-1);
  background: #fafbfc;
}

/* 图表网格 - 2列布局 */
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

/* 图表面板 */
.chart-panel {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid var(--neutral-2);
  padding: 20px;
  transition: all 200ms ease;
}

.chart-panel:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  border-color: var(--neutral-3);
}

/* 图表标题 */
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--neutral-10);
  margin: 0 0 4px 0;
  line-height: 1.4;
}

.chart-description {
  font-size: 12px;
  color: var(--neutral-5);
  margin: 0 0 16px 0;
  line-height: 1.5;
}

/* 图表内容区 */
.chart-content {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-content :deep(.health-gauge),
.chart-content :deep(.consume-level-progress) {
  width: 100%;
  max-width: 100%;
}

/* 加载状态 */
.chart-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 240px;
  width: 100%;
}

/* 响应式布局 */
@media (max-width: 1199px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .charts-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .metrics-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  
  .metric-card {
    padding: 14px 16px;
    min-height: 64px;
  }
  
  .metric-card .metric-value {
    font-size: 16px;
  }
  
  .metric-card.primary .metric-value,
  .metric-card.success .metric-value {
    font-size: 18px;
  }
  
  .charts-grid {
    gap: 16px;
  }
  
  .chart-panel {
    padding: 16px;
  }
  
  .chart-content {
    min-height: 200px;
  }
}

@media (max-width: 480px) {
  .metric-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .metric-card .metric-value {
    font-size: 18px;
  }
}

/* 减少运动偏好支持 */
@media (prefers-reduced-motion: reduce) {
  .metric-card,
  .chart-panel {
    transition: none;
  }
  
  .metric-card:hover {
    transform: none;
  }
}

/* Tabs 容器 - 防止内容溢出 */
:deep(.arco-tabs-pane) {
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
  box-sizing: border-box;
}

:deep(.arco-tabs-content) {
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
  box-sizing: border-box;
}

/* 表格自动布局 - 确保表格不超过容器宽度 */
:deep(.arco-table) {
  table-layout: fixed;
  width: 100%;
  max-width: 100%;
}

:deep(.arco-table-wrapper) {
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
}

/* 表格容器 - 支持横向滚动 */
.table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--neutral-2);
  border-radius: var(--radius-md);
}

/* 表格空状态居中样式 */
:deep(.arco-table-empty) {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 48px 24px;
  min-height: 300px;
}

:deep(.arco-table-empty .empty-state) {
  margin: 0 auto;
}

/* 空数据最小高度，防止布局塌陷 */
.info-grid,
.balance-cards {
  min-height: 200px;
}

/* 响应式断点 */
/* XS Mobile - 374px and below */
@media (max-width: 374px) {
  .info-grid,
  .balance-cards {
    grid-template-columns: 1fr;
    gap: 16px;
    padding: 16px 12px;
  }

  .info-item {
    padding: 12px;
    min-height: 80px;
  }

  .balance-card {
    padding: 16px 12px;
    min-height: 100px;
  }

  .balance-value {
    font-size: 26px;
  }

  .tabs-section {
    padding: 12px;
    border-radius: 12px;
  }

  .header-title h1 {
    font-size: 20px;
  }
}

/* Mobile - 375px to 767px */
@media (min-width: 375px) and (max-width: 767px) {
  .balance-cards {
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .header-actions {
    width: 100%;
  }

  .header-actions .arco-btn {
    flex: 1;
  }

  .tabs-section {
    padding: 20px 16px;
  }

  .header-title h1 {
    font-size: 22px;
  }

  .balance-value {
    font-size: 28px;
  }
}

/* Tablet - 768px to 1199px */
@media (min-width: 768px) and (max-width: 1199px) {
  .balance-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .tabs-section {
    padding: 28px;
  }
}

/* Large Tablet / Small Desktop - 1200px to 1399px */
@media (min-width: 1200px) and (max-width: 1399px) {
  .balance-cards {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* Desktop - 1400px+ */
@media (min-width: 1400px) {
  .balance-cards {
    grid-template-columns: repeat(4, 1fr);
  }
}

/* Ultra-wide screens - 1600px+ */
@media (min-width: 1600px) {
  .tabs-section {
    max-width: 1600px;
    margin: 0 auto;
  }
}

/* 余额趋势区域 */
.balance-trend-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--neutral-2);
  width: 100%;
  box-sizing: border-box;
  min-height: 400px;
}

/* 用量分布区域 */
.usage-distribution-section {
  margin-bottom: 24px;
  width: 100%;
  box-sizing: border-box;
  min-height: 350px;
  background: white;
  border-radius: var(--radius-md, 10px);
  padding: 16px;
  border: 1px solid var(--neutral-2);
}

.usage-table-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--neutral-2);
  width: 100%;
  box-sizing: border-box;
}

/* 减少运动偏好支持 */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* 扩展指标网格间距 */
.metrics-grid-extended {
  margin-top: 4px;
}

/* 备注文字样式 - 支持换行 */
.notes-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

/* ========== 编辑弹框三列布局 ========== */

/* 编辑表单网格容器 */
.edit-form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0 20px;
  width: 100%;
}

/* 编辑表单列 */
.edit-form-column {
  display: flex;
  flex-direction: column;
}

/* 列标题 */
.edit-form-column .column-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary-6, #0369a1);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--primary-1, #e8f3ff);
}

/* 列分隔线 */
.edit-form-column + .edit-form-column {
  border-left: 1px solid var(--neutral-2, #eef0f3);
  padding-left: 20px;
}

/* 备注区域 - 横跨三列 */
.edit-form-note {
  grid-column: 1 / -1;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--neutral-2, #eef0f3);
}

/* 响应式降级：两列 */
@media (max-width: 1399px) {
  .edit-form-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .edit-form-column:nth-child(1) {
    border-right: 1px solid var(--neutral-2, #eef0f3);
    padding-right: 20px;
  }

  .edit-form-column:nth-child(2) {
    border-left: none;
    padding-left: 0;
  }

  .edit-form-column:nth-child(3) {
    border-top: 1px solid var(--neutral-2, #eef0f3);
    padding-top: 16px;
    margin-top: 16px;
    grid-column: 1 / -1;
  }

  .edit-form-column:nth-child(3) .column-title {
    margin-bottom: 12px;
  }
}

/* 响应式降级：单列 */
@media (max-width: 767px) {
  .edit-form-grid {
    grid-template-columns: 1fr;
  }

  .edit-form-column {
    border-left: none !important;
    border-right: none !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    border-top: none !important;
    padding-top: 0 !important;
    margin-top: 0 !important;
    grid-column: auto !important;
  }

  .edit-form-column + .edit-form-column {
    border-top: 1px solid var(--neutral-2, #eef0f3);
    padding-top: 16px;
    margin-top: 16px;
  }

  .edit-form-note {
    border-top: 1px solid var(--neutral-2, #eef0f3);
  }
}
</style>
