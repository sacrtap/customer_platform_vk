# 计费规则有效期重叠校验优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复计费规则创建/更新时的有效期重叠校验 bug，并新增前端预校验能力。

**Architecture:** 提取统一的 `_check_overlap` 私有方法供创建和更新共用；新增 `check_pricing_rule_conflict` 公开方法供 API 调用；前端在提交前调用冲突检查接口提前拦截。

**Tech Stack:** Python 3.12 + SQLAlchemy 2.0 + Sanic + Vue 3 + TypeScript + Arco Design

---

## File Structure

| 文件 | 职责 |
|------|------|
| `backend/app/services/billing.py` | 核心改动：提取 `_check_overlap`，修复 create，增强 update，新增 `check_pricing_rule_conflict` |
| `backend/app/routes/billing.py` | 新增 `GET /pricing-rules/check-conflict` 路由 |
| `frontend/src/api/billing.ts` | 新增 `checkPricingRuleConflict` API 方法和类型定义 |
| `frontend/src/views/billing/PricingRules.vue` | 修改 `handleSubmit` 增加提交前预校验 |
| `backend/tests/test_billing_service.py` | 新增单元测试：重叠校验、layer_type NULL、更新校验 |
| `backend/tests/integration/test_billing_api.py` | 新增集成测试：check-conflict API |

---

### Task 1: 提取 `_check_overlap` 统一校验方法

**Files:**
- Modify: `backend/app/services/billing.py` (PricingService 类)
- Test: `backend/tests/test_billing_service.py`

- [ ] **Step 1: 编写测试用例 — `_check_overlap` 核心逻辑**

在 `backend/tests/test_billing_service.py` 中新增测试类：

```python
class TestPricingService_CheckOverlap:
    """PricingService._check_overlap 测试"""

    @pytest.mark.asyncio
    async def test_overlap_same_layer_type(self, pricing_service):
        """测试相同 layer_type 时检测到重叠"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([existing_rule]),
        ]

        with pytest.raises(ValueError, match="有效期存在重叠"):
            await service._check_overlap(
                customer_id=100,
                device_type="X",
                layer_type="single",
                effective_date=date(2026, 6, 1),
                expiry_date=date(2026, 9, 30),
            )

    @pytest.mark.asyncio
    async def test_overlap_layer_type_none(self, pricing_service):
        """测试 layer_type 为 None 时正确匹配"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type=None,
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([existing_rule]),
        ]

        with pytest.raises(ValueError, match="有效期存在重叠"):
            await service._check_overlap(
                customer_id=100,
                device_type="X",
                layer_type=None,
                effective_date=date(2026, 3, 1),
                expiry_date=date(2026, 8, 31),
            )

    @pytest.mark.asyncio
    async def test_no_overlap_different_layer(self, pricing_service):
        """测试不同 layer_type 不冲突"""
        service, mock_db = pricing_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([]),
        ]

        # 不应抛出异常
        await service._check_overlap(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2026, 6, 1),
            expiry_date=date(2026, 9, 30),
        )

    @pytest.mark.asyncio
    async def test_overlap_exclude_self(self, pricing_service):
        """测试 exclude_id 排除自身"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([existing_rule]),
        ]

        # exclude_id=1 应排除自身，不抛出异常
        await service._check_overlap(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2026, 6, 1),
            expiry_date=date(2026, 9, 30),
            exclude_id=1,
        )
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_billing_service.py::TestPricingService_CheckOverlap -v
```

Expected: FAIL — `_check_overlap` 方法不存在

- [ ] **Step 3: 实现 `_check_overlap` 方法**

在 `backend/app/services/billing.py` 的 `PricingService` 类中，在 `create_pricing_rule` 方法之前添加：

