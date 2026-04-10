import api from './index'

// ========== 角色管理 ==========

export interface Permission {
  id: number
  code: string
  name: string
  description?: string
  module?: string
}

export interface Role {
  id: number
  name: string
  description?: string
  isSystem?: boolean
  permissions?: Permission[]
  createdAt?: string
  updatedAt?: string
}

export interface RoleListParams {
  page?: number
  page_size?: number
  keyword?: string
}

export interface RoleListResponse {
  list: Role[]
  total: number
  page: number
  page_size: number
}

/**
 * 获取角色列表（带分页）
 * @param params - 查询参数
 */
export function getRoles(params?: RoleListParams) {
  return api.get<RoleListResponse>('/roles', { params })
}

/**
 * 获取角色详情
 * @param id - 角色 ID
 */
export function getRole(id: number) {
  return api.get<Role>(`/roles/${id}`)
}

/**
 * 创建角色
 * @param data - 角色数据
 */
export function createRole(data: {
  name: string
  description?: string
  permission_ids?: number[]
}) {
  return api.post('/roles', data)
}

/**
 * 更新角色
 * @param id - 角色 ID
 * @param data - 角色数据
 */
export function updateRole(
  id: number,
  data: {
    name?: string
    description?: string
    permission_ids?: number[]
  }
) {
  return api.put(`/roles/${id}`, data)
}

/**
 * 删除角色
 * @param id - 角色 ID
 */
export function deleteRole(id: number) {
  return api.delete(`/roles/${id}`)
}

// ========== 权限管理 ==========

/**
 * 获取角色权限
 * @param id - 角色 ID
 */
export function getRolePermissions(id: number) {
  return api.get<Role>(`/roles/${id}`).then((res) => res.data.permissions)
}

/**
 * 更新角色权限
 * @param id - 角色 ID
 * @param permissionIds - 权限 ID 列表
 */
export function updateRolePermissions(id: number, permissionIds: number[]) {
  return api.post(`/roles/${id}/permissions`, { permission_ids: permissionIds })
}

// ========== 权限列表 ==========

/**
 * 获取所有可用权限
 */
export function getPermissions() {
  return api.get<Permission[]>('/permissions')
}
