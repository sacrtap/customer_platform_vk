# PRD: 包年结算规则优化 — 设备类型和楼层类型字段可选化

## 背景

当前计费规则弹框中，无论选择哪种计费类型（定价/阶梯/包年），都强制要求填写设备类型和楼层类型。但包年结算模式只与**套餐类型**和**时间**有关，与设备/楼层无关。

## 目标

当计费类型为包年结算时，隐藏设备类型和楼层类型字段，后端允许这两个字段为 NULL。

## 约束

- 定价结算和阶梯结算的行为不变，仍然必须选择设备类型和楼层类型
- 已有的包年结算规则数据（如果有）保持兼容
- 冲突检查逻辑需要适配：包年结算的冲突维度是 `customer_id + pricing_type + 有效期`，不涉及 device_type/layer_type

## 验收标准

### AC-1: 前端表单条件渲染
- 当 `pricing_type === 'package'` 时，设备类型和楼层类型字段不显示
- 当 `pricing_type` 从 `package` 切换到其他类型时，设备类型恢复默认值 `L`，楼层类型恢复默认值 `single_and_multi`
- 包年结算时只显示：客户、计费类型、套餐类型、生效日期、失效日期

### AC-2: 前端提交逻辑
- 包年结算提交时，`submitData` 不包含 `device_type` 和 `layer_type` 字段
- 包年结算的冲突检查不传 `device_type` 和 `layer_type`
- 创建成功提示不再显示"已生成单层+多层两条规则"

### AC-3: 后端模型
- `PricingRule.device_type` 改为 `nullable=True`
- 数据库迁移脚本：`ALTER TABLE pricing_rules ALTER COLUMN device_type DROP NOT NULL`

### AC-4: 后端服务验证
- `create_pricing_rule`: 当 `pricing_type == 'package'` 时，不要求 `device_type`，不执行 `single_and_multi` 拆分逻辑
- `create_pricing_rule`: 当 `pricing_type != 'package'` 时，`device_type` 仍然必填
- `_check_overlap` / `_check_single_overlap`: 当 `device_type` 为 None 时，冲突条件使用 `device_type IS NULL` 匹配
- `check_pricing_rule_conflict`: 同上适配
- `update_pricing_rule`: 包年规则更新时，允许不传 device_type

### AC-5: 后端路由
- 冲突检查端点：`device_type` 参数改为可选
- 创建/更新端点：包年结算时不校验 device_type

### AC-6: 前端列表展示
- 包年结算规则在列表中设备类型列显示为"—"或"不限"
- 设备类型筛选不影响包年规则的展示

### AC-7: 编辑兼容
- 编辑已有的包年规则时，正确识别 pricing_type 为 package，不显示设备/楼层字段
- 编辑已有的老数据（有 device_type 的包年规则），正常回显并允许保存

## 影响范围

| 层 | 文件 | 改动 |
|---|---|---|
| DB Model | `backend/app/models/billing.py` | `device_type` nullable=True |
| DB Migration | 新增迁移脚本 | ALTER COLUMN |
| Service | `backend/app/services/billing.py` | PricingService 条件验证 |
| Route | `backend/app/routes/billing/pricing.py` | 冲突检查端点参数可选 |
| API Type | `frontend/src/api/billing.ts` | `device_type` 改为可选 |
| Modal | `frontend/src/views/billing/components/PricingRuleModal.vue` | 条件渲染 + 提交逻辑 |
| List | `frontend/src/views/billing/PricingRules.vue` | 列表展示适配 |
