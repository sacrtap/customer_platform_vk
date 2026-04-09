# Graph Report - .  (2026-04-09)

## Corpus Check
- 186 files · ~159,793 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 28 nodes · 26 edges · 7 communities detected
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `frontend/src/views/customers/Index.vue` - 7 edges
2. `Customer - God Node (91 edges)` - 5 edges
3. `架构速览 - 技术栈` - 3 edges
4. `业务模块` - 3 edges
5. `客户管理页面体验优化实施计划` - 3 edges
6. `Community 4 - Billing & Balance` - 3 edges
7. `Task 2: 优化重点客户样式显示` - 2 edges
8. `Task 3: 优化运营经理字段为下拉选择` - 2 edges
9. `Task 5: 在 Detail.vue 中添加缺失的编辑字段` - 2 edges
10. `Community 35 - 业务模块概览` - 2 edges

## Surprising Connections (you probably didn't know these)
- `Task 5: 在 Detail.vue 中添加缺失的编辑字段` --conceptually_related_to--> `Customer - God Node (91 edges)`  [INFERRED]
  docs/superpowers/plans/2026-04-09-customer-management-optimization.md → graphify-out/GRAPH_REPORT.md
- `Task 2: 优化重点客户样式显示` --conceptually_related_to--> `Customer - God Node (91 edges)`  [INFERRED]
  docs/superpowers/plans/2026-04-09-customer-management-optimization.md → graphify-out/GRAPH_REPORT.md
- `Task 3: 优化运营经理字段为下拉选择` --conceptually_related_to--> `Customer - God Node (91 edges)`  [INFERRED]
  docs/superpowers/plans/2026-04-09-customer-management-optimization.md → graphify-out/GRAPH_REPORT.md
- `架构速览 - 技术栈` --implements--> `Vue 3.4 + TypeScript 5.3 + Arco Design 2.54`  [EXTRACTED]
  AGENTS.md → docs/superpowers/plans/2026-04-09-customer-management-optimization.md
- `知识图谱系统` --references--> `Graph Report Summary (1601 nodes, 2660 edges)`  [EXTRACTED]
  AGENTS.md → graphify-out/GRAPH_REPORT.md

## Communities

### Community 0 - "Customer & Billing Core"
Cohesion: 0.29
Nodes (7): Community 2 - Customer Service Core, Community 4 - Billing & Balance, CustomerBalance - God Node (78 edges), Customer - God Node (91 edges), Invoice - God Node (76 edges), Task 2: 优化重点客户样式显示, Task 3: 优化运营经理字段为下拉选择

### Community 1 - "Customer Management Implementation"
Cohesion: 0.29
Nodes (7): 架构速览 - 技术栈, 安全约束, 测试配置与规范, frontend/src/views/customers/Detail.vue, 客户管理页面体验优化实施计划, Task 5: 在 Detail.vue 中添加缺失的编辑字段, Vue 3.4 + TypeScript 5.3 + Arco Design 2.54

### Community 2 - "Index.vue Optimization Tasks"
Cohesion: 0.4
Nodes (5): frontend/src/views/customers/Index.vue, Task 1: 修复创建时间格式问题, Task 4: 优化筛选区域布局, Task 6: 优化表格列宽和操作按钮布局, Task 7: 添加表单验证触发器和必填项标识

### Community 3 - "Business Modules Overview"
Cohesion: 0.5
Nodes (5): 业务模块, 余额管理 (先赠后实), Community 35 - 业务模块概览, RBAC 权限模型, 3 种计费模式 (定价/阶梯/包年)

### Community 4 - "Knowledge Graph System"
Cohesion: 1.0
Nodes (2): 知识图谱系统, Graph Report Summary (1601 nodes, 2660 edges)

### Community 5 - "Empty Community"
Cohesion: 1.0
Nodes (0): 

### Community 6 - "AGENTS.md Documentation"
Cohesion: 1.0
Nodes (1): AGENTS.md - 客户运营中台开发指南

## Knowledge Gaps
- **13 isolated node(s):** `AGENTS.md - 客户运营中台开发指南`, `测试配置与规范`, `安全约束`, `知识图谱系统`, `Task 1: 修复创建时间格式问题` (+8 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Knowledge Graph System`** (2 nodes): `知识图谱系统`, `Graph Report Summary (1601 nodes, 2660 edges)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Empty Community`** (1 nodes): `index.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `AGENTS.md Documentation`** (1 nodes): `AGENTS.md - 客户运营中台开发指南`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `frontend/src/views/customers/Index.vue` connect `Index.vue Optimization Tasks` to `Customer & Billing Core`, `Customer Management Implementation`?**
  _High betweenness centrality (0.257) - this node is a cross-community bridge._
- **Why does `Customer - God Node (91 edges)` connect `Customer & Billing Core` to `Customer Management Implementation`?**
  _High betweenness centrality (0.188) - this node is a cross-community bridge._
- **Why does `客户管理页面体验优化实施计划` connect `Customer Management Implementation` to `Index.vue Optimization Tasks`?**
  _High betweenness centrality (0.181) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Customer - God Node (91 edges)` (e.g. with `Task 2: 优化重点客户样式显示` and `Task 3: 优化运营经理字段为下拉选择`) actually correct?**
  _`Customer - God Node (91 edges)` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `架构速览 - 技术栈` (e.g. with `测试配置与规范` and `安全约束`) actually correct?**
  _`架构速览 - 技术栈` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `AGENTS.md - 客户运营中台开发指南`, `测试配置与规范`, `安全约束` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._