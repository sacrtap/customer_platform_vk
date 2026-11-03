# 修复 VR 创建弹框明细文件上传双缺陷（含同构场景）

## Goal

VR 结算单创建弹框选择结算明细文件后：上传失败只显示统一文案（真实原因不可见）、移除已选文件按钮无效。break-loop 系统性排查发现减免编辑/提交弹窗存在完全同构的缺陷，一并修复。

## Root Cause

1. `handleFileChange` 的 `if (list.length > 0)` 守卫：Arco 移除时回传空数组被忽略 → 条目残留、移除无效
2. 上传 catch 吞错误：`catch { Message.error('附件上传失败') }` 丢弃后端真实错误（无权限/大小超限/类型不符）

## Requirements

- R1 受控 file-list 的 change 无条件同步（空数组 = 移除语义）
- R2 上传失败走 handleError(error, fallback) 透传后端文案
- R3 同构场景（DiscountEditModal / SubmitModal）同步修复
- R4 回归测试：移除清空 / 失败透传 / 成功路径三态

## 验收边界

- 改动：VrSettlementCreateModal.vue、DiscountEditModal.vue、SubmitModal.vue、新增 VrSettlementCreateModal.upload.test.ts（3 例）
- 验证：组件测试 3 passed；vitest 全量、vue-tsc、prettier 通过；浏览器冒烟（真实 xlsx：选择→移除→重选，移除后 count=0）；后端 /files/upload 直连同文件成功（排除服务端因素）
- spec 沉淀：受控 file-list 与上传错误处理契约（component-guidelines.md）
- 提交：6795a91（VR 弹框）+ 4c7be37（同构修复）+ 0af2b9e（spec）