```python
    async def _check_overlap(
        self,
        customer_id: int,
        device_type: str,
        layer_type: Optional[str],
        effective_date: date,
        expiry_date: Optional[date],
        exclude_id: Optional[int] = None,
    ) -> None:
        """检查是否存在有效期重叠的规则，存在则抛出 ValueError"""
        # 构建 layer_type 匹配条件（处理 NULL 情况）
        if layer_type is None:
            layer_condition = PricingRule.layer_type.is_(None)
        else:
            layer_condition = PricingRule.layer_type == layer_type

        conflict_stmt = select(PricingRule).where(
            PricingRule.customer_id == customer_id,
            PricingRule.device_type == device_type,
            layer_condition,
            PricingRule.deleted_at.is_(None),
        )

        if exclude_id is not None:
            conflict_stmt = conflict_stmt.where(PricingRule.id != exclude_id)

        result = await self.db.execute(conflict_stmt)
        existing_rules = result.scalars().all()

        for rule in existing_rules:
            rule_expiry = rule.expiry_date
            new_expiry = expiry_date

            # 检查有效期是否有交集
            if rule_expiry is None or new_expiry is None:
                if rule_expiry is None and new_expiry is None:
                    raise ValueError(
                        "该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠"
                    )
                elif rule_expiry is None:
                    if new_expiry >= rule.effective_date:
                        raise ValueError(
                            "该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠"
                        )
                else:
                    if effective_date <= rule_expiry:
                        raise ValueError(
                            "该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠"
                        )
            else:
                if effective_date <= rule_expiry and new_expiry >= rule.effective_date:
                    raise ValueError(
                        "该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠"
                    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_billing_service.py::TestPricingService_CheckOverlap -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/billing.py backend/tests/test_billing_service.py
git commit -m "feat(billing): 提取 _check_overlap 统一校验方法并处理 layer_type NULL"
```

---

### Task 2: 重构 `create_pricing_rule` 使用 `_check_overlap`

**Files:**
- Modify: `backend/app/services/billing.py` (create_pricing_rule 方法)

- [ ] **Step 1: 修改 `create_pricing_rule` 方法**

将 `create_pricing_rule` 中的重叠校验逻辑替换为调用 `_check_overlap`：

```python
    async def create_pricing_rule(self, data: Dict[str, Any]) -> PricingRule:
        """创建定价规则"""
        customer_id = data.get("customer_id")
        device_type = data["device_type"]
        layer_type = data.get("layer_type")
        effective_date = data["effective_date"]
        expiry_date = data.get("expiry_date")

        # 使用统一的校验方法
        await self._check_overlap(
            customer_id=customer_id,
            device_type=device_type,
            layer_type=layer_type,
            effective_date=effective_date,
            expiry_date=expiry_date,
        )

        rule = PricingRule(
            customer_id=data.get("customer_id"),
            device_type=data["device_type"],
            layer_type=data.get("layer_type"),
            pricing_type=data["pricing_type"],
            unit_price=data.get("unit_price"),
            tiers=data.get("tiers"),
            package_type=data.get("package_type"),
            package_limits=data.get("package_limits"),
            effective_date=data["effective_date"],
            expiry_date=data.get("expiry_date"),
            created_by=data.get("created_by"),
        )
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule
```

- [ ] **Step 2: 运行现有测试确认未破坏**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_billing_service.py::TestPricingService_Create -v
```

Expected: All existing tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/billing.py
git commit -m "refactor(billing): create_pricing_rule 使用 _check_overlap 统一校验"
```

---

### Task 3: `update_pricing_rule` 增加重叠校验

**Files:**
- Modify: `backend/app/services/billing.py` (update_pricing_rule 方法)
- Test: `backend/tests/test_billing_service.py`

- [ ] **Step 1: 编写测试用例 — 更新操作的重叠校验**

在 `backend/tests/test_billing_service.py` 中新增：

