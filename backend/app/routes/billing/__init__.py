"""结算管理路由包

将原 billing.py（2882行）拆分为 5 个子模块：
- balances: 余额管理（充值、记录、统计、趋势）
- pricing: 定价规则 CRUD
- invoices: 发票管理（生成、审批、支付、导出）
- imports: 余额导入
- packages: 套餐计划管理
"""

from sanic import Blueprint

billing_bp = Blueprint("billing", url_prefix="/api/v1/billing")

# 导入子模块以注册路由
from . import balances, imports, invoices, packages, pricing  # noqa: E402, F401
