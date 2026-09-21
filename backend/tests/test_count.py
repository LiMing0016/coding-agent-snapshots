from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def post(payload):
    return client.post("/api/analysis/count", json=payload)


# ---------- 成功语义 ----------

def test_op_counts_one():
    r = post({"n": "1", "program": {"type": "op"}})
    assert r.status_code == 200
    assert r.json() == {"count": "1"}


def test_seq_sums_items():
    program = {"type": "seq", "items": [{"type": "op"}, {"type": "op"}, {"type": "op"}]}
    r = post({"n": "10", "program": program})
    assert r.status_code == 200
    assert r.json() == {"count": "3"}


def test_empty_seq_is_zero():
    r = post({"n": "5", "program": {"type": "seq", "items": []}})
    assert r.json() == {"count": "0"}


def test_repeat_integer_times():
    program = {"type": "repeat", "times": 7, "body": {"type": "op"}}
    r = post({"n": "1", "program": program})
    assert r.json() == {"count": "7"}


def test_repeat_zero_times():
    program = {"type": "repeat", "times": 0, "body": {"type": "op"}}
    r = post({"n": "1", "program": program})
    assert r.json() == {"count": "0"}


def test_repeat_string_n():
    program = {"type": "repeat", "times": "n", "body": {"type": "op"}}
    r = post({"n": "42", "program": program})
    assert r.json() == {"count": "42"}


def test_double_rounds_are_floor_log2_plus_one():
    program = {"type": "double", "body": {"type": "op"}}
    # n=1..3 -> 2 轮 (1,2)；n=4..7 -> 3 轮 (1,2,4)
    assert post({"n": "1", "program": program}).json()["count"] == "1"
    assert post({"n": "2", "program": program}).json()["count"] == "2"
    assert post({"n": "3", "program": program}).json()["count"] == "2"
    assert post({"n": "4", "program": program}).json()["count"] == "3"
    assert post({"n": "7", "program": program}).json()["count"] == "3"
    assert post({"n": "8", "program": program}).json()["count"] == "4"


def test_double_body_runs_once_per_round_not_multiplied():
    # body 本身是 seq[op, op]，每轮 2 个单位操作；n=4 有 3 轮 -> 6
    body = {"type": "seq", "items": [{"type": "op"}, {"type": "op"}]}
    program = {"type": "double", "body": body}
    r = post({"n": "4", "program": program})
    assert r.json() == {"count": "6"}


def test_triangle_is_n_n_plus_1_over_2():
    r = post({"n": "100", "program": {"type": "triangle"}})
    assert r.json() == {"count": "5050"}


def test_triangle_at_n_one():
    r = post({"n": "1", "program": {"type": "triangle"}})
    assert r.json() == {"count": "1"}


def test_nested_structures_compose():
    # repeat(times=3, body=double(body=seq[op, op]))
    # n=8 -> double 4 轮 * 2 = 8；再 *3 = 24
    body = {"type": "seq", "items": [{"type": "op"}, {"type": "op"}]}
    program = {"type": "repeat", "times": 3,
               "body": {"type": "double", "body": body}}
    r = post({"n": "8", "program": program})
    assert r.json() == {"count": "24"}


def test_n_leading_zeros_accepted():
    r = post({"n": "00010", "program": {"type": "triangle"}})
    assert r.status_code == 200
    assert r.json()["count"] == "55"


def test_max_n_triangle_exact_big_integer():
    n = 10**18
    expected = n * (n + 1) // 2
    r = post({"n": str(n), "program": {"type": "triangle"}})
    assert r.json() == {"count": str(expected)}
    assert len(r.json()["count"]) == 36  # 500000000000000000500000000000000000


