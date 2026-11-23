"""
AIGC 工作流最小执行引擎（MVP）

概念对标开源项目 Dify (github.com/langgenius/dify)：
- 工作流 = 由节点 (node) 和连线 (edge) 组成的有向无环图 (DAG)
- 节点类型：start / llm / template / end
- 引擎按拓扑排序依次执行，上游节点的输出通过 `{{ node_id.output }}`
  模板变量注入下游节点

本模块不依赖任何第三方库，可独立被 CLI、测试或 Web 服务调用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# 异常定义
# --------------------------------------------------------------------------- #


class WorkflowError(Exception):
    """工作流定义或执行期错误。"""


class CycleDetectedError(WorkflowError):
    """图中存在环，无法拓扑排序。"""


# --------------------------------------------------------------------------- #
# 运行结果数据结构
# --------------------------------------------------------------------------- #


@dataclass
class NodeResult:
    node_id: str
    node_type: str
    status: str  # success / error
    output: Any = None
    error: Optional[str] = None
    elapsed_ms: float = 0.0


@dataclass
class RunResult:
    status: str  # success / error
    final_output: Any = None
    node_results: List[NodeResult] = field(default_factory=list)
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
# 模板变量解析
# --------------------------------------------------------------------------- #

_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\-]+)\.([a-zA-Z0-9_\-]+)\s*\}\}")


def _resolve_template(text: str, outputs: Dict[str, Dict[str, Any]]) -> str:
    """把 `{{ node_id.output }}` 形式的变量替换为上游节点真实输出。"""

    def _sub(match: re.Match[str]) -> str:
        node_id, attr = match.group(1), match.group(2)
        if node_id not in outputs:
            raise WorkflowError(f"引用了不存在的上游节点: {node_id}")
        value = outputs[node_id].get(attr)
        if value is None:
            return ""
        return str(value)

    return _VAR_PATTERN.sub(_sub, text)


# --------------------------------------------------------------------------- #
# 引擎本体
# --------------------------------------------------------------------------- #


class WorkflowEngine:
    """
    传入 workflow dict，执行并返回每一步结果。

    workflow 结构::

        {
          "nodes": [
            {"id": "start", "type": "start", "config": {"input": "你好"}},
            {"id": "llm1",  "type": "llm",   "config": {"prompt": "把这句话改写成诗: {{ start.output }}",
                                                        "mock": True}},
            {"id": "end",   "type": "end",   "config": {"output": "{{ llm1.output }}"}}
          ],
          "edges": [
            {"source": "start", "target": "llm1"},
            {"source": "llm1",  "target": "end"}
          ]
        }
    """

    def __init__(self, workflow: Dict[str, Any], llm_client: Optional[Any] = None):
        self.workflow = workflow
        self.llm_client = llm_client  # 可注入真实 LLM 客户端；为空时走 mock
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._adj: Dict[str, List[str]] = {}
        self._validate()

    # ----------------------------- 图校验 ----------------------------- #

    def _validate(self) -> None:
        nodes = self.workflow.get("nodes", [])
        edges = self.workflow.get("edges", [])
        if not nodes:
            raise WorkflowError("工作流不能为空：至少需要一个节点")

        for node in nodes:
            if "id" not in node or "type" not in node:
                raise WorkflowError("每个节点必须包含 id 和 type")
            self._nodes[node["id"]] = node
            self._adj.setdefault(node["id"], [])

        for edge in edges:
            src, tgt = edge.get("source"), edge.get("target")
            if src not in self._nodes or tgt not in self._nodes:
                raise WorkflowError(f"连线引用了不存在的节点: {src} -> {tgt}")
            self._adj[src].append(tgt)

        # 节点类型合法性
        allowed = {"start", "llm", "template", "end"}
        for node in nodes:
            if node["type"] not in allowed:
                raise WorkflowError(f"不支持的节点类型: {node['type']}")

    def _topological_order(self) -> List[str]:
        """Kahn 拓扑排序；检测到环时抛 CycleDetectedError。"""
        indegree: Dict[str, int] = {nid: 0 for nid in self._nodes}
        for src, targets in self._adj.items():
            for tgt in targets:
                indegree[tgt] += 1

        queue = [nid for nid, deg in indegree.items() if deg == 0]
        order: List[str] = []
        while queue:
            current = queue.pop(0)
            order.append(current)
            for nxt in self._adj[current]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)

        if len(order) != len(self._nodes):
            raise CycleDetectedError("工作流图中存在环，无法执行")
        return order

    # ----------------------------- 节点执行 ----------------------------- #

    def _run_start(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": config.get("input", "")}

    def _run_llm(self, config: Dict[str, Any], resolved_prompt: str) -> Dict[str, Any]:
        # 真实 LLM：注入了 llm_client 且未强制 mock 时调用
        if self.llm_client is not None and not config.get("mock", False):
            reply = self.llm_client.generate(resolved_prompt)
            return {"output": reply}
        # 离线 mock：保证无 API Key 也能跑通完整链路
        mock_style = config.get("mock_style", "echo")
        if mock_style == "poem":
            output = f"【模拟成诗】\n{resolved_prompt}\n—— 韵脚悠然，意境自成。"
        else:
            output = f"[Mock LLM] 已处理输入: {resolved_prompt}"
        return {"output": output}

    def _run_template(self, config: Dict[str, Any], resolved_text: str) -> Dict[str, Any]:
        return {"output": resolved_text}

    def _run_end(self, config: Dict[str, Any], resolved_text: str) -> Dict[str, Any]:
        return {"output": resolved_text}

    def _execute_node(self, node: Dict[str, Any], outputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        ntype = node["type"]
        config = node.get("config", {})

        if ntype == "start":
            return self._run_start(config)

        if ntype == "llm":
            prompt = _resolve_template(config.get("prompt", ""), outputs)
            return self._run_llm(config, prompt)

        if ntype == "template":
            text = _resolve_template(config.get("text", ""), outputs)
            return self._run_template(config, text)

        if ntype == "end":
            text = _resolve_template(config.get("output", ""), outputs)
            return self._run_end(config, text)

        raise WorkflowError(f"未实现的节点类型: {ntype}")

    # ----------------------------- 入口 ----------------------------- #

    def run(self) -> RunResult:
        import time

        outputs: Dict[str, Dict[str, Any]] = {}
        results: List[NodeResult] = []
        final_output: Any = None

        try:
            order = self._topological_order()
            for nid in order:
                node = self._nodes[nid]
                started = time.perf_counter()
                try:
                    node_output = self._execute_node(node, outputs)
                    outputs[nid] = node_output
                    final_output = node_output.get("output")
                    results.append(
                        NodeResult(
                            node_id=nid,
                            node_type=node["type"],
                            status="success",
                            output=node_output.get("output"),
                            elapsed_ms=(time.perf_counter() - started) * 1000,
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - 引擎需要兜底收集错误
                    results.append(
                        NodeResult(
                            node_id=nid,
                            node_type=node["type"],
                            status="error",
                            error=str(exc),
                            elapsed_ms=(time.perf_counter() - started) * 1000,
                        )
                    )
                    return RunResult(
                        status="error",
                        final_output=None,
                        node_results=results,
                        error=f"节点 {nid} 执行失败: {exc}",
                    )

            return RunResult(status="success", final_output=final_output, node_results=results)

        except WorkflowError as exc:
            return RunResult(status="error", node_results=results, error=str(exc))
