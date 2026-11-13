# Break-Loop 分析：CRM 同步 failed「回款字段缺少行业分类」= 元数据解析的键名白名单

- **日期**: 2026-11-12
- **现象**: 手动同步 → 后台日志 `CRM 同步失败 run=2: CRM 回款字段缺少「行业分类」，无法筛选可导入回款`
- **事实**: `resolve_industry_paths()` 在真实 `GET /api/v2/custom_fields/received_payment/by_group`
  响应里一个字段节点都没找到 → `CrmContractError` → run failed
- **结论**: 上游契约没变。是**我们自己的递归遍历器看不见 `custom_fields`**。

---

## 1. 根因分类

- **主分类**: **E. Implicit Assumption** —— `_walk_dicts` 假设上游元数据沿
  `children / options / sub_fields / values / items / list` 这些键下钻。
- **并发分类**: **D. Test Coverage Gap（以「自编结构」形式）** —— 既有单测 fixture 是
  `{"items": [{"label": "房产经纪", "children": [...]}]}`，**恰好命中白名单**，
  于是单测 100% 绿灯，把一个错误假说固化成了「契约」。
- **附带**: 调研阶段确实实测过该接口并把真实路径写进了方案文档
  （`docs/specs/2026-11-11-crm-recharge-management-plan.md:20`），但**实现与测试都没用它**。

### 真实结构（2026-11-12 实测，本租户）

```
data.custom_field_groups[]                                  (list, 3 组)
  .custom_fields[]                                          ← 白名单里没有它
    .name = "text_asset_3565dc", .label = "行业分类", .field_type = "nested_select_field"
    .input_field_options.collection_options[]               (16 项)
    .options.select_options[]                               (镜像分支，同一份 16 项)
      .children[]                                           (递归子项)
```

行业根值实测：房产经纪 `ba2503bf-…`、新房开发 `bdb440d1-…`；子项新业绩 `1b1ae256-…`、
老业绩 `943a9513-…` —— 与调研记录一致。

---

## 2. 贝叶斯推理记录

| 假设 | 先验 | 依据 |
|---|---|---|
| H1 我方解析器与真实结构不符 | 45% | 该接口在调研阶段已验证有「行业分类」；现在报缺失，最可能是读取路径错 |
| H2 上游契约变更（字段被改名/隐藏） | 25% | 上游确实可能改版；但方案文档记录了 `text_asset_3565dc` 且是本租户租户级字段 |
| H3 凭据/企业权限变化导致返回空数据 | 20% | 用户刚重填配置（corp/phone 与调研时可能不同） |
| H4 请求路径/参数错（需 group 参数） | 10% | 路径来自官方文档 |

**判别性证据**（只做一次真实只读调用，而不是继续读代码猜）：

| 证据 | H1 | H2 | H3 | H4 | 观测 |
|---|---|---|---|---|---|
| 真实响应含 `label=行业分类, name=text_asset_3565dc` | 是（那问题必在解析） | 否 | 否 | 否 | **是** |
| 顶层结构 `custom_field_groups[].custom_fields[]` | 是 | 可能 | 否 | 否 | **是** |
| 白名单中是否含 `custom_fields` | 否 | — | — | — | **否** |

**后验**: H1 ≈ 99%。**置信度 ≥90% → 直接修复并端到端验证。**

**证伪路径**：把 `_walk_dicts` 恢复成旧白名单，`resolve_industry_paths(真实响应)` 会重新抛
「缺少行业分类」；单测 `test_collects_roots_and_descendants_from_real_structure` 会立刻失败。

---

## 3. 防复发机制

