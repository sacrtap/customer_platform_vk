"""客户余额与健康度共享阈值常量

余额预警阈值是跨模块契约：客户列表「简易健康度」估算与定时任务
`check_balance_warning` 必须使用同一组阈值，否则会出现「列表标高风险、
预警任务却未标记 warning/critical」或反之的口径漂移。

历史问题：`routes/customers.py` 列表 health 与 `tasks/balance_check.py`
各自硬编码 500/1000，数值相同但无引用关系，改一处必漏另一处。
"""

# 余额低于此值 → 严重预警 / 列表「高风险」
BALANCE_CRITICAL_THRESHOLD: float = 500.0

# 余额低于此值 → 预警 / 列表「关注」
BALANCE_WARNING_THRESHOLD: float = 1000.0
