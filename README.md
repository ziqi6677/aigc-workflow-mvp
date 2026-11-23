# AIGC Workflow MVP

一个最小可运行的 **AIGC 可视化工作流** 演示项目：在画布上拖拽节点、连线编排 AI 生成链路，后端按 DAG 拓扑排序依次执行。

> 概念对标 GitHub 开源项目 [**langgenius/dify**](https://github.com/langgenius/dify)（以及 [shrimbly/node-banana](https://github.com/shrimbly/node-banana)）。
> 本仓库只保留 Dify 工作流引擎的最小骨架：开始 / LLM / 模板 / 结束 四类节点、变量引用、拓扑执行、画布编排，便于二次扩展。

## 功能一览

- 🧩 **节点画布**：添加节点、拖拽移动、端口连线、点击连线删除
- 🔗 **四类节点**
  - `start` 开始节点：定义工作流初始输入
  - `llm` 大模型节点：提示词中用 `{{ 节点ID.output }}` 引用上游输出；内置离线 Mock，无 API Key 也能跑通
  - `template` 模板节点：文本拼接与变量替换
  - `end` 结束节点：汇总最终输出
- ⚙️ **执行引擎**：Kahn 拓扑排序，自动检测环路；逐节点记录状态、输出与耗时
- 💾 **JSON 导入 / 导出**：工作流可序列化为可移植的 JSON 文件
- 🖥️ **双入口**：Web 画布（FastAPI + 原生前端）与命令行（`run.py`）

## 目录结构

```
aigc-workflow-mvp/
├── app/
│   ├── __init__.py
│   ├── engine.py        # DAG 拓扑排序 + 节点执行引擎（无第三方依赖）
│   └── main.py          # FastAPI 接口 + 静态画布
├── examples/
│   ├── hello_poem.json  # 示例：输入主题 -> LLM 成诗 -> 输出
│   └── template_chain.json
├── static/
│   └── index.html       # 单页画布（原生 HTML/JS，无需构建）
├── tests/
│   └── test_engine.py   # 引擎单元测试
├── run.py               # CLI 运行入口
├── requirements.txt
└── README.md
```

## 快速开始

> **注意**：本项目是跑在你**自己电脑上**的程序，不是部署在云端的网站。
> 下面的 `http://127.0.0.1:8000` 是你本机的本地地址——必须先在本机启动服务，
> 这个地址才能打开；直接点开 README 里的链接、或在别人电脑上访问都是无效的。

### 1. 克隆代码并安装依赖

```bash
git clone https://github.com/ziqi6677/aigc-workflow-mvp.git
cd aigc-workflow-mvp

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 启动 Web 画布（在你自己的电脑上执行下面这条命令）

```bash
uvicorn app.main:app --reload --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 后，**再在本机浏览器**打开
<http://127.0.0.1:8000>：

1. 点击「载入示例」加载预置工作流
2. 在画布上调整节点、连线，或在右侧面板修改提示词
3. 点击「运行工作流」，右侧日志区查看每个节点的输出与最终结果
4. 「导出 JSON」保存当前编排，「导入 JSON」恢复

> 如果 8000 端口被占用，可换端口：`uvicorn app.main:app --port 8010`，
> 然后浏览器访问对应的 <http://127.0.0.1:8010>。

### 3. 命令行运行（不启动 Web 服务）

```bash
python run.py examples/hello_poem.json
```

### 4. 运行测试

```bash
pip install pytest
python -m pytest tests/ -q
```

## 工作流 JSON 格式

```json
{
  "nodes": [
    { "id": "start", "type": "start",    "position": {"x": 80, "y": 160},
      "config": { "input": "秋日傍晚的上海梧桐道" } },
    { "id": "llm1",  "type": "llm",      "position": {"x": 360, "y": 160},
      "config": { "prompt": "把下面的场景扩写成一句七言诗：{{ start.output }}",
                  "mock": true, "mock_style": "poem" } },
    { "id": "end",   "type": "end",      "position": {"x": 640, "y": 160},
      "config": { "output": "{{ llm1.output }}" } }
  ],
  "edges": [
    { "source": "start", "target": "llm1" },
    { "source": "llm1",  "target": "end" }
  ]
}
```

- `edges` 描述有向边；引擎会校验节点存在性并检测环路
- 变量引用语法：`{{ <上游节点ID>.output }}`

## 接入真实大模型

`WorkflowEngine` 支持注入自定义 LLM 客户端：

```python
from app.engine import WorkflowEngine

class OpenAIClient:
    def generate(self, prompt: str) -> str:
        # 在此调用 OpenAI / 国产大模型 API
        return "模型返回的结果"

engine = WorkflowEngine(workflow, llm_client=OpenAIClient())
result = engine.run()
```

当 LLM 节点配置 `mock: false` 时，引擎会调用注入的客户端；否则走离线 Mock。

## 与上游开源项目的差距（MVP 边界）

本仓库刻意**未实现**以下生产级能力，留作后续迭代方向：

- 条件分支（IF/ELSE）、循环迭代、并行节点与变量聚合
- 知识库检索（RAG）、HTTP 请求节点、代码沙箱节点
- 用户认证、工作流持久化存储、运行历史与可观测性
- 多模型供应商管理、API Key 加密与发布为对外 REST API

## License

MIT
