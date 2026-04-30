"""中间件模块

注意：auth 中间件不在 __init__.py 中导入，避免在测试中过早加载
require_permission 装饰器和 permission_cache。需要时直接从 app.middleware.auth 导入。
"""
