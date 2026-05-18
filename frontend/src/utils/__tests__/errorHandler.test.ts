import { describe, it, expect } from 'vitest'
import {
  getErrorCategory,
  getUserFriendlyMessage,
  ErrorCategory,
} from '../errorHandler'

describe('getErrorCategory', () => {
  it('should return SUCCESS for code 0', () => {
    expect(getErrorCategory(0)).toBe(ErrorCategory.SUCCESS)
  })

  it('should return CLIENT_ERROR for 4xxxx codes', () => {
    expect(getErrorCategory(40001)).toBe(ErrorCategory.CLIENT_ERROR)
    expect(getErrorCategory(40002)).toBe(ErrorCategory.CLIENT_ERROR)
  })

  it('should return AUTH_ERROR for 401xx codes', () => {
    expect(getErrorCategory(40101)).toBe(ErrorCategory.AUTH_ERROR)
    expect(getErrorCategory(40102)).toBe(ErrorCategory.AUTH_ERROR)
  })

  it('should return FORBIDDEN_ERROR for 403xx codes', () => {
    expect(getErrorCategory(40301)).toBe(ErrorCategory.FORBIDDEN_ERROR)
  })

  it('should return NOT_FOUND_ERROR for 404xx codes', () => {
    expect(getErrorCategory(40401)).toBe(ErrorCategory.NOT_FOUND_ERROR)
  })

  it('should return SERVER_ERROR for 5xxxx codes', () => {
    expect(getErrorCategory(50000)).toBe(ErrorCategory.SERVER_ERROR)
    expect(getErrorCategory(50001)).toBe(ErrorCategory.SERVER_ERROR)
  })

  it('should return SERVER_ERROR for unknown codes', () => {
    expect(getErrorCategory(99999)).toBe(ErrorCategory.SERVER_ERROR)
  })
})

describe('getUserFriendlyMessage', () => {
  it('should return backend message for CLIENT_ERROR', () => {
    const msg = getUserFriendlyMessage(40001, '参数不能为空')
    expect(msg).toBe('参数不能为空')
  })

  it('should return default message for CLIENT_ERROR without backend message', () => {
    const msg = getUserFriendlyMessage(40001, '')
    expect(msg).toBe('请求参数有误，请检查后重试')
  })

  it('should return fixed message for AUTH_ERROR', () => {
    const msg = getUserFriendlyMessage(40101, 'Token 无效')
    expect(msg).toBe('登录已过期，请重新登录')
  })

  it('should return fixed message for FORBIDDEN_ERROR', () => {
    const msg = getUserFriendlyMessage(40301, '权限不足')
    expect(msg).toBe('您没有执行此操作的权限')
  })

  it('should return fixed message for NOT_FOUND_ERROR', () => {
    const msg = getUserFriendlyMessage(40401, '用户不存在')
    expect(msg).toBe('请求的资源不存在')
  })

  it('should return fixed message for SERVER_ERROR', () => {
    const msg = getUserFriendlyMessage(50000, '内部错误')
    expect(msg).toBe('系统繁忙，请稍后重试')
  })
})
