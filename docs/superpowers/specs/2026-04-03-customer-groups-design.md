# 客户分群功能设计文档

**创建日期**: 2026-04-03  
**状态**: 已批准  
**优先级**: 高

---

## 一、概述

### 1.1 功能定义

客户分群功能允许用户创建和管理客户群组，支持两种类型：

| 类型         | 说明                               | 类比         |
| ------------ | ---------------------------------- | ------------ |
| **动态群组** | 保存筛选条件，成员自动更新         | 智能文件夹   |
| **静态群组** | 手动管理成员列表，成员固定         | 播放列表     |

### 1.2 核心价值

1. **快速筛选**：一键应用常用筛选条件，无需重复配置
2. **批量操作**：支持群组级别的打标签、导出、充值等操作
3. **数据分析**：提供群组维度的消耗统计和对比分析（二期）

### 1.3 用户场景

| 场景               | 群组类型 | 使用频率 |
| ------------------ | -------- | -------- |
| 保存常用筛选条件   | 动态     | 高       |
| 重点客户专项管理   | 静态     | 高       |
| 待跟进客户临时分组 | 静态     | 中       |
| 区域/行业客户分析  | 动态     | 中       |
| 活动参与客户追踪   | 静态     | 低       |

---

## 二、后端设计

### 2.1 数据模型

#### CustomerGroup 表

```python
class CustomerGroup(BaseModel):
    """客户群组表"""

    __tablename__ = "customer_groups"

    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    group_type = Column(String(20), nullable=False, index=True)  # 'dynamic' / 'static'
    filter_conditions = Column(JSON)  # 动态群组的筛选条件
    created_by = Column(Integer, ForeignKey("users.id"), index=True)

    # 关联
    creator = relationship("User", back_populates="created_groups")
    members = relationship(
        "CustomerGroupMember", back_populates="group", cascade="all, delete-orphan"
    )
```

#### CustomerGroupMember 表

```python
class CustomerGroupMember(BaseModel):
    """静态群组成员表"""

    __tablename__ = "customer_group_members"

    group_id = Column(Integer, ForeignKey("customer_groups.id"), primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), primary_key=True, index=True)

    # 关联
    group = relationship("CustomerGroup", back_populates="members")
    customer = relationship("Customer", back_populates="group_memberships")
```

#### 索引设计

```python
__table_args__ = (
    # 动态群组查询优化
    Index("idx_group_type_created_by", "group_type", "created_by"),
    # 成员查询优化
    Index("idx_member_group_customer", "group_id", "customer_id"),
    Index("idx_member_customer", "customer_id"),
)
```

### 2.2 API 端点

#### 群组管理

| 方法  | 端点                                  | 说明         |
| ----- | ------------------------------------- | ------------ |
| GET   | `/api/v1/customer-groups`             | 获取群组列表 |
| POST  | `/api/v1/customer-groups`             | 创建群组     |
| GET   | `/api/v1/customer-groups/{id}`        | 获取群组详情 |
| PUT   | `/api/v1/customer-groups/{id}`        | 更新群组     |
| DELETE | `/api/v1/customer-groups/{id}`        | 删除群组     |
| GET   | `/api/v1/customer-groups/{id}/members` | 获取群组成员 |

#### 成员管理（静态群组）

| 方法   | 端点                                        | 说明       |
| ------ | ------------------------------------------- | ---------- |
| POST   | `/api/v1/customer-groups/{id}/members`      | 添加成员   |
| POST   | `/api/v1/customer-groups/{id}/members/batch` | 批量添加   |
| DELETE | `/api/v1/customer-groups/{id}/members/{customer_id}` | 移除成员   |
| DELETE | `/api/v1/customer-groups/{id}/members/batch` | 批量移除   |

#### 群组应用

| 方法 | 端点                               | 说明                   |
| ---- | ---------------------------------- | ---------------------- |
| POST | `/api/v1/customer-groups/{id}/apply` | 应用群组筛选，返回客户列表 |
| GET  | `/api/v1/customer-groups/{id}/stats` | 获取群组统计信息       |

### 2.3 服务层设计

#### CustomerGroupService

