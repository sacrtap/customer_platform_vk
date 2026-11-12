"""数据库事务辅助工具。

背景（踩过的坑）：Sanic 把 `AsyncSession` 挂在 `request.ctx.db_session` 上，
`@auth_required` / `@require_permission` / 预检查询等只读操作都会触发
SQLAlchemy 2.0 的 autobegin，使 session 上留下一个隐式事务。此时路由体里再写
`async with db.begin():` 会抛：

    sqlalchemy.exc.InvalidRequestError: A transaction is already begun on this Session

异常逃出路由 → HTTP 500 → 前端只能显示「系统繁忙，请稍后重试」。而权限缓存
命中与否会改变「前面到底有没有发生查询」，所以这类缺陷在开发时可能偶发通过，
上线后必然复现。

`begin_write` 把「结束请求级隐式事务 + 开启显式写事务」收敛成一处，新增写端点
一律用它，不要裸写 `db.begin()`。

注意：只适用于 `begin_write` 之前**没有待提交写入**的场景（纯读前置）。若之前的
步骤已经 `add()`/修改了 ORM 对象并希望一起提交，直接用 `await db.commit()`。
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def begin_write(db: AsyncSession) -> AsyncGenerator[None, None]:
    """开启显式写事务，先结束请求级隐式（只读）事务。

    用法与 `db.begin()` 完全相同：

        async with begin_write(db):
            ...
    """
    await db.rollback()
    async with db.begin():
        yield