```python
class TestPricingService_UpdateOverlap:
    """PricingService.update_pricing_rule 重叠校验测试"""

    @pytest.mark.asyncio
    async def test_update_causes_overlap(self, pricing_service):
        """测试更新导致重叠时抛出异常"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        # 当前规则
        current_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 6, 30),
        )

        # 已存在的另一条规则（与更新后的日期重叠）
        other_rule = PricingRule(
            id=2,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="tier",
            effective_date=date(2026, 7, 1),
            expiry_date=date(2026, 12, 31),
        )

        mock_db.execute.side_effect = [
            make_mock_execute_result([current_rule]),  # 查找当前规则
            make_mock_execute_result([other_rule]),     # 查找冲突规则
        ]

        with pytest.raises(ValueError, match="有效期存在重叠"):
            await service.update_pricing_rule(1, {
                "effective_date": date(2026, 8, 1),
                "expiry_date": date(2026, 10, 31),
            })

    @pytest.mark.asyncio
    async def test_update_no_overlap(self, pricing_service):
        """测试更新不导致重叠时成功"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        current_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 6, 30),
        )

        mock_db.execute.side_effect = [
            make_mock_execute_result([current_rule]),  # 查找当前规则
            make_mock_execute_result([]),               # 无冲突规则
        ]

        result = await service.update_pricing_rule(1, {
            "effective_date": date(2026, 7, 1),
            "expiry_date": date(2026, 12, 31),
        })

        assert result is not None
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_update_non_date_fields_skip_check(self, pricing_service):
        """测试仅更新非日期字段时跳过校验"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        current_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            unit_price=Decimal("10.00"),
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )

        mock_db.execute.return_value = make_mock_execute_result([current_rule])

        result = await service.update_pricing_rule(1, {
            "unit_price": Decimal("15.00"),
        })

        assert result is not None
        # 只执行了一次查询（查找当前规则），没有冲突检查
        assert mock_db.execute.call_count == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_billing_service.py::TestPricingService_UpdateOverlap -v
```

Expected: FAIL — 更新操作尚无重叠校验

- [ ] **Step 3: 修改 `update_pricing_rule` 方法**

将现有的 `update_pricing_rule` 方法替换为：

```python
    async def update_pricing_rule(
        self, rule_id: int, data: Dict[str, Any]
    ) -> Optional[PricingRule]:
        """更新定价规则"""
        result = await self.db.execute(
            select(PricingRule).where(PricingRule.id == rule_id, PricingRule.deleted_at.is_(None))
        )
        rule = result.scalar_one_or_none()

        if not rule:
            return None

        # 检查是否需要重叠校验
        overlap_fields = {"effective_date", "expiry_date", "customer_id", "device_type", "layer_type"}
        needs_overlap_check = any(f in data for f in overlap_fields)

        if needs_overlap_check:
            # 使用修改后的值（如果提供了）或原始值
            check_customer_id = data.get("customer_id", rule.customer_id)
            check_device_type = data.get("device_type", rule.device_type)
            check_layer_type = data.get("layer_type", rule.layer_type)
            check_effective_date = data.get("effective_date", rule.effective_date)
            check_expiry_date = data.get("expiry_date", rule.expiry_date)

            await self._check_overlap(
                customer_id=check_customer_id,
                device_type=check_device_type,
                layer_type=check_layer_type,
                effective_date=check_effective_date,
                expiry_date=check_expiry_date,
                exclude_id=rule_id,
            )

        # 可更新字段
        updatable = [
            "device_type",
            "layer_type",
            "pricing_type",
            "unit_price",
            "tiers",
            "package_type",
            "package_limits",
            "effective_date",
            "expiry_date",
        ]

        for field in updatable:
            if field in data:
                setattr(rule, field, data[field])

        await self.db.commit()
        await self.db.refresh(rule)

        return rule
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_billing_service.py::TestPricingService_UpdateOverlap -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: 运行所有 billing 测试确认未破坏**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_billing_service.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/billing.py backend/tests/test_billing_service.py
git commit -m "feat(billing): update_pricing_rule 增加有效期重叠校验"
```

---

### Task 4: 新增 `check_pricing_rule_conflict` 服务方法

**Files:**
- Modify: `backend/app/services/billing.py` (PricingService 类)
- Test: `backend/tests/test_billing_service.py`

- [ ] **Step 1: 编写测试用例**

在 `backend/tests/test_billing_service.py` 中新增：