| 优先级 | 机制 | 具体动作 | 状态 |
|---|---|---|---|
| P0 | 架构 | `_walk_dicts` 改为**全量遍历**（迭代栈，避免深递归），命中与否只由 `label`/`name` 精确匹配决定 | DONE |
| P0 | 测试 | fixture 换成**实测响应最小快照**（保留 `custom_field_groups/custom_fields/input_field_options/options` 与无关字段），断言 4 个允许值精确相等 | DONE |
| P0 | 测试 | 新增：仅 `options` 镜像分支可解析；无关字段不被误收；`label` 重名 → 显式报错 | DONE |
| P1 | 文档 | `cross-layer-thinking-guide.md` 新增「第三方 JSON 解析：不要按已知键名白名单下钻」 | DONE |
| P1 | 文档 | 解析器 docstring 写清真实键路径并注明「白名单曾导致同步必然 failed」 | DONE |
| P2 | 流程 | 外部接口调研结论必须**同时**落成 fixture；只写进方案文档不算完成 | DONE（写入 guide 规则） |

---

## 4. 系统性扩展

- **同类风险点扫描**：`_walk_dicts` / `_node_label` / `_collect_option_values` 只有
  `resolve_industry_paths` 一个调用方，影响面已收窄（`grep -rn "_walk_dicts" app/` 仅定义处）。
- **同族缺陷**：`CrmClient._extract_page` 原本也只认
  `list/items/records/data` 四个键 —— 上一轮已修（具名键扩充 + 「唯一数组」兜底 +
  错误信息带实际键名）。两者是同一类「键名假设」，建议后续把所有上游分页/元数据解析
  统一走「具名键优先 + 结构兜底 + 失败带键名」三步。
- **设计层**：`resolve_industry_paths` 的失败语义是**显式 failed**（不猜、不用客户 industry
  兜底），这一点是正确的 —— 本次不需要改语义，只改解析能力。
- **流程层**：本次缺陷能上线，是因为「调研 → 实现」之间没有把实测响应交接给实现与测试。
  规则已写入 guide：调研结论必须落成 fixture。

---

## 5. 知识沉淀（已落盘）

- [x] `.trellis/spec/guides/cross-layer-thinking-guide.md` → `## 第三方 JSON 解析：不要按「已知键名白名单」下钻`
- [x] `app/services/crm_recharge.py::_walk_dicts` docstring：真实键路径 + 事故原因
- [x] `tests/unit/test_crm_recharge.py`：fixture 改为实测结构（含 4 个真实 UUID 与无关字段）
- [x] 本文件 + `acceptance.md` 追加端到端验证记录

## 6. 相邻缺陷（同一次调查发现）：合同枚举按 created_at asc，回款要等扫完历史合同

修好解析后真实同步仍长时间 `payment_count=0`，进一步查证：

| 证据 | 结果 |
|---|---|
| `order=asc` 前 500 个合同 `received_payments_amount` | **全部为 0**（老合同未收款） |
| `order=asc` 扫到 1100 个合同时 `payment_count` | **0** |
| `order=desc` 第一页 50 个合同中 `received_payments_amount>0` | **36 个** |
| `order=desc` 同步前 50 个合同后 `crm_payments` 镜像 | **11 笔本月回款，9 笔 eligible** |

这不是「解析错误」而是**顺序导致的可用性缺陷**：全量语义正确，但用户要等扫完全部
历史合同才看到本月数据（前端只能看到「已扫到 0 笔回款」）。修复：`iter_contracts`
改 `order="desc"`（全量不变），并把阶段/合同扫描进度显示到同步弹窗。
回归锚点：`tests/unit/test_crm_client_iters.py::TestIterContracts::test_requests_newest_first`。

## 7. 端到端验证（真实上游，只读镜像，不充值）

- 元数据解析：真实 `by_group` → 4 个允许值；真实样本回款 14430502 → `eligible=True`、
  `industry_label=房产经纪/老业绩`。
- 真实同步 run=4：`crm_payments` 镜像 8 笔（11-04~11-09），全部 `eligible=true`，
  行业标签正确；客户阶段 5032 完成；字段校验不再失败。
- 详见 `acceptance.md`「2026-11-12 元数据解析修复」。