def test_max_times_exact():
    program = {"type": "repeat", "times": 10**6, "body": {"type": "triangle"}}
    r = post({"n": "1000000000000000000", "program": program})
    n = 10**18
    assert r.json()["count"] == str(10**6 * n * (n + 1) // 2)


def test_deep_nesting_does_not_expand():
    # 15 层 repeat(times=10^6) 包住 op（根为第 1 层，op 在第 16 层，合法），
    # 结果 10^90；树只有 16 个节点，瞬间闭形式算出。
    node = {"type": "op"}
    for _ in range(15):
        node = {"type": "repeat", "times": 10**6, "body": node}
    r = post({"n": "1", "program": node})
    assert r.status_code == 200
    assert r.json()["count"] == str(10**90)


def test_double_with_max_n():
    # 2^59 < 10^18 < 2^60 -> 60 轮
    r = post({"n": "1000000000000000000",
              "program": {"type": "double", "body": {"type": "op"}}})
    assert r.json() == {"count": "60"}


# ---------- 422：n 校验 ----------

def assert_422(payload, code, path):
    r = post(payload)
    assert r.status_code == 422, r.text
    assert r.json() == {"code": code, "path": path}


def test_missing_n():
    assert_422({"program": {"type": "op"}}, "missing_field", "$.n")


def test_n_integer_rejected():
    assert_422({"n": 10, "program": {"type": "op"}}, "type_error", "$.n")


def test_n_boolean_rejected():
    assert_422({"n": True, "program": {"type": "op"}}, "type_error", "$.n")


def test_n_empty_string():
    assert_422({"n": "", "program": {"type": "op"}}, "invalid_value", "$.n")


def test_n_non_decimal_strings():
    for bad in ["0", "-1", "1.0", "0x10", " 1", "1 ", "1e3", "+1"]:
        payload = {"n": bad, "program": {"type": "op"}}
        r = post(payload)
        assert r.status_code == 422, bad
        assert r.json()["path"] == "$.n", bad


def test_n_zero_and_above_max():
    assert_422({"n": "0", "program": {"type": "op"}}, "out_of_range", "$.n")
    assert_422({"n": "1000000000000000001", "program": {"type": "op"}},
               "out_of_range", "$.n")


def test_n_huge_string_does_not_blow_up():
    assert_422({"n": "9" * 100000, "program": {"type": "op"}},
               "out_of_range", "$.n")


# ---------- 422：program 与节点校验 ----------

def test_missing_program():
    assert_422({"n": "1"}, "missing_field", "$.program")


def test_program_not_object():
    assert_422({"n": "1", "program": "op"}, "type_error", "$.program")


def test_program_null():
    assert_422({"n": "1", "program": None}, "type_error", "$.program")


def test_missing_type():
    assert_422({"n": "1", "program": {}}, "missing_field", "$.program.type")


def test_unknown_node_type():
    assert_422({"n": "1", "program": {"type": "loop"}},
               "unknown_node", "$.program.type")


def test_type_non_string():
    assert_422({"n": "1", "program": {"type": 1}},
               "type_error", "$.program.type")


def test_unknown_field_on_op():
    assert_422({"n": "1", "program": {"type": "op", "x": 1}},
               "unknown_field", "$.program.x")


def test_triangle_rejects_body():
    assert_422({"n": "1", "program": {"type": "triangle", "body": {"type": "op"}}},
               "unknown_field", "$.program.body")


def test_seq_missing_items():
    assert_422({"n": "1", "program": {"type": "seq"}},
               "missing_field", "$.program.items")


def test_seq_items_not_array():
    assert_422({"n": "1", "program": {"type": "seq", "items": {}}},
               "type_error", "$.program.items")


def test_repeat_missing_body():
    assert_422({"n": "1", "program": {"type": "repeat", "times": 1}},
               "missing_field", "$.program.body")


def test_double_missing_body():
    assert_422({"n": "1", "program": {"type": "double"}},
               "missing_field", "$.program.body")


def test_repeat_times_bool_rejected():
    # bool 虽是 int 子类，但必须明确拒绝
    program = {"type": "repeat", "times": True, "body": {"type": "op"}}
    assert_422({"n": "1", "program": program}, "type_error", "$.program.times")


def test_repeat_times_float_rejected():
    program = {"type": "repeat", "times": 1.5, "body": {"type": "op"}}
    assert_422({"n": "1", "program": program}, "type_error", "$.program.times")


def test_repeat_times_null_rejected():
    program = {"type": "repeat", "times": None, "body": {"type": "op"}}
    assert_422({"n": "1", "program": program}, "type_error", "$.program.times")


def test_repeat_times_negative():
    program = {"type": "repeat", "times": -1, "body": {"type": "op"}}
    assert_422({"n": "1", "program": program}, "out_of_range", "$.program.times")


def test_repeat_times_too_large():
    program = {"type": "repeat", "times": 10**6 + 1, "body": {"type": "op"}}
    assert_422({"n": "1", "program": program}, "out_of_range", "$.program.times")


def test_repeat_times_bad_string():
    program = {"type": "repeat", "times": "0", "body": {"type": "op"}}
    assert_422({"n": "1", "program": program}, "invalid_value", "$.program.times")


def test_missing_field_beats_unknown_field_on_same_node():
    # 同一节点同时缺必填字段并带未知字段：先报缺失，再报未知（与顶层规则一致）。
    program = {"type": "repeat", "times": 1, "bogus": 0}
    assert_422({"n": "1", "program": program},
               "missing_field", "$.program.body")


def test_unknown_field_beats_child_errors():
    # 本节点的结构错误先于子树（先序）：double 带未知字段时，
    # 即使 body 也非法，先报本节点 unknown_field。
    program = {"type": "double", "body": {}, "bogus": 0}
    assert_422({"n": "1", "program": program},
               "unknown_field", "$.program.bogus")


# ---------- 422：先序路径与预算 ----------

def test_first_error_is_preorder_nested_path():
    # seq 第一个元素合法（triangle），第二个元素缺 type
    program = {"type": "seq", "items": [{"type": "triangle"}, {"x": 1}]}
    assert_422({"n": "3", "program": program},
               "missing_field", "$.program.items[1].type")


def test_error_inside_nested_repeat_body():
    program = {
        "type": "repeat", "times": 2,
        "body": {"type": "seq", "items": [
            {"type": "op"},
            {"type": "double"},  # 缺 body
        ]},
    }
    assert_422({"n": "3", "program": program},
               "missing_field", "$.program.body.items[1].body")


def test_depth_limit_root_is_depth_one():
    # 16 层合法（根=1），第 17 层触发 depth_limit。
    node = {"type": "op"}
    for _ in range(16):
        node = {"type": "double", "body": node}
    r = post({"n": "1", "program": node})
    assert r.status_code == 422
    assert r.json()["code"] == "depth_limit"
    assert r.json()["path"] == "$.program" + ".body" * 16


def test_depth_check_on_enter_before_node_count():
    # 超深且总节点也超限：路径在最深的进入点，且报 depth_limit。
    node = {"type": "op"}
    for _ in range(20):
        node = {"type": "double", "body": node}
    r = post({"n": "1", "program": node})
    assert r.json()["code"] == "depth_limit"
    assert r.json()["path"] == "$.program" + ".body" * 16


def test_node_limit_at_201st_node():
    # seq 是第 1 个节点，items[0..198] 为第 2..200 个（合法），
    # items[199] 是第 201 个 -> node_limit。
    items = [{"type": "op"} for _ in range(200)]
    program = {"type": "seq", "items": items}
    r = post({"n": "1", "program": program})
    assert r.status_code == 422
    assert r.json() == {"code": "node_limit", "path": "$.program.items[199]"}


def test_exactly_200_nodes_ok():
    items = [{"type": "op"} for _ in range(199)]  # seq 自身 1 + 199 = 200
    program = {"type": "seq", "items": items}
    r = post({"n": "1", "program": program})
    assert r.status_code == 200
    assert r.json()["count"] == "199"


def test_budget_checked_on_enter_before_field_errors():
    # 第 201 个节点本身还缺 type：进入时先撞 node_limit（199 个 op 占第 2..200）。
    items = [{"type": "op"} for _ in range(199)]
    items.append({})  # 第 201 个节点，缺 type
    program = {"type": "seq", "items": items}
    r = post({"n": "1", "program": program})
    assert r.json()["code"] == "node_limit"
    assert r.json()["path"] == "$.program.items[199]"


def test_top_level_unknown_field():
    assert_422({"n": "1", "program": {"type": "op"}, "extra": 0},
               "unknown_field", "$.extra")


def test_top_level_must_be_object():
    r = client.post("/api/analysis/count", json=[1, 2, 3])
    assert r.status_code == 422
    assert r.json() == {"code": "type_error", "path": "$"}


def test_malformed_json_body():
    r = client.post("/api/analysis/count", content=b"{not json",
                    headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert r.json() == {"code": "invalid_json", "path": "$"}


def test_empty_body():
    r = client.post("/api/analysis/count", content=b"",
                    headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert r.json() == {"code": "invalid_json", "path": "$"}