```python
class TestPricingService_CheckConflict:
    """PricingService.check_pricing_rule_conflict 测试"""

    @pytest.mark.asyncio
    async def test_has_conflict(self, pricing_service):
        """测试存在冲突时返回冲突列表"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        conflicting_rule = PricingRule(
            id=5,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([conflicting_rule]),
        ]

        result = await service.check_pricing_rule_conflict(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2026, 6, 1),
            expiry_date=date(2026, 9, 30),
        )

        assert len(result) == 1
        assert result[0].id == 5

    @pytest.mark.asyncio
    async def test_no_conflict(self, pricing_service):
        """测试无冲突时返回空列表"""
        service, mock_db = pricing_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([]),
        ]

        result = await service.check_pricing_rule_conflict(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2027, 1, 1),
            expiry_date=date(2027, 12, 31),
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_exclude_self(self, pricing_service):
        """测试 exclude_id 排除自身"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        self_rule = PricingRule(
            id=10,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([self_rule]),
        ]

        result = await service.check_pricing_rule_conflict(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2026, 6, 1),
            expiry_date=date(2026, 9, 30),
            exclude_id=10,
        )

        # 排除自身后应无冲突
        assert len(result) == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_billing_service.py::TestPricingService_CheckConflict -v
```

Expected: FAIL — 方法不存在

- [ ] **Step 3: 实现方法**

在 `PricingService` 类中添加：

```python
    async def check_pricing_rule_conflict(
        self,
        customer_id: int,
        device_type: str,
        layer_type: Optional[str],
        effective_date: date,
        expiry_date: Optional[date],
        exclude_id: Optional[int] = None,
    ) -> List[PricingRule]:
        """查询与给定条件存在有效期重叠的规则，返回冲突列表"""
        # 构建 layer_type 匹配条件（处理 NULL 情况）
        if layer_type is None:
            layer_condition = PricingRule.layer_type.is_(None)
        else:
            layer_condition = PricingRule.layer_type == layer_type

        conflict_stmt = select(PricingRule).where(
            PricingRule.customer_id == customer_id,
            PricingRule.device_type == device_type,
            layer_condition,
            PricingRule.deleted_at.is_(None),
        )

        if exclude_id is not None:
            conflict_stmt = conflict_stmt.where(PricingRule.id != exclude_id)

        result = await self.db.execute(conflict_stmt)
        existing_rules = result.scalars().all()

        conflicting = []
        for rule in existing_rules:
            rule_expiry = rule.expiry_date
            new_expiry = expiry_date

            if rule_expiry is None or new_expiry is None:
                if rule_expiry is None and new_expiry is None:
                    conflicting.append(rule)
                elif rule_expiry is None:
                    if new_expiry >= rule.effective_date:
                        conflicting.append(rule)
                else:
                    if effective_date <= rule_expiry:
                        conflicting.append(rule)
            else:
                if effective_date <= rule_expiry and new_expiry >= rule.effective_date:
                    conflicting.append(rule)

        return conflicting
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_billing_service.py::TestPricingService_CheckConflict -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/billing.py backend/tests/test_billing_service.py
git commit -m "feat(billing): 新增 check_pricing_rule_conflict 方法供 API 调用"
```

---

### Task 5: 新增冲突检查 API 路由

**Files:**
- Modify: `backend/app/routes/billing.py`
- Test: `backend/tests/integration/test_billing_api.py`

- [ ] **Step 1: 编写集成测试**

在 `backend/tests/integration/test_billing_api.py` 中新增：

