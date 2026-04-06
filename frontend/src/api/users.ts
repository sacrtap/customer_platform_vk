import api from './index'

/** 用户接口类型定义 */
export interface User {
  id: number
  username: string
  email: string
  real_name?: string
  is_active: boolean
  is_system: boolean
  roles?: Array<{ id: number; name: string }>
  created_at: string
}

/** 用户列表请求参数 */
export interface GetUsersParams {
  page?: number
  page_size?: number
  keyword?: string
}

/** 创建用户请求数据 */
export interface CreateUserData {
  username: string
  password: string
  email?: string
  real_name?: string
}

/** 更新用户请求数据 */
export interface UpdateUserData {
  email?: string
  real_name?: string
  is_active?: boolean
}

/** 角色接口类型定义 */
export interface Role {
  id: number
  name: string
  description?: string
}

/**
 * 获取用户列表
 * @param params - 查询参数
 * @returns API 响应
 */
export function getUsers(params?: GetUsersParams) {
  return api.get('/users', { params })
}

/**
 * 获取用户详情
 * @param id - 用户 ID
 * @returns API 响应
 */
export function getUser(id: number) {
  return api.get(`/users/${id}`)
}

/**
 * 创建用户
 * @param data - 用户数据
 * @returns API 响应
 */
export function createUser(data: CreateUserData) {
  return api.post('/users', data)
}

/**
 * 更新用户信息
 * @param id - 用户 ID
 * @param data - 更新数据
 * @returns API 响应
 */
export function updateUser(id: number, data: UpdateUserData) {
  return api.put(`/users/${id}`, data)
}

/**
 * 删除用户
 * @param id - 用户 ID
 * @returns API 响应
 */
export function deleteUser(id: number) {
  return api.delete(`/users/${id}`)
}

/**
 * 获取用户角色
 * @param id - 用户 ID
 * @returns API 响应
 */
export function getUserRoles(id: number) {
  return api.get(`/users/${id}/roles`)
}

/**
 * 为用户分配角色
 * @param id - 用户 ID
 * @param roleIds - 角色 ID 列表
 * @returns API 响应
 */
export function assignUserRoles(id: number, roleIds: number[]) {
  return api.post(`/users/${id}/roles`, { role_ids: roleIds })
}

/**
 * 重置用户密码
 * @param id - 用户 ID
 * @param newPassword - 新密码
 * @returns API 响应
 */
export function resetPassword(id: number, newPassword: string) {
  return api.post(`/users/${id}/reset-password`, { new_password: newPassword })
}

/**
 * 获取运营经理列表（所有活跃用户）
 * @returns API 响应
 */
export function getManagers(params?: { page?: number; page_size?: number }) {
  return api.get('/users', { params: { ...params, page_size: params?.page_size || 100 } })
}
