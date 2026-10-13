#!/bin/bash
# 先应用数据库迁移并校验漂移，防止运行库落后于模型（「写了迁移」≠「升了库」）
python -m alembic upgrade head
python scripts/check_schema_drift.py
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