```python
class CustomerGroupService:
    """客户群组服务"""

    async def create_group(self, data: dict, created_by: int) -> CustomerGroup:
        """创建群组"""

    async def get_user_groups(self, user_id: int) -> List[CustomerGroup]:
        """获取用户的群组列表"""

    async def get_group_detail(self, group_id: int) -> Optional[CustomerGroup]:
        """获取群组详情"""

    async def update_group(self, group_id: int, data: dict) -> Optional[CustomerGroup]:
        """更新群组"""

    async def delete_group(self, group_id: int) -> bool:
        """删除群组"""

    async def add_member(self, group_id: int, customer_id: int) -> bool:
        """添加成员（静态群组）"""

    async def remove_member(self, group_id: int, customer_id: int) -> bool:
        """移除成员"""

    async def get_group_members(self, group_id: int, page: int, page_size: int) -> Tuple[List[Customer], int]:
        """获取群组成员列表"""

    async def apply_group_filter(self, group_id: int, page: int, page_size: int) -> Tuple[List[Customer], int]:
        """应用群组筛选，返回匹配的客户"""

    async def get_group_stats(self, group_id: int) -> dict:
        """获取群组统计信息"""
```

### 2.4 权限设计

| 操作         | 创建者 | 管理员 | 普通用户 |
| ------------ | ------ | ------ | -------- |
| 查看自己的群组 | ✅     | ✅     | ❌       |
| 查看他人群组   | ❌     | ✅     | ❌       |
| 创建群组     | ✅     | ✅     | ✅       |
| 编辑自己的群组 | ✅     | ✅     | ❌       |
| 删除自己的群组 | ✅     | ✅     | ❌       |
| 编辑他人群组   | ❌     | ✅     | ❌       |
| 删除他人群组   | ❌     | ✅     | ❌       |
| 使用群组筛选   | ✅     | ✅     | ✅（自己的群组） |

---

## 三、前端设计

### 3.1 页面结构

```
frontend/src/views/customer-groups/
├── Index.vue          # 群组管理主页面（左侧边栏 + 客户列表）
├── components/
│   ├── GroupSidebar.vue   # 群组列表侧边栏
│   ├── GroupForm.vue      # 新建/编辑群组表单
│   ├── GroupMembers.vue   # 群组成员管理
│   └── GroupFilter.vue    # 动态群组筛选条件配置
```

### 3.2 界面布局

```
┌─────────────────────────────────────────────────────────────┐
│ 群组管理 │ 客户列表                                          │
│ ──────── │ ───────────────────────────────────────────────  │
│          │                                                  │
│ 📁 全部客户│ [筛选条件显示区 - 当前群组/筛选]                  │
│          │                                                  │
│ 📂 我的群组│ ┌─────────────────────────────────────────────┐│
│   ├─ Q1 重点客户│ │ 客户表格                                   ││
│   ├─ 待跟进客户│ │ - 复选框批量选择                          ││
│   ├─ 区域客户  │ │ - 操作列：添加到群组                       ││
│   └─ [+ 新建群组]│ └─────────────────────────────────────────────┘│
│          │                                                  │
│ ──────── │ [分页]                                            │
│ [群组详情]│                                                  │
│ 名称：___ │                                                  │
│ 类型：○动态 ●静态│                                              │
│ 成员：15 个 │                                                  │
│ [编辑] [删除]│                                                  │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 核心交互流程

#### 3.3.1 创建动态群组

```
1. 用户在客户列表配置筛选条件
2. 点击"保存为群组"按钮
3. 弹出表单：填写名称、描述、选择"动态群组"
4. 确认创建
5. 群组出现在左侧边栏
```

#### 3.3.2 创建静态群组

```
1. 用户点击左侧边栏"新建群组"
2. 弹出表单：填写名称、描述、选择"静态群组"
3. 确认创建，进入群组成员管理页面
4. 点击"添加客户"，弹出客户选择器
5. 勾选客户，确认添加
```

#### 3.3.3 应用群组筛选

```
1. 用户点击左侧边栏群组
2. 动态群组：应用筛选条件，刷新客户列表
3. 静态群组：加载成员列表，刷新客户列表
4. 表格上方显示"当前查看：XXX 群组"
```

#### 3.3.4 批量添加到群组

```
1. 用户在客户列表勾选多个客户
2. 点击"批量操作" → "添加到群组"
3. 弹出群组选择器（仅显示用户自己的群组）
4. 选择目标群组，确认
5. 显示添加结果（成功/失败数量）
```

### 3.4 API 客户端

```typescript
// frontend/src/api/customer-groups.ts

export function getCustomerGroups() {
  return request.get('/api/v1/customer-groups')
}

