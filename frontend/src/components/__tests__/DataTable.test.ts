import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount, enableAutoUnmount } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import { defineComponent, h } from 'vue'
import DataTable from '@/components/DataTable.vue'

// Arco 组件（Tooltip 等）在 jsdom 销毁后可能残留 requestAnimationFrame，
// 统一挂载插件 + 自动卸载，避免「Cannot read properties of null」未处理异常
enableAutoUnmount(afterEach)

const columns = [
  { key: 'name', title: '名称' },
  {
    key: 'age',
    title: '年龄',
    sortable: { sortDirections: ['ascend', 'descend'] as ('ascend' | 'descend')[] },
  },
  { key: 'remark', title: '备注', defaultVisible: false },
  {
    key: 'action',
    title: '操作',
    fixed: 'right' as const,
    width: 200,
    slotName: 'action',
  },
]

const data = [
  { id: 1, name: '张三', age: 30 },
  { id: 2, name: '李四', age: 25 },
]

const mountTable = (props: Record<string, unknown> = {}, slots: Record<string, string> = {}) =>
  mount(DataTable, {
    props: { columns, data, ...props },
    slots,
    global: { plugins: [ArcoVue] },
  })

describe('DataTable', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('默认列可见性', () => {
    it('默认渲染所有 defaultVisible !== false 的列', () => {
      const wrapper = mountTable()
      const headers = wrapper.findAll('.arco-table-th')
      const titles = headers.map((h) => h.text())
      expect(titles).toContain('名称')
      expect(titles).toContain('年龄')
      // remark 默认隐藏
      expect(titles).not.toContain('备注')
      // 操作列始终渲染
      expect(titles.some((t) => t.includes('操作'))).toBe(true)
    })

    it('defaultVisible 未声明的列默认显示', () => {
      const wrapper = mountTable()
      const titles = wrapper.findAll('.arco-table-th').map((h) => h.text())
      expect(titles).toContain('名称')
      expect(titles).toContain('年龄')
    })
  })

  describe('列设置持久化', () => {
    it('传 storageKey 时从 localStorage 读初始可见列', () => {
      localStorage.setItem('test_table_columns', JSON.stringify(['name', 'action']))
      const wrapper = mountTable({ storageKey: 'test_table_columns' })
      const titles = wrapper.findAll('.arco-table-th').map((h) => h.text())
      expect(titles).toContain('名称')
      expect(titles).not.toContain('年龄')
      expect(titles).not.toContain('备注')
    })

    it('存量配置与 columns 无交集时回退到默认集', () => {
      localStorage.setItem('test_table_columns', JSON.stringify(['deleted_col']))
      const wrapper = mountTable({ storageKey: 'test_table_columns' })
      const titles = wrapper.findAll('.arco-table-th').map((h) => h.text())
      expect(titles).toContain('名称')
      expect(titles).toContain('年龄')
      expect(titles).not.toContain('备注')
    })

    it('存量配置中的无效 key 被忽略', () => {
      localStorage.setItem('test_table_columns', JSON.stringify(['name', 'ghost_col', 'action']))
      const wrapper = mountTable({ storageKey: 'test_table_columns' })
      const titles = wrapper.findAll('.arco-table-th').map((h) => h.text())
      expect(titles).toContain('名称')
      expect(titles).not.toContain('年龄')
    })

    // 回归：老用户的存量 customer_table_columns_config 不含 action 键，
    // 过滤时不能把操作列也滤掉（客户管理页曾因此丢失操作列）
    it('存量配置不含 action 键时操作列仍强制显示', () => {
      localStorage.setItem('test_table_columns', JSON.stringify(['name', 'age']))
      const wrapper = mountTable(
        { storageKey: 'test_table_columns' },
        { action: '<button>编辑</button>' }
      )
      const titles = wrapper.findAll('.arco-table-th').map((h) => h.text())
      expect(titles).toContain('名称')
      expect(titles).toContain('年龄')
      expect(titles).toContain('操作')
      // 操作列 slot 内容实际渲染
      expect(wrapper.html()).toContain('编辑')
    })

    it('action 列不出现在列设置可勾选列表中', async () => {
      const wrapper = mountTable(
        { storageKey: 'test_table_columns' },
        { action: '<button>编辑</button>' }
      )
      await wrapper.find('.th-icon-btn').trigger('click')
      await wrapper.vm.$nextTick()
      const options = [...document.body.querySelectorAll('.arco-modal-body label')].map((l) =>
        l.textContent?.trim()
      )
      expect(options).toContain('名称')
      expect(options).not.toContain('操作')
    })

    it('列设置弹窗确认后写回 localStorage', async () => {
      localStorage.setItem('test_table_columns', JSON.stringify(['name', 'action']))
      const wrapper = mountTable(
        { storageKey: 'test_table_columns' },
        { action: '<button>编辑</button>' }
      )

      // 打开列设置弹窗（Arco Modal teleport 到 body）
      await wrapper.find('.th-icon-btn').trigger('click')
      await wrapper.vm.$nextTick()
      expect(document.body.querySelector('.arco-modal')).not.toBeNull()

      // 模拟弹窗确认：直接调用 model-value 更新（走 ColumnSettingModal 的 @ok 路径）
      const vm = wrapper.vm as unknown as { updateVisibleColumns: (k: string[]) => void }
      vm.updateVisibleColumns(['name', 'age', 'action'])
      await wrapper.vm.$nextTick()

      const saved = JSON.parse(localStorage.getItem('test_table_columns')!)
      expect(saved).toEqual(['name', 'age', 'action'])

      // 表格列随之更新
      const titles = wrapper.findAll('.arco-table-th').map((h) => h.text())
      expect(titles).toContain('年龄')
    })

    it('不传 storageKey 时不渲染列设置入口', () => {
      const wrapper = mountTable({}, { action: '<button>编辑</button>' })
      expect(wrapper.find('.th-icon-btn').exists()).toBe(false)
    })

    it('enableColumnSetting=false 时不渲染列设置入口', () => {
      const wrapper = mountTable(
        { storageKey: 'test_table_columns', enableColumnSetting: false },
        { action: '<button>编辑</button>' }
      )
      expect(wrapper.find('.th-icon-btn').exists()).toBe(false)
    })
  })

  describe('Slot 透传', () => {
    it('传 #action slot 能在操作列位置渲染', () => {
      const wrapper = mountTable({}, { action: '<button class="edit-btn">编辑</button>' })
      expect(wrapper.find('.edit-btn').exists()).toBe(true)
      expect(wrapper.find('.edit-btn').text()).toBe('编辑')
    })

    it('传 #name slot 能在对应列位置渲染', () => {
      const wrapper = mountTable({}, { name: '<span class="name-cell">自定义</span>' })
      expect(wrapper.find('.name-cell').exists()).toBe(true)
    })

    it('slot 能拿到 record 数据', () => {
      const wrapper = mountTable(
        {},
        {
          name: '<span class="name-cell">{{ params.record.name }}</span>',
        }
      )
      // 每行都渲染 slot
      const cells = wrapper.findAll('.name-cell')
      expect(cells.length).toBeGreaterThan(0)
      expect(cells[0].text()).toBe('张三')
    })

    it('无 action slot 时不渲染列设置入口', () => {
      const wrapper = mountTable({ storageKey: 'test_table_columns' })
      expect(wrapper.find('.th-icon-btn').exists()).toBe(false)
    })
  })

  describe('固定列', () => {
    it('fixed:right 列出现在末尾且带固定样式类', () => {
      const wrapper = mountTable()
      const ths = wrapper.findAll('.arco-table-th')
      const lastTh = ths[ths.length - 1]
      expect(lastTh.text()).toContain('操作')
      expect(lastTh.classes().join(' ')).toContain('fixed')
    })

    it('数据行的固定列单元格存在', () => {
      const wrapper = mountTable()
      const rows = wrapper.findAll('.arco-table-tr')
      expect(rows.length).toBeGreaterThan(0)
    })
  })

  describe('事件透传', () => {
    // 用宿主组件真正挂 @row-click 监听，验证监听器经 attrs 冒泡到 a-table
    const mountHost = () =>
      mount(
        defineComponent({
          components: { DataTable },
          setup() {
            return () =>
              h(DataTable, {
                columns,
                data,
                onRowClick: (record: Record<string, unknown>) => {
                  captured.push(record)
                },
                onPageChange: (page: number) => {
                  capturedPage.push(page)
                },
                onSorterChange: (field: string, dir: string) => {
                  capturedSort.push([field, dir])
                },
              })
          },
        }),
        { global: { plugins: [ArcoVue] } }
      )

    const captured: Record<string, unknown>[] = []
    const capturedPage: number[] = []
    const capturedSort: [string, string][] = []

    it('a-table 的 row-click 冒泡到宿主组件监听器', async () => {
      const wrapper = mountHost()
      const aTable = wrapper.findComponent({ name: 'Table' })
      expect(aTable.exists()).toBe(true)
      aTable.vm.$emit('rowClick', { id: 1, name: '张三' }, new Event('click'))
      await wrapper.vm.$nextTick()
      expect(captured).toEqual([{ id: 1, name: '张三' }])
    })

    it('a-table 的 page-change 冒泡到宿主组件监听器', () => {
      const wrapper = mountHost()
      wrapper.findComponent({ name: 'Table' }).vm.$emit('pageChange', 2)
      expect(capturedPage).toEqual([2])
    })

    it('a-table 的 sorter-change 冒泡到宿主组件监听器', () => {
      const wrapper = mountHost()
      wrapper.findComponent({ name: 'Table' }).vm.$emit('sorterChange', 'name', 'ascend')
      expect(capturedSort).toEqual([['name', 'ascend']])
    })

    it('点击排序列头不报错且表格正常渲染', async () => {
      const wrapper = mountTable()
      const sortableTh = wrapper.findAll('.arco-table-th').find((h) => h.text().includes('年龄'))
      expect(sortableTh).toBeTruthy()
      await sortableTh!.trigger('click')
      await wrapper.vm.$nextTick()
      expect(wrapper.findAll('tbody .arco-table-tr').length).toBe(2)
    })
  })

  describe('其他 props', () => {
    it('loading 状态传递给 a-table', () => {
      const wrapper = mountTable({ loading: true })
      expect(wrapper.find('.arco-spin').classes().join(' ')).toContain('arco-spin-loading')
    })

    it('rowKey 缺省为 id', () => {
      const wrapper = mountTable()
      expect(wrapper.findAll('tbody .arco-table-tr').length).toBe(2)
    })

    it('rowClass 函数返回的类名应用到行上', () => {
      const wrapper = mountTable({
        rowClass: (record: Record<string, unknown>) =>
          (record.age as number) > 28 ? 'row-warning' : '',
      })
      const rows = wrapper.findAll('tbody .arco-table-tr')
      const firstRow = rows.find((r) => r.text().includes('张三'))
      expect(firstRow!.classes()).toContain('row-warning')
      const secondRow = rows.find((r) => r.text().includes('李四'))
      expect(secondRow!.classes()).not.toContain('row-warning')
    })

    it('rowClass 字符串直接应用到所有行上', () => {
      const wrapper = mountTable({ rowClass: 'row-warn' })
      const rows = wrapper.findAll('tbody .arco-table-tr')
      expect(rows[0].classes()).toContain('row-warn')
      expect(rows[1].classes()).toContain('row-warn')
    })

    it('空数据渲染 empty slot', () => {
      const wrapper = mountTable(
        { data: [] },
        { empty: '<div class="custom-empty">暂无数据</div>' }
      )
      expect(wrapper.find('.custom-empty').exists()).toBe(true)
    })
  })
})
