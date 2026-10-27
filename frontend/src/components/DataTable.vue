<template>
  <div class="table-section">
    <a-table
      v-bind="tableBindings"
      :columns="visibleColumns"
      :data="data"
      :loading="loading"
      :pagination="pagination"
      :row-selection="rowSelection"
      :row-class="rowClass"
      :scroll="scroll"
      :row-key="rowKey"
    >
      <template v-for="(_, name) in $slots" #[name]="slotData">
        <slot :name="name" v-bind="slotData ?? {}" />
      </template>
      <template #empty>
        <slot name="empty" />
      </template>
      <!-- 操作列标题：列设置入口（storageKey 存在且未显式关闭时显示） -->
      <template #action-title="{ column }">
        <span class="action-title">
          <span>{{ column.title }}</span>
          <button
            v-if="canUseColumnSetting && $slots.action"
            class="th-icon-btn"
            title="列设置"
            @click.stop="columnSettingVisible = true"
          >
            <IconSettings :size="14" />
          </button>
        </span>
      </template>
    </a-table>

    <!-- 列设置弹窗（复用现有通用组件） -->
    <ColumnSettingModal
      v-if="canUseColumnSetting"
      v-model:visible="columnSettingVisible"
      :columns="columnSettingOptions"
      :model-value="visibleColumnKeys"
      @update:model-value="updateVisibleColumns"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, getCurrentInstance, ref, useAttrs, watch } from 'vue'
import ColumnSettingModal from '@/views/customers/components/ColumnSettingModal.vue'
import { IconSettings } from '@arco-design/web-vue/es/icon'

export interface DataTableColumn {
  /** 列标识，同时作为 dataIndex 与列设置 key */
  key: string
  title: string
  /** 缺省取 key */
  dataIndex?: string
  /** 自定义渲染 slot 名，缺省取 key */
  slotName?: string
  width?: number
  fixed?: 'left' | 'right'
  sortable?: { sortDirections?: ('ascend' | 'descend')[] }
  align?: 'left' | 'center' | 'right'
  ellipsis?: boolean
  tooltip?: boolean
  /** 列设置默认勾选；缺省 true */
  defaultVisible?: boolean
}

interface Props {
  columns: DataTableColumn[]
  data: Record<string, unknown>[]
  rowKey?: string
  loading?: boolean
  pagination?: Record<string, unknown> | boolean
  rowSelection?: Record<string, unknown>
  rowClass?: string | ((record: Record<string, unknown>) => string)
  scroll?: { x?: number; y?: number }
  /** 列设置持久化 key；不传则不启用列设置 */
  storageKey?: string
  /** 缺省 true；为 false 时即使传 storageKey 也不显示入口 */
  enableColumnSetting?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  rowKey: 'id',
  loading: false,
  enableColumnSetting: true,
})

// 显式声明事件：给父组件提供类型推断（@row-click 等在 IDE 有提示）。
// 注意：defineEmits 会把对应监听器从 $attrs 剔除，因此不能只靠 v-bind="$attrs" 透传；
// 下面从 vnode.props 取原始监听器，手动转发给 a-table。
defineEmits<{
  (e: 'page-change', page: number): void
  (e: 'page-size-change', pageSize: number): void
  (e: 'sorter-change', dataIndex: string, direction: string): void
  (e: 'change', ...args: unknown[]): void
  (e: 'row-click', record: Record<string, unknown>, ev: Event): void
  (e: 'select', rowKeys: unknown[], rowKey: unknown, record: unknown): void
  (e: 'select-all', checked: boolean): void
}>()

// 原始监听器（onXxx）：defineEmits 后 $attrs 不再包含，需从 vnode.props 提取。
// 用函数而非 computed：vnode.props 在挂载后才填充，computed 会在 setup 时点缓存空对象。
const instance = getCurrentInstance()!
const rawListeners = () => {
  const props = (instance.vnode.props ?? {}) as Record<string, unknown>
  const listeners: Record<string, unknown> = {}
  for (const key of Object.keys(props)) {
    if (key.startsWith('on')) listeners[key] = props[key]
  }
  return listeners
}

// 合并 $attrs 与原始监听器：v-bind 接受对象，属性变化可被模板响应式追踪
// （v-on="obj" 的 obj 在编译期固化，动态修改不生效）。
const attrs = useAttrs()
const tableBindings = computed(() => ({
  ...attrs,
  ...rawListeners(),
}))

// --- 列设置 ---
const columnSettingVisible = ref(false)

// 是否显示列设置入口：storageKey 存在 + 未显式关闭 + 调用方提供了 action slot。
// 不用 useSlots() 做 computed 依赖（其返回对象非响应式，挂载时点求值会缓存 false），
// 改为模板中每次渲染直接判定。
const canUseColumnSetting = computed(() => Boolean(props.storageKey) && props.enableColumnSetting)

// 初始可见列：优先读 localStorage 存量配置，否则取 defaultVisible!==false
const visibleColumnKeys = ref<string[]>(loadColumnConfig())

function loadColumnConfig(): string[] {
  if (props.storageKey) {
    try {
      const saved = localStorage.getItem(props.storageKey)
      if (saved) {
        const parsed: unknown = JSON.parse(saved)
        if (Array.isArray(parsed)) {
          const keys = parsed.filter((k): k is string => typeof k === 'string')
          // 兜底：与 columns 交集为空时回退到默认集（列增删过，避免少显示列）
          const validKeys = new Set(props.columns.map((c) => c.key))
          const filtered = keys.filter((k) => validKeys.has(k))
          if (filtered.length > 0) return filtered
        }
      }
    } catch {
      // ignore
    }
  }
  return props.columns.filter((c) => c.defaultVisible !== false).map((c) => c.key)
}

