#!/usr/bin/env python3
"""命令行入口：直接运行 examples 下的工作流 JSON，无需启动 Web 服务。

用法：
    python run.py examples/hello_poem.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.engine import WorkflowEngine


def main() -> int:
    if len(sys.argv) != 2:
        print("用法: python run.py <workflow.json>")
        return 1

    workflow_path = Path(sys.argv[1])
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))

    engine = WorkflowEngine(workflow)
    result = engine.run()

    for r in result.node_results:
        if r.status == "success":
            print(f"[OK]   {r.node_id} ({r.node_type}) -> {r.output}")
        else:
            print(f"[FAIL] {r.node_id} ({r.node_type}) -> {r.error}")

    print("\n最终输出:", result.final_output if result.status == "success" else result.error)
    return 0 if result.status == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
