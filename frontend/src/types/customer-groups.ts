/** 客户群组接口 */
export interface CustomerGroup {
  id: number
  name: string
  description?: string
  group_type: 'dynamic' | 'static'
  filter_conditions?: Record<string, unknown>
  created_at?: string
}

/** 创建群组参数 */
export interface CreateGroupParams {
  name: string
  description?: string
  group_type: 'dynamic' | 'static'
  filter_conditions?: Record<string, unknown> | null
}

/** 群组成员接口 */
export interface GroupMember {
  id: number
  name: string
  company_id: string | number
}

/** 群组统计接口 */
export interface GroupStats {
  total_members: number
  group_type: 'dynamic' | 'static'
  [key: string]: unknown
}
