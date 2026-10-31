"""权限码三处一致性（防漂移）守护测试。

单一事实源是 ``scripts/seed.py`` 的 ``ALL_PERMISSIONS``。后端路由
（``require_permission("...")``）与前端门控（``can('...')`` /
``hasPermission('...')`` / 路由 ``meta.requiresPermission`` / navSections
``permission``）引用的权限码必须是 seed 的子集——否则会出现「代码引用了一个
seed 里不存在的权限码」：后端端点永远 403、前端门控永远不满足，且这类问题
只在运行时暴露。

静态扫描，无 DB、无网络。seed 的延迟导入约定同
``test_test_data_consistency.py``（避免收集期副作用）。
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
REPO_ROOT = BASE_DIR.parent  # 仓库根

# 权限码字面量形式：module:action（小写字母/下划线），过滤掉普通字符串属性
CODE = r"[a-z_]+:[a-z_]+"

BACKEND_PATTERN = re.compile(rf"""require_permission\(\s*['"]({CODE})['"]\s*\)""")

FRONTEND_PATTERNS = [
    re.compile(rf"""can\(\s*['"]({CODE})['"]\s*\)"""),
    re.compile(rf"""hasPermission\(\s*['"]({CODE})['"]\s*\)"""),
    re.compile(rf"""requiresPermission:\s*['"]({CODE})['"]"""),
    re.compile(rf"""permission:\s*['"]({CODE})['"]"""),
]


def _seed_codes() -> set[str]:
    from scripts.seed import ALL_PERMISSIONS

    return {code for code, *_ in ALL_PERMISSIONS}


def _backend_refs() -> dict[str, list[str]]:
    """扫描 backend/app 下所有 .py 的 require_permission 字面量 → {code: [位置]}"""
    refs: dict[str, list[str]] = {}
    for py in sorted((BASE_DIR / "app").rglob("*.py")):
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            for m in BACKEND_PATTERN.finditer(line):
                refs.setdefault(m.group(1), []).append(f"{py.relative_to(REPO_ROOT)}:{lineno}")
    return refs


def _frontend_refs() -> dict[str, list[str]]:
    """扫描 frontend/src 下所有 .vue/.ts 的权限门控字面量 → {code: [位置]}"""
    refs: dict[str, list[str]] = {}
    src = REPO_ROOT / "frontend" / "src"
    files = sorted([*src.rglob("*.vue"), *src.rglob("*.ts")])
    for f in files:
        for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in FRONTEND_PATTERNS:
                for m in pattern.finditer(line):
                    refs.setdefault(m.group(1), []).append(f"{f.relative_to(REPO_ROOT)}:{lineno}")
    return refs


def _format_missing(seed: set[str], refs: dict[str, list[str]]) -> str:
    return "\n".join(f"  {code}  <-  {', '.join(refs[code])}" for code in sorted(set(refs) - seed))


def test_backend_permission_codes_exist_in_seed():
    """后端 require_permission 引用的权限码必须都在 seed ALL_PERMISSIONS 中。"""
    missing = _format_missing(_seed_codes(), _backend_refs())
    assert not missing, f"后端引用了 seed 中不存在的权限码：\n{missing}"


def test_frontend_permission_codes_exist_in_seed():
    """前端权限门控引用的权限码必须都在 seed ALL_PERMISSIONS 中。"""
    missing = _format_missing(_seed_codes(), _frontend_refs())
    assert not missing, f"前端引用了 seed 中不存在的权限码：\n{missing}"
