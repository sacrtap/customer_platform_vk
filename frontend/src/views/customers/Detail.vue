<template>
  <div class="customer-detail">
    <a-page-header
      title="客户详情"
      @back="handleBack"
    >
      <template #extra>
        <a-space>
          <a-button @click="handleEdit">编辑</a-button>
          <a-button type="primary" @click="toggleKeyCustomer">
            {{ customer.is_key_customer ? '取消重点' : '设为重点' }}
          </a-button>
        </a-space>
      </template>
    </a-page-header>

    <a-card style="margin-top: 16px">
      <a-tabs default-active-key="basic">
        <a-tab-pane key="basic" title="基础信息">
          <a-descriptions :column="2" bordered>
            <a-descriptions-item label="客户名称">{{ customer.name }}</a-descriptions-item>
            <a-descriptions-item label="公司 ID">{{ customer.company_id }}</a-descriptions-item>
            <a-descriptions-item label="账号类型">
              <a-tag>{{ customer.account_type || '-' }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="业务类型">
              <a-tag>{{ customer.business_type || '-' }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="客户等级">
              <a-tag>{{ customer.customer_level || '-' }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="重点客户">
              <a-tag :color="customer.is_key_customer ? 'orangered' : 'gray'">
                {{ customer.is_key_customer ? '是' : '否' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="结算方式">
              <a-tag :color="customer.settlement_type === 'prepaid' ? 'green' : 'arcoblue'">
                {{ customer.settlement_type === 'prepaid' ? '预付费' : '后付费' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="结算周期">
              {{ getSettlementCycleText(customer.settlement_cycle) }}
            </a-descriptions-item>
            <a-descriptions-item label="邮箱">{{ customer.email || '-' }}</a-descriptions-item>
            <a-descriptions-item label="创建时间">
              {{ formatDate(customer.created_at) }}
            </a-descriptions-item>
          </a-descriptions>
        </a-tab-pane>

        <a-tab-pane key="profile" title="客户画像">
          <a-form v-if="profile" layout="vertical">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="客户规模等级">
                  <a-input v-model="profile.scale_level" placeholder="请输入规模等级" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="客户消费等级">
                  <a-input v-model="profile.consume_level" placeholder="请输入消费等级" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="所属行业">
                  <a-input v-model="profile.industry" placeholder="请输入行业" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="是否房产">
                  <a-switch v-model="profile.is_real_estate" checked-children="是" unchecked-children="否" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="描述">
              <a-textarea v-model="profile.description" :rows="4" placeholder="请输入描述" />
            </a-form-item>
            <a-form-item>
              <a-button type="primary" :loading="profileLoading" @click="saveProfile">保存画像</a-button>
            </a-form-item>
          </a-form>
          <a-empty v-else>
            <template #description>
              <span>暂无画像信息，请添加</span>
            </template>
            <a-button type="primary" @click="initProfile">创建画像</a-button>
          </a-empty>
        </a-tab-pane>

        <a-tab-pane key="balance" title="账户余额">
          <a-descriptions :column="3" bordered>
            <a-descriptions-item label="总余额">
              <a-statistic :value="balance.total_amount" :precision="2" suffix="元" />
            </a-descriptions-item>
            <a-descriptions-item label="现金余额">
              <a-statistic :value="balance.real_amount" :precision="2" suffix="元" />
            </a-descriptions-item>
            <a-descriptions-item label="赠金余额">
              <a-statistic :value="balance.bonus_amount" :precision="2" suffix="元" />
            </a-descriptions-item>
            <a-descriptions-item label="已用总额">
              <a-statistic :value="balance.used_total" :precision="2" suffix="元" />
            </a-descriptions-item>
            <a-descriptions-item label="已用现金">
              <a-statistic :value="balance.used_real" :precision="2" suffix="元" />
            </a-descriptions-item>
            <a-descriptions-item label="已用赠金">
              <a-statistic :value="balance.used_bonus" :precision="2" suffix="元" />
            </a-descriptions-item>
          </a-descriptions>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import * as customerApi from '@/api/customers'

const route = useRoute()
const router = useRouter()

const customer = ref<any>({
  id: 0,
  company_id: '',
  name: '',
  account_type: '',
  business_type: '',
  customer_level: '',
  settlement_cycle: '',
  settlement_type: '',
  is_key_customer: false,
  email: '',
  created_at: '',
})

const profile = ref<any>(null)
const profileLoading = ref(false)
const balance = ref({
  total_amount: 0,
  real_amount: 0,
  bonus_amount: 0,
  used_total: 0,
  used_real: 0,
  used_bonus: 0,
})

const fetchData = async () => {
  try {
    const res = await customerApi.getCustomer(Number(route.params.id))
    customer.value = res.data
    profile.value = res.data.profile
    balance.value = res.data.balance || {
      total_amount: 0,
      real_amount: 0,
      bonus_amount: 0,
      used_total: 0,
      used_real: 0,
      used_bonus: 0,
    }
  } catch (err: any) {
    Message.error(err.message || '加载失败')
  }
}

const saveProfile = async () => {
  profileLoading.value = true
  try {
    await customerApi.updateProfile(Number(route.params.id), {
      scale_level: profile.value?.scale_level,
      consume_level: profile.value?.consume_level,
      industry: profile.value?.industry,
      is_real_estate: profile.value?.is_real_estate,
      description: profile.value?.description,
    })
    Message.success('保存成功')
  } catch (err: any) {
    Message.error(err.message || '保存失败')
  } finally {
    profileLoading.value = false
  }
}

const initProfile = async () => {
  profile.value = {
    scale_level: '',
    consume_level: '',
    industry: '',
    is_real_estate: false,
    description: '',
  }
}

const toggleKeyCustomer = async () => {
  try {
    await customerApi.updateCustomer(Number(route.params.id), {
      is_key_customer: !customer.value.is_key_customer,
    })
    customer.value.is_key_customer = !customer.value.is_key_customer
    Message.success('更新成功')
  } catch (err: any) {
    Message.error(err.message || '操作失败')
  }
}

const handleEdit = () => {
  // TODO: 打开编辑弹窗
  Message.info('编辑功能开发中')
}

const handleBack = () => {
  router.back()
}

const getSettlementCycleText = (cycle?: string) => {
  const map: Record<string, string> = {
    monthly: '月度',
    quarterly: '季度',
    yearly: '年度',
  }
  return cycle ? map[cycle] || '-' : '-'
}

const formatDate = (date?: string) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.customer-detail {
  padding: 20px;
}
</style>
