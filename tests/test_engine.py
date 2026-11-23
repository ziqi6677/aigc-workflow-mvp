"""引擎单元测试：拓扑排序、变量替换、环检测、离线 mock 运行。

运行：
    python -m pytest tests/ -q
"""

import json
from pathlib import Path

from app.engine import WorkflowEngine, WorkflowError, CycleDetectedError

BASE = Path(__file__).resolve().parent.parent


def load_example(name: str) -> dict:
    return json.loads((BASE / "examples" / name).read_text(encoding="utf-8"))


def test_run_hello_poem_offline():
    result = WorkflowEngine(load_example("hello_poem.json")).run()
    assert result.status == "success"
    assert result.final_output is not None
    assert len(result.node_results) == 3
    assert [r.node_id for r in result.node_results] == ["start", "llm1", "end"]


def test_template_chain_passes_variables():
    result = WorkflowEngine(load_example("template_chain.json")).run()
    assert result.status == "success"
    assert "产品发布通知" in result.final_output


def test_cycle_is_detected():
    workflow = {
        "nodes": [
            {"id": "a", "type": "llm", "config": {"prompt": "x"}},
            {"id": "b", "type": "llm", "config": {"prompt": "y"}},
        ],
        "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
    }
    engine = WorkflowEngine(workflow)
    result = engine.run()
    assert result.status == "error"
    assert "环" in result.error


def test_missing_node_reference_raises():
    workflow = {
        "nodes": [{"id": "a", "type": "end", "config": {"output": "{{ ghost.output }}"}}],
        "edges": [],
    }
    result = WorkflowEngine(workflow).run()
    assert result.status == "error"


def test_invalid_node_type_raises():
    workflow = {"nodes": [{"id": "a", "type": "unknown", "config": {}}], "edges": []}
    try:
        WorkflowEngine(workflow)
        assert False, "应当抛出 WorkflowError"
    except WorkflowError:
        pass
