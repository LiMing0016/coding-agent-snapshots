"""POST /api/analysis/count 的核心逻辑：校验并精确计数程序树。

程序是由 op / seq / repeat / double / triangle 构成的 JSON 树。
所有计数都用闭形式（公式或对已计算子体做乘法），绝不按 n 或 times 展开执行；
数值全程使用 Python 任意精度整数，结果以十进制字符串返回。

错误路径为 JSONPath 风格：$.n、$.program.items[0].body，返回先序遇到的首个错误。
"""
from __future__ import annotations

import json
from typing import Any

MAX_N = 10**18
MAX_TIMES = 10**6
MAX_NODES = 200
MAX_DEPTH = 16  # 根节点深度为 1

NODE_TYPES = frozenset({"op", "seq", "repeat", "double", "triangle"})
# 各节点类型除 type 外必须存在的字段（按文档顺序校验）
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "seq": ("items",),
    "repeat": ("times", "body"),
    "double": ("body",),
}
KNOWN_FIELDS: dict[str, frozenset[str]] = {
    "op": frozenset({"type"}),
    "seq": frozenset({"type", "items"}),
    "repeat": frozenset({"type", "times", "body"}),
    "double": frozenset({"type", "body"}),
    "triangle": frozenset({"type"}),
}

# 稳定错误码
E_INVALID_JSON = "invalid_json"
E_TYPE_ERROR = "type_error"
E_MISSING_FIELD = "missing_field"
E_UNKNOWN_FIELD = "unknown_field"
E_INVALID_VALUE = "invalid_value"
E_OUT_OF_RANGE = "out_of_range"
E_NODE_LIMIT = "node_limit"
E_DEPTH_LIMIT = "depth_limit"
E_UNKNOWN_NODE = "unknown_node"


class AnalysisError(Exception):
    """携带稳定 code 与输入树先序首个错误的 JSON 路径。"""

    def __init__(self, code: str, path: str):
        super().__init__(f"{code} at {path}")
        self.code = code
        self.path = path


def _format_path(segments: tuple[str, ...]) -> str:
    """段为对象字段名（点号连接）或数组下标（方括号）。"""
    out = "$"
    for seg in segments:
        if seg.isdigit():
            out += f"[{seg}]"
        else:
            out += f".{seg}"
    return out


def _fail(code: str, segments: tuple[str, ...]) -> None:
    raise AnalysisError(code, _format_path(segments))


def _parse_n(raw: Any, segments: tuple[str, ...]) -> int:
    """n 必须是十进制数字字符串，数值在 1..10^18。"""
    if not isinstance(raw, str):  # bool 也不是 str，自然落入类型错误
        _fail(E_TYPE_ERROR, segments)
    assert isinstance(raw, str)
    if not raw.isdigit() or not raw:  # 排除空串、符号、小数点、空白等
        _fail(E_INVALID_VALUE, segments)
    if len(raw) > 19:  # 10^18 只有 19 位，超长必越界，先挡掉超大整数转换
        _fail(E_OUT_OF_RANGE, segments)
    value = int(raw)
    if value < 1 or value > MAX_N:
        _fail(E_OUT_OF_RANGE, segments)
    return value


def analyze(raw_text: str | bytes) -> str:
    """解析并计数整个请求体，成功返回十进制字符串，失败抛 AnalysisError。"""
    try:
        root: Any = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        raise AnalysisError(E_INVALID_JSON, "$")
    if not isinstance(root, dict):
        raise AnalysisError(E_TYPE_ERROR, "$")

    # 顶层字段：必填检查（n 先于 program，因为计数依赖 n），再查未知字段，最后才下树。
    if "n" not in root:
        _fail(E_MISSING_FIELD, ("n",))
    n = _parse_n(root["n"], ("n",))
    if "program" not in root:
        _fail(E_MISSING_FIELD, ("program",))
    for key in sorted(k for k in root if k not in ("n", "program")):
        _fail(E_UNKNOWN_FIELD, (key,))

    state = {"nodes": 0}

    def visit(node: Any, depth: int, segments: tuple[str, ...]) -> int:
        # 进入节点即检查预算：先确认对象类型，再查深度，再查节点数。
        if not isinstance(node, dict):
            _fail(E_TYPE_ERROR, segments)
        assert isinstance(node, dict)
        if depth > MAX_DEPTH:
            _fail(E_DEPTH_LIMIT, segments)
        state["nodes"] += 1
        if state["nodes"] > MAX_NODES:
            _fail(E_NODE_LIMIT, segments)

        # type 判别字段。
        if "type" not in node:
            _fail(E_MISSING_FIELD, segments + ("type",))
        node_type = node["type"]
        if not isinstance(node_type, str):
            _fail(E_TYPE_ERROR, segments + ("type",))
        if node_type not in NODE_TYPES:
            _fail(E_UNKNOWN_NODE, segments + ("type",))

        # 节点自身检查先于子树下溯（先序）：先必填、再未知字段。
        for field in REQUIRED_FIELDS.get(node_type, ()):
            if field not in node:
                _fail(E_MISSING_FIELD, segments + (field,))
        known = KNOWN_FIELDS[node_type]
        for key in sorted(k for k in node if k not in known):
            _fail(E_UNKNOWN_FIELD, segments + (key,))

        if node_type == "op":
            return 1
        if node_type == "triangle":
            # 固定单位体的 1+2+…+n，不接收 body 等参数。
            return n * (n + 1) // 2

        if node_type == "seq":
            items = node["items"]
            if not isinstance(items, list):
                _fail(E_TYPE_ERROR, segments + ("items",))
            total = 0
            for i, item in enumerate(items):
                total += visit(item, depth + 1, segments + ("items", str(i)))
            return total

        if node_type == "repeat":
            times_raw = node["times"]
            if isinstance(times_raw, bool) or not isinstance(times_raw, (int, str)):
                _fail(E_TYPE_ERROR, segments + ("times",))
            if isinstance(times_raw, str):
                if times_raw != "n":
                    _fail(E_INVALID_VALUE, segments + ("times",))
                times = n
            else:
                times = times_raw
                if times < 0 or times > MAX_TIMES:
                    _fail(E_OUT_OF_RANGE, segments + ("times",))
            body_count = visit(node["body"], depth + 1, segments + ("body",))
            return times * body_count

        # double：倍增 1,2,4,… 直到不超过 n，每轮执行一次 body，不按 n 展开。
        body_count = visit(node["body"], depth + 1, segments + ("body",))
        rounds = n.bit_length()  # 2^0..2^(k-1) <= n < 2^k，恰好 k 轮
        return rounds * body_count

    count = visit(root["program"], 1, ("program",))
    return str(count)