```python
@pytest.mark.asyncio
async def test_check_pricing_rule_conflict_has_conflict(test_client, auth_token):
    """测试冲突检查 API — 有冲突"""
    # 先创建一条规则
    await test_client.post(
        "/api/v1/billing/pricing-rules",
        json={
            "customer_id": 1,
            "device_type": "X",
            "layer_type": "single",
            "pricing_type": "fixed",
            "unit_price": 10.0,
            "effective_date": "2026-01-01",
            "expiry_date": "2026-12-31",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    # 检查冲突
    response = await test_client.get(
        "/api/v1/billing/pricing-rules/check-conflict",
        params={
            "customer_id": 1,
            "device_type": "X",
            "layer_type": "single",
            "effective_date": "2026-06-01",
            "expiry_date": "2026-09-30",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["has_conflict"] is True
    assert len(data["data"]["conflicting_rules"]) > 0


@pytest.mark.asyncio
async def test_check_pricing_rule_conflict_no_conflict(test_client, auth_token):
    """测试冲突检查 API — 无冲突"""
    response = await test_client.get(
        "/api/v1/billing/pricing-rules/check-conflict",
        params={
            "customer_id": 1,
            "device_type": "X",
            "layer_type": "single",
            "effective_date": "2027-01-01",
            "expiry_date": "2027-12-31",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["has_conflict"] is False
    assert len(data["data"]["conflicting_rules"]) == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/integration/test_billing_api.py::test_check_pricing_rule_conflict_has_conflict -v
```

Expected: FAIL — 路由不存在

- [ ] **Step 3: 新增路由**

在 `backend/app/routes/billing.py` 中，在 `get_pricing_rules` 路由之后（约第 375 行之后）添加：

```python
@billing_bp.get("/pricing-rules/check-conflict")
@auth_required
async def check_pricing_rule_conflict(request: Request):
    """
    检查定价规则有效期冲突

    Query params:
    - customer_id (必填, int)
    - device_type (必填, string)
    - layer_type (必填, string)
    - effective_date (必填, date)
    - expiry_date (可选, date)
    - exclude_id (可选, int) — 编辑时排除自身
    """
    db: AsyncSession = request.ctx.db_session

    # 参数校验
    try:
        customer_id = int(request.args.get("customer_id", 0))
        device_type = request.args.get("device_type", "")
        layer_type = request.args.get("layer_type")
        effective_date_str = request.args.get("effective_date", "")
        expiry_date_str = request.args.get("expiry_date")
        exclude_id_str = request.args.get("exclude_id")

        if not customer_id or not device_type or not effective_date_str:
            return json({
                "code": 40001,
                "message": "缺少必填参数：customer_id, device_type, effective_date",
            }, status=400)

        effective_date = date.fromisoformat(effective_date_str)
        expiry_date = date.fromisoformat(expiry_date_str) if expiry_date_str else None
        exclude_id = int(exclude_id_str) if exclude_id_str else None
    except (ValueError, TypeError):
        return json({
            "code": 40001,
            "message": "参数格式错误",
        }, status=400)

    pricing_service = PricingService(db)

    conflicting_rules = await pricing_service.check_pricing_rule_conflict(
        customer_id=customer_id,
        device_type=device_type,
        layer_type=layer_type,
        effective_date=effective_date,
        expiry_date=expiry_date,
        exclude_id=exclude_id,
    )

    return json({
        "code": 0,
        "data": {
            "has_conflict": len(conflicting_rules) > 0,
            "conflicting_rules": [
                {
                    "id": r.id,
                    "pricing_type": r.pricing_type,
                    "effective_date": r.effective_date.isoformat() if r.effective_date else None,
                    "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                }
                for r in conflicting_rules
            ],
        },
    })
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/integration/test_billing_api.py::test_check_pricing_rule_conflict_has_conflict tests/integration/test_billing_api.py::test_check_pricing_rule_conflict_no_conflict -v
```

Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/billing.py backend/tests/integration/test_billing_api.py
git commit -m "feat(billing): 新增 GET /pricing-rules/check-conflict API"
```

---

### Task 6: 前端 — 新增 API 方法

**Files:**
- Create: `frontend/src/api/billing.ts` 新增方法

- [ ] **Step 1: 在 `frontend/src/api/billing.ts` 中添加类型和方法**

在定价规则部分（`deletePricingRule` 之后）添加：

```typescript
export interface ConflictCheckParams {
  customer_id: number
  device_type: string
  layer_type: string
  effective_date: string
  expiry_date?: string
  exclude_id?: number
}

export interface ConflictRule {
  id: number
  pricing_type: string
  effective_date: string | null
  expiry_date: string | null
}

