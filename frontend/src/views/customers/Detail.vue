<template>
  <div class="customer-detail-page">
    <div v-if="loading" class="page-loading">
      <a-spin :size="24" />
    </div>
    <template v-else>
      <!-- PageHeader -->
      <PageHeader :eyebrow="'Customer Detail'" :title="customer?.name || '客户详情'"
        subtitle="详情页按基础信息、画像、余额、消耗、结算、操作记录聚合，支持运营在一个页面完成判断。">
        <template #actions>
          <a-button @click="goBack">返回</a-button>
          <a-button @click="openEdit">编辑</a-button>
          <a-button type="primary" :loading="keyCustomerLoading" @click="toggleKeyCustomer">
            {{ customer?.is_key_customer ? '取消重点' : '设为重点' }}
          </a-button>
        </template>
      </PageHeader>

      <!-- Tab 区域 -->
      <div class="tabs-card">
        <a-tabs v-model="activeTab" type="rounded" @change="handleTabChange">
          <a-tab-pane key="basic" title="基础信息">
            <CustomerBasicTab
              v-if="customer"
              :key="customer?.id"
              :customer="customer as any"
              :managers="managers as any"
              :customer-tags="customerTags as any"
              @open-tag-selector="openTagSelector"
              @remove-tag="removeTag"
            />
          </a-tab-pane>
          <a-tab-pane key="profile" title="画像信息">
            <CustomerProfileTab
              v-if="profile"
              :key="profile?.id"
              :profile="profile as any"
              :profile-loading="profileLoading as boolean"
              :health-score="healthScore as any"
              :health-score-loading="healthScoreLoading as boolean"
            />
          </a-tab-pane>
          <a-tab-pane key="balance" title="余额信息">
            <CustomerBalanceTab
              v-if="balance"
              :key="balance?.customer_id"
              :balance="balance as any"
              :balance-loading="balanceLoading as boolean"
              :balance-trend="balanceTrend as any"
              :balance-trend-loading="balanceTrendLoading as boolean"
              :should-render-balance-trend="shouldRenderBalanceTrend as any"
            />
          </a-tab-pane>
          <a-tab-pane key="invoices" title="结算单">
            <CustomerInvoicesTab
              :invoices="invoices as any"
              @view-invoice="viewInvoice"
            />
          </a-tab-pane>
          <a-tab-pane key="usage" title="用量分析">
            <CustomerUsageTab
              :usage-data="usageData as any"
              :usage-loading="usageLoading as boolean"
              :usage-pagination="usagePagination as any"
              @page-change="loadUsage"
            />
          </a-tab-pane>
        </a-tabs>
      </div>

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
      />

      <!-- 标签选择器对话框 -->
      <TagSelectorDialog
        :visible="tagSelectorVisible as boolean"
        :loading="tagSelectorLoading as boolean"
        :all-tags="allTags as any"
        :all-tags-loading="allTagsLoading as boolean"
        :customer-tags="customerTags as any"
        @add="addTags"
        @close="closeTagSelector"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { useCustomerDetail } from '@/composables/useCustomerDetail'
import PageHeader from '@/components/PageHeader.vue'

import EditCustomerDialog from './detail/EditCustomerDialog.vue'
import TagSelectorDialog from './detail/TagSelectorDialog.vue'
import CustomerBasicTab from './detail/CustomerBasicTab.vue'
import CustomerProfileTab from './detail/CustomerProfileTab.vue'
import CustomerBalanceTab from './detail/CustomerBalanceTab.vue'
import CustomerInvoicesTab from './detail/CustomerInvoicesTab.vue'
import CustomerUsageTab from './detail/CustomerUsageTab.vue'

// 使用 composable 管理详情页所有状态和逻辑
const {
  customer, loading, activeTab,
  balance, balanceLoading, balanceTrend, balanceTrendLoading, shouldRenderBalanceTrend,
  profile, profileLoading,
  invoices,
  usageData, usageLoading, usagePagination,
  healthScore, healthScoreLoading,
  editModalVisible, editLoading, modalWidth,
  tagSelectorVisible, tagSelectorLoading,
  customerTags, allTags, allTagsLoading,
  managers, industryTypes, industryTypesLoading, pricePolicyOptions,
  keyCustomerLoading,
  loadUsage, viewInvoice,
  handleTabChange,
  goBack, openEdit, submitEdit, toggleKeyCustomer,
  openTagSelector, closeTagSelector, addTags, removeTag,
} = useCustomerDetail()
</script>

<style scoped>
.customer-detail-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
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

/* ---- PageHeader ---- */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-info {
  display: flex;
  flex-direction: column;
}

.title-info h1 {
  font-size: 26px;
  font-weight: 850;
  color: var(--ink);
  margin: 2px 0 0 0;
  line-height: 1.2;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* ---- Tabs Card ---- */
.tabs-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 24px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: auto;
}

/* Arco Tabs 药丸标签样式 */
.tabs-card :deep(.arco-tabs-nav) {
  margin-bottom: 20px;
}

.tabs-card :deep(.arco-tabs-tab) {
  border-radius: 999px;
  padding: 7px 16px;
  font-weight: 700;
  font-size: 13px;
  transition: all var(--transition-fast);
}

.tabs-card :deep(.arco-tabs-tab-active) {
  background: #DBEAFE;
  border-color: #BFDBFE;
  color: var(--primary);
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

/* 表格自动布局 */
:deep(.arco-table) {
  table-layout: auto;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

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

/* 表格表头 */
:deep(.arco-table-th) {
  background: #F8FAFC;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

/* 表格行 hover */
:deep(.arco-table-tr:hover .arco-table-td) {
  background: #F8FBFF;
}

/* 空状态 */
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

/* 响应式 */
@media (max-width: 767px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .header-actions {
    width: 100%;
  }

  .header-actions .arco-btn {
    flex: 1;
  }

  .tabs-card {
    padding: 16px;
  }

  .title-info h1 {
    font-size: 22px;
  }
}
</style>