// 调用方 columns 变化时重载配置（例如切换了 storageKey）
watch(
  () => props.storageKey,
  () => {
    visibleColumnKeys.value = loadColumnConfig()
  }
)

function updateVisibleColumns(keys: string[]) {
  visibleColumnKeys.value = keys
  if (props.storageKey) {
    localStorage.setItem(props.storageKey, JSON.stringify(keys))
  }
}

const columnSettingOptions = computed(() =>
  // action 列强制可见，不放入列设置可勾选列表
  props.columns.filter((c) => c.key !== 'action').map((c) => ({ key: c.key, title: c.title }))
)

// visibleColumns：过滤隐藏列 + 转成 a-table 的列结构
const visibleColumns = computed(() => {
  const keySet = new Set(visibleColumnKeys.value)
  return (
    props.columns
      // action 列是功能列（固定右侧 + 承载列设置入口），不受列可见性控制，
      // 否则存量 localStorage 配置（无 action 键）会把它过滤掉导致操作列丢失
      .filter((c) => c.key === 'action' || keySet.has(c.key))
      .map((c) => ({
        key: c.key,
        title: c.title,
        dataIndex: c.dataIndex ?? c.key,
        // slotName 缺省取 key；action 列同样保留 slotName（arco 经 slotName 找渲染函数）
        slotName: c.slotName ?? c.key,
        // 操作列标题挂列设置入口（静态 slot 名，编译期可确定）
        titleSlotName: c.key === 'action' ? 'action-title' : undefined,
        width: c.width,
        fixed: c.fixed,
        sortable: c.sortable,
        align: c.align,
        ellipsis: c.ellipsis,
        tooltip: c.tooltip,
      }))
  )
})
</script>

<style scoped>
.table-section {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}

/* 表头样式 — 对齐客户管理基准（原 TableSection.vue 覆盖逻辑迁入） */
:deep(.arco-table-th) {
  background-color: var(--table-th-bg, #f8fafc);
  color: var(--table-th-color, #334155);
  font-weight: 600;
  font-size: 12px;
}

/* 紧凑密度：收窄 cell 内边距与字号（Arco 默认 9px 16px / 14px 过于宽松，
   1440 视口下客户表 12 列仅露出 9 列；收窄后同等宽度容纳更多列） */
:deep(.arco-table-th .arco-table-cell),
:deep(.arco-table-td .arco-table-cell) {
  padding: var(--table-cell-padding-y, 5px) var(--table-cell-padding-x, 10px);
  font-size: var(--table-cell-font-size, 13px);
  line-height: var(--table-cell-line-height, 20px);
}

/* 多选列与固定列 cell 同样收窄，避免与数据列密度不一致 */
:deep(.arco-table-th.arco-table-operation .arco-table-cell),
:deep(.arco-table-td.arco-table-operation .arco-table-cell) {
  padding: var(--table-cell-padding-y, 5px) var(--table-cell-padding-x, 10px);
}

:deep(.arco-table-tr:hover .arco-table-td) {
  background-color: var(--table-row-hover, #f8fbff);
}

/* 固定列阴影 — 对齐 BalanceTable 现有视觉 */
:deep(.arco-table-col-fixed-right-first::after) {
  box-shadow: var(--table-fixed-shadow, -8px 0 8px -8px rgba(15, 23, 42, 0.15));
}

/* 行高亮工具类：调用方通过 rowClass 返回类名 */
:deep(.arco-table-tr.row-warning .arco-table-td) {
  background-color: var(--table-row-warning-bg, rgba(220, 38, 38, 0.04));
}
:deep(.arco-table-tr.row-warn .arco-table-td) {
  background-color: var(--table-row-warn-bg, rgba(245, 158, 11, 0.04));
}
/* 多选列（fixed-left）背景：横向滑动时不透出后部内容。
   行高亮用不透明等效色（rgba 半透明叠白底的合成结果），避免 fixed 列透出滚动内容。 */
:deep(.arco-table-th.arco-table-col-fixed-left) {
  background-color: var(--table-th-bg, #f8fafc);
}
:deep(.arco-table-td.arco-table-col-fixed-left) {
  background-color: #fff;
}
:deep(.arco-table-tr:hover .arco-table-td.arco-table-col-fixed-left) {
  background-color: var(--table-row-hover, #f8fbff);
}
:deep(.arco-table-tr.row-warning .arco-table-td.arco-table-col-fixed-left) {
  background-color: #fef6f6;
}
:deep(.arco-table-tr.row-warn .arco-table-td.arco-table-col-fixed-left) {
  background-color: #fefbf5;
}

/* 操作列（fixed-right）背景：与 fixed-left（多选列）方案一致，横向滑动时不透出后部内容。
   行高亮用不透明等效色（rgba 半透明叠白底的合成结果），避免 fixed 列透出滚动内容。 */
:deep(.arco-table-th.arco-table-col-fixed-right) {
  background-color: var(--table-th-bg, #f8fafc);
}
:deep(.arco-table-td.arco-table-col-fixed-right) {
  background-color: #fff;
}
:deep(.arco-table-tr:hover .arco-table-td.arco-table-col-fixed-right) {
  background-color: var(--table-row-hover, #f8fbff);
}
:deep(.arco-table-tr.row-warning .arco-table-td.arco-table-col-fixed-right) {
  background-color: #fef6f6;
}
:deep(.arco-table-tr.row-warn .arco-table-td.arco-table-col-fixed-right) {
  background-color: #fefbf5;
}

/* 操作列标题内的列设置入口 */
.action-title {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.th-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  color: var(--muted);
  padding: 0;
  transition:
    background 0.15s,
    border-color 0.15s,
    color 0.15s;
}
.th-icon-btn:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: var(--primary);
}
</style>