export interface ConflictCheckResult {
  has_conflict: boolean
  conflicting_rules: ConflictRule[]
}

export function checkPricingRuleConflict(params: ConflictCheckParams) {
  return api.get<ConflictCheckResult>('/billing/pricing-rules/check-conflict', { params })
}
```

- [ ] **Step 2: 运行前端类型检查确认通过**

```bash
cd frontend && npm run type-check
```

Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/billing.ts
git commit -m "feat(billing): 新增 checkPricingRuleConflict API 方法"
```

---

### Task 7: 前端 — `handleSubmit` 增加提交前预校验

**Files:**
- Modify: `frontend/src/views/billing/PricingRules.vue`

- [ ] **Step 1: 修改 import 语句**

将：
```typescript
import * as billingApi from '@/api/billing'
```

改为（无需改动，`* as billingApi` 已包含新方法）

- [ ] **Step 2: 修改 `handleSubmit` 方法**

将现有的 `handleSubmit` 方法替换为：

```typescript
const handleSubmit = async () => {
  if (!formData.customer_id) {
    Message.warning('请选择客户')
    return false
  }
  if (!formData.effective_date) {
    Message.warning('请选择生效日期')
    return false
  }

  modalLoading.value = true
  try {
    // 提交前检查冲突
    const conflictRes = await billingApi.checkPricingRuleConflict({
      customer_id: formData.customer_id,
      device_type: formData.device_type,
      layer_type: formData.layer_type,
      effective_date: formData.effective_date,
      expiry_date: formData.expiry_date,
      exclude_id: isEdit.value && formData.id ? formData.id : undefined,
    })

    if (conflictRes.data.has_conflict) {
      const conflictRules = conflictRes.data.conflicting_rules
      const conflictMsg = conflictRules
        .map(
          (r: any) =>
            `规则ID ${r.id}（${r.pricing_type}）：${r.effective_date} ~ ${r.expiry_date || '永久'}`
        )
        .join('\n')
      Message.error({
        content: `有效期冲突，已存在以下规则：\n${conflictMsg}`,
        duration: 5000,
      })
      return false
    }

    const data: Partial<PricingRule> = {
      customer_id: formData.customer_id,
      device_type: formData.device_type,
      layer_type: formData.layer_type,
      pricing_type: formData.pricing_type,
      effective_date: formData.effective_date,
      expiry_date: formData.expiry_date,
    }

    if (formData.pricing_type === 'fixed' && formData.unit_price) {
      data.unit_price = formData.unit_price
    } else if (formData.pricing_type === 'tiered') {
      if (formData.tiersJson) {
        try {
          data.tiers = JSON.parse(formData.tiersJson)
        } catch (e) {
          Message.error('阶梯配置 JSON 格式不正确')
          modalLoading.value = false
          return false
        }
      }
    } else if (formData.pricing_type === 'package' && formData.package_type) {
      data.package_type = formData.package_type
    }

    if (isEdit.value && formData.id) {
      await billingApi.updatePricingRule(formData.id, data)
      Message.success('更新成功')
    } else {
      await billingApi.createPricingRule(data)
      Message.success('创建成功')
    }
    fetchData()
    return true
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '操作失败')
    return false
  } finally {
    modalLoading.value = false
  }
}
```

- [ ] **Step 3: 运行前端类型检查确认通过**

```bash
cd frontend && npm run type-check
```

Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/billing/PricingRules.vue
git commit -m "feat(billing): 前端提交前增加冲突预校验"
```

---

### Task 8: 全量测试验证

- [ ] **Step 1: 运行后端所有测试**

```bash
cd backend && make test
```

Expected: All tests PASS

- [ ] **Step 2: 运行后端测试覆盖率检查**

```bash
cd backend && make test-cov
```

Expected: Coverage ≥ 50%

- [ ] **Step 3: 运行前端测试**

```bash
cd frontend && npm run type-check && npm run lint
```

Expected: No errors

- [ ] **Step 4: 最终 Commit**

```bash
git commit --allow-empty -m "chore: 计费规则有效期重叠校验优化完成"
```
