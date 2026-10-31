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


# ========== 反向断言：登录可访问的端点必须显式登记 ==========
#
# 正向断言防「引用了不存在的码」，反向断言防「有端点却没有任何码」——
# 后者正是行业类型/合作状态/ERP 系统三个 GET 端点曾长期裸奔（页面按
# manage 隐藏、API 登录即可读）的盲区。规则：
#
#   所有带 @auth_required 的路由，若没有任何 require_permission，
#   则必须在下列豁免清单中登记（附理由），否则测试失败。
#
# 豁免清单是显式决策的记录，不是后门：新增裸端点必须在此说明理由。
EXEMPT_READ_ENDPOINTS: dict[str, str] = {
    "/api/v1/dicts/industry_types": "字典数据（id/name/sort_order）：客户表单行业类型下拉，全员基础交互数据",
    "/api/v1/system/updates": "系统升级公告：产品设计为全员可见",
    "/api/v1/users/options": "运营经理/销售经理下拉选项（id/username/real_name）：业务模块姓名展示的基础能力，路由 docstring 已声明",
    "/api/v1/users/profile": "个人中心：本人资料",
    "/api/v1/users/me/preferences": "个人中心：本人偏好设置",
}

EXEMPT_WRITE_ENDPOINTS: dict[str, str] = {
    "/api/v1/users/profile": "个人中心：本人资料修改",
    "/api/v1/users/password": "个人中心：本人修改密码",
    "/api/v1/users/me/preferences": "个人中心：本人偏好修改",
    "/api/v1/users/avatar": "个人中心：本人头像上传",
}


def _scan_endpoints() -> list[tuple[str, str, bool, list[str], str]]:
    """AST 扫描全部路由 → [(METHOD, full_path, has_auth_required, perms, 位置)]。

    full_path = blueprint url_prefix + 路由 path。用 AST 而非正则，
    避免漏掉跨行装饰器或把非路由函数误判为端点。
    """
    import ast

    endpoints: list[tuple[str, str, bool, list[str], str]] = []
    for py in sorted((BASE_DIR / "app" / "routes").rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        prefixes: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                tgt = node.targets[0]
                if isinstance(tgt, ast.Name) and "Blueprint" in ast.unparse(node.value.func):
                    for kw in node.value.keywords:
                        if kw.arg == "url_prefix" and isinstance(kw.value, ast.Constant):
                            prefixes[tgt.id] = kw.value.value
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            method = path = None
            perms: list[str] = []
            has_auth = False
            for dec in node.decorator_list:
                src = ast.unparse(dec)
                if "require_permission" in src:
                    m = re.search(rf"""['"]({CODE})['"]""", src)
                    if m:
                        perms.append(m.group(1))
                if "auth_required" in src:
                    has_auth = True
                m = re.match(r"(\w+)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]*)['\"]", src)
                if m:
                    bp, verb, sub = m.group(1), m.group(2).upper(), m.group(3)
                    method = verb
                    prefix = prefixes.get(bp, "")
                    path = prefix + (sub if sub.startswith("/") or sub == "" else "/" + sub)
                    if len(path) > 1:
                        path = path.rstrip("/")
            if method:
                endpoints.append(
                    (method, path, has_auth, perms, f"{py.relative_to(REPO_ROOT)}:{node.lineno}")
                )
    return endpoints


def test_no_unguarded_endpoints_without_exemption():
    """@auth_required 但无权限码的端点必须在豁免清单登记（附理由）。"""
    unguarded = [(m, p, loc) for m, p, auth, perms, loc in _scan_endpoints() if auth and not perms]
    problems = []
    for method, path, loc in unguarded:
        table = EXEMPT_READ_ENDPOINTS if method == "GET" else EXEMPT_WRITE_ENDPOINTS
        if path not in table:
            problems.append(f"  {method} {path}  ({loc})")
    assert not problems, (
        "以下端点登录可访问但未挂权限码、也未在豁免清单登记：\n"
        + "\n".join(problems)
        + "\n\n若是刻意设计（字典数据/本人数据/公告等），请在 "
        "test_permission_drift.py 的 EXEMPT_READ_ENDPOINTS / EXEMPT_WRITE_ENDPOINTS "
        "中登记并附理由；否则补上 @require_permission。"
    )


def test_exemption_list_has_no_stale_entries():
    """豁免清单不得包含已不存在的端点（防清单腐烂）。"""
    all_endpoints = _scan_endpoints()
    stale = []
    for table in (EXEMPT_READ_ENDPOINTS, EXEMPT_WRITE_ENDPOINTS):
        for path in table:
            if not any(p == path for _, p, _, _, _ in all_endpoints):
                stale.append(f"  {path}")
    assert not stale, (
        "豁免清单包含已不存在的端点（端点已删除或路径变更），请同步清理：\n" + "\n".join(stale)
    )
