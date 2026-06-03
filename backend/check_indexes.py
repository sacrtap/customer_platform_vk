import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def check():
    url = "postgresql+asyncpg://postgres:postgres@localhost:5432/customer_platform_test"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        # Check unique index
        result = await conn.execute(
            text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'industry_types'
        """)
        )
        rows = result.fetchall()
        for row in rows:
            print(f"Index: {row.indexname}")
            print(f"Definition: {row.indexdef}")
            print()


asyncio.run(check())
