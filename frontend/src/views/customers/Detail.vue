<template>
  <div class="customer-detail-page">
    <div v-if="loading" class="page-loading">
      <a-spin :size="24" />
    </div>
    <template v-else>
      <AppPageHeader
        :eyebrow="customer?.industry || 'Customer'"
        :title="customer?.name || '客户详情'"
        description="客户 360° 全景视图，涵盖基础档案、画像洞察、财务状况、结算记录与用量趋势。"
      >
        <template #actions>
          <a-button type="text" @click="goBack">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path fill-rule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 1 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z" />
            </svg>
            返回列表
          </a-button>
          <a-button @click="openEdit">编辑</a-button>
          <a-button type="primary" :loading="keyCustomerLoading" @click="toggleKeyCustomer">
            {{ customer?.is_key_customer ? '取消重点' : '设为重点' }}
          </a-button>
        </template>
      </AppPageHeader>

      <MetricGrid>
        <MetricCard
          label="客户等级"
          :value="customer?.customer_level || '未分级'"
          trend="定级依据：消耗/合同"
          trend-type="neutral"
        />
        <MetricCard
          label="账户余额"
          :value="balance ? formatCurrencyWan(balance.total_balance || 0) : '—'"
          :trend="balance?.real_balance < 0 ? '余额不足' : '余额充足'"
          :trend-type="balance?.real_balance < 0 ? 'down' : 'up'"
        />
        <MetricCard
          label="本月消耗"
          :value="balance ? formatCurrencyWan(balance.month_consumption || 0) : '—'"
          trend="月度预算执行"
          trend-type="up"
        />
        <MetricCard
          label="健康分"
          :value="healthScore?.score || '—'"
          :trend="healthScore?.level || '评估中'"
          :trend-type="healthScore?.score >= 80 ? 'up' : healthScore?.score >= 60 ? 'warn' : 'down'"
        />
      </MetricGrid>

      <DataSection title="基础信息" subtitle="核心档案字段">
        <CustomerBasicTab
          v-if="customer"
          :key="customer?.id"
          :customer="customer as any"
          :managers="managers as any"
          :customer-tags="customerTags as any"
          @open-tag-selector="openTagSelector"
          @remove-tag="removeTag"
        />
      </DataSection>

      <DataSection title="画像信息" subtitle="多维画像标签与洞察">
        <CustomerProfileTab
          v-if="profile"
          :key="profile?.id"
          :profile="profile as any"
          :profile-loading="profileLoading as boolean"
          :health-score="healthScore as any"
          :health-score-loading="healthScoreLoading as boolean"
        />
      </DataSection>

      <DataSection title="余额信息" subtitle="实时余额、消耗趋势与预警">
        <CustomerBalanceTab
          v-if="balance"
          :key="balance?.customer_id"
          :balance="balance as any"
          :balance-loading="balanceLoading as boolean"
          :balance-trend="balanceTrend as any"
          :balance-trend-loading="balanceTrendLoading as boolean"
          :should-render-balance-trend="shouldRenderBalanceTrend as any"
        />
      </DataSection>

      <DataSection title="结算单" subtitle="历史结算记录" :count="invoices?.length">
        <CustomerInvoicesTab
          :invoices="invoices as any"
          @view-invoice="viewInvoice"
        />
      </DataSection>

      <DataSection title="用量分析" subtitle="用量趋势与明细" :count="usagePagination?.total">
        <CustomerUsageTab
          :usage-data="usageData as any"
          :usage-loading="usageLoading as boolean"
          :usage-pagination="usagePagination as any"
          @page-change="loadUsage"
        />
      </DataSection>

      <DataSection title="操作记录" subtitle="关键业务操作审计轨迹">
        <div class="placeholder-section">操作记录待开发</div>
      </DataSection>

      <!-- 编辑客户对话框 -->
      <EditCustomerDialog
        :visible="editModalVisible as boolean"
        :customer="customer as any"
        :edit-loading="editLoading as boolean"
        :modal-width="modalWidth as any"
        :industry-types="industryTypes as any"
        :industry-types-loading="industryTypesLoading as boolean"
        :managers="managers as any"
        :price-policy-options="pricePolicyOptions as any"
        @submit="(form) => submitEdit(form as any)"
        @close="editModalVisible = false"
        @update:modal-width="modalWidth = $event"
      />

      <!-- 标签选择器对话框 -->
      <TagSelectorDialog
        :visible="tagSelectorVisible as boolean"
        :customer-id="customer?.id as number"
        :customer-tags="customerTags as any"
        :all-tags="allTags as any"
        :all-tags-loading="allTagsLoading as boolean"
        @close="closeTagSelector"
        @add-tags="addTags"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { useCustomerDetail } from '@/composables/useCustomerDetail'