export function createCustomerGroup(data: {
  name: string
  description?: string
  group_type: 'dynamic' | 'static'
  filter_conditions?: any
}) {
  return request.post('/api/v1/customer-groups', data)
}

export function updateCustomerGroup(id: number, data: any) {
  return request.put(`/api/v1/customer-groups/${id}`, data)
}

export function deleteCustomerGroup(id: number) {
  return request.delete(`/api/v1/customer-groups/${id}`)
}

export function getGroupMembers(id: number, params: any) {
  return request.get(`/api/v1/customer-groups/${id}/members`, { params })
}

export function addGroupMember(id: number, customer_id: number) {
  return request.post(`/api/v1/customer-groups/${id}/members`, { customer_id })
}

export function removeGroupMember(id: number, customer_id: number) {
  return request.delete(`/api/v1/customer-groups/${id}/members/${customer_id}`)
}

export function applyGroupFilter(id: number, params: any) {
  return request.post(`/api/v1/customer-groups/${id}/apply`, params)
}
```

---

## 四、分阶段交付计划

### Phase 1: 动态群组（4-6 小时）

**功能**：
- 保存筛选条件为动态群组
- 群组列表展示
- 应用群组筛选

**交付物**：
- 后端：CustomerGroup 模型、CRUD API
- 前端：GroupSidebar、GroupForm、筛选应用

### Phase 2: 静态群组（3-4 小时）

**功能**：
- 创建静态群组
- 手动添加/移除成员
- 批量添加成员

**交付物**：
- 后端：CustomerGroupMember 模型、成员管理 API
- 前端：GroupMembers 组件、批量操作

### Phase 3: 批量操作（3-4 小时，二期）

**功能**：
- 群组批量打标签
- 群组批量导出
- 群组批量充值

### Phase 4: 群组报表（4-6 小时，二期）

**功能**：
- 群组消耗统计
- 群组对比分析
- 群组趋势图表

---

## 五、技术风险与缓解

### 5.1 动态群组性能

**风险**：复杂筛选条件可能导致查询慢

**缓解措施**：
- 添加查询结果缓存（Redis）
- 限制最大返回数量（1000 条）
- 添加查询超时保护（30 秒）

### 5.2 静态群组维护

**风险**：客户删除后需要清理成员记录

**缓解措施**：
- 外键级联删除（ON DELETE CASCADE）
- 定期清理任务（每天凌晨）
- 删除客户前检查群组成员关系

### 5.3 数据一致性

**风险**：动态群组筛选条件可能引用不存在的字段

**缓解措施**：
- 保存时验证筛选条件格式
- 查询时捕获异常并返回友好错误
- 添加筛选条件版本管理（二期）

---

## 六、测试策略

### 6.1 单元测试

- CustomerGroupService 所有方法
- 筛选条件解析和验证
- 成员管理逻辑

### 6.2 集成测试

- 群组 CRUD API
- 成员管理 API
- 筛选应用 API

### 6.3 E2E 测试

- 创建动态群组流程
- 创建静态群组流程
- 应用群组筛选流程
- 批量添加到群组流程

---

## 七、成功指标

| 指标               | 目标值 | 测量方式     |
| ------------------ | ------ | ------------ |
| 群组创建率         | > 30%  | 创建群组用户/活跃用户 |
| 群组使用频率       | > 50%  | 使用群组筛选的会话/总会话 |
| 平均群组成员数     | > 10   | 总成员数/群组数 |
| 用户满意度         | > 4.0  | 用户调研评分 |

---

## 八、附录

### 8.1 筛选条件 JSON 结构

```json
{
  "keyword": "测试公司",
  "account_type": "formal",
  "business_type": "A",
  "customer_level": "KA",
  "settlement_type": "prepaid",
  "is_key_customer": true,
  "created_at_range": {
    "start": "2026-01-01",
    "end": "2026-03-31"
  }
}
```

### 8.2 群组列表响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "id": 1,
        "name": "Q1 重点客户",
        "description": "2026 年 Q1 重点跟进客户",
        "group_type": "static",
        "member_count": 15,
        "created_by": 1,
        "created_at": "2026-04-01T10:00:00Z"
      },
      {
        "id": 2,
        "name": "待跟进客户",
        "description": null,
        "group_type": "dynamic",
        "filter_conditions": {
          "customer_level": "普通",
          "is_key_customer": false
        },
        "member_count": 42,
        "created_by": 1,
        "created_at": "2026-04-02T15:30:00Z"
      }
    ],
    "total": 2
  }
}
```