import { formatCurrencyWan } from '@/utils/formatters'

import EditCustomerDialog from './detail/EditCustomerDialog.vue'
import TagSelectorDialog from './detail/TagSelectorDialog.vue'
import CustomerBasicTab from './detail/CustomerBasicTab.vue'
import CustomerProfileTab from './detail/CustomerProfileTab.vue'
import CustomerBalanceTab from './detail/CustomerBalanceTab.vue'
import CustomerInvoicesTab from './detail/CustomerInvoicesTab.vue'
import CustomerUsageTab from './detail/CustomerUsageTab.vue'

// 新组件导入
import AppPageHeader from '@/components/dashboard/AppPageHeader.vue'
import MetricGrid from '@/components/dashboard/MetricGrid.vue'
import MetricCard from '@/components/dashboard/MetricCard.vue'
import DataSection from '@/components/dashboard/DataSection.vue'

// 使用 composable 管理详情页所有状态和逻辑
const {
  customer, loading,
  balance, balanceLoading, balanceTrend, balanceTrendLoading, shouldRenderBalanceTrend,
  profile, profileLoading,
  invoices,
  usageData, usageLoading, usagePagination,
  healthScore, healthScoreLoading,
  editModalVisible, editLoading, modalWidth,
  tagSelectorVisible,
  customerTags, allTags, allTagsLoading,
  managers, industryTypes, industryTypesLoading, pricePolicyOptions,
  keyCustomerLoading,
  loadUsage, viewInvoice,
  goBack, openEdit, submitEdit, toggleKeyCustomer,
  openTagSelector, closeTagSelector, addTags, removeTag,
} = useCustomerDetail()
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
.page-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
  width: 100%;
}


/* Arco Spin 组件宽度约束 */
::deep(.arco-spin) {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* 数据区块占位符样式 */
.placeholder-section {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  color: var(--cop-muted);
  font-size: 14px;
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
  margin: 0 0 8px 0;
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
  overflow-x: auto;
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


/* 表格自动布局 - 使用 auto 自适应，不强制固定宽度 */
:deep(.arco-table) {
  table-layout: auto;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box; /* 修复：Arco 默认 content-box + padding 导致溢出 */
}

/* 表格单元格内容不换行时截断显示 */
:deep(.arco-table-td),
:deep(.arco-table-th) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
.info-grid {
  min-height: 200px;
}

/* 响应式断点 */
/* XS Mobile - 374px and below */
@media (max-width: 374px) {
  .info-grid {
    grid-template-columns: 1fr;
    gap: 16px;
    padding: 16px 12px;
  }

  .info-item {
    padding: 12px;
    min-height: 80px;
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

}

/* Tablet - 768px to 1199px */
@media (min-width: 768px) and (max-width: 1199px) {

  .tabs-section {
    padding: 28px;
  }
}



/* Ultra-wide screens - 1600px+ */
@media (min-width: 1600px) {
  .tabs-section {
    max-width: 1600px;
    margin: 0 auto;
  }
}


/* 用量分布区域 */
.usage-distribution-section {
  margin-bottom: 24px;
  width: 100%;
  box-sizing: border-box;
  min-height: 350px;
}

.usage-table-section {
  margin-top: 24px;
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
