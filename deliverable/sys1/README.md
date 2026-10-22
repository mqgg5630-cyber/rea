# sys1 — 用 agent 本身做决策引擎（不调用任何 API）

`laya` 的协议 + 解码 + 路由，被完整复现成一个**零依赖、纯标准库、离线**的 Python
服务；它的打分器可以是你（当前对话里的 agent），而不是 laya 的 checkpoint，也不是
任何托管 LLM API。

```text
             ┌──────────────────────────────────────────────────────────┐
  state ───► │ sys1.protocol   渲染 laya 的 [CLS]…[SEP][MASK]…[SEP]…[SEP] │
  questions  │ sys1.lang       路由：english / multilingual / typed      │
             ├──────────────────────────────────────────────────────────┤
             │ 打分器（可替换）                                          │
             │   local : 词法/量表打分器（离线、确定性）                 │
             │   agent : 由 agent 给出每个选项的证据分（nats）           │
             ├──────────────────────────────────────────────────────────┤
             │ sys1.decode     温度 → softmax → choice/score/noul        │
             │                 confidence / answer_confidence / jev_conf │
             └──────────────────────────────────────────────────────────┘
                       │ HTTP (Jev 兼容)      │ MCP stdio        │ CLI
```

没有 `torch`、没有 `numpy`、没有 `requests`——`selfcheck.py` 会在
`socket.create_connection` 被替换成抛异常的情况下重跑一次决策，证明它真的不需要网络。

---

## 目录

| 路径 | 内容 |
|---|---|
| `code/sys1/sys1/protocol.py` | state 序列化、问题归一化、laya 序列/提示词渲染、token 预算 |
| `code/sys1/sys1/lang.py` | 脚本检测、拉丁语猜测、路由优先级（800 个 fixture 上 96.3% 同判） |
| `code/sys1/sys1/decode.py` | 温度表、softmax、三类答案、三种置信度、abstention 闸门、Jev strict 投影 |
| `code/sys1/sys1/scoring.py` | 离线词法打分器（13 组 cue + 量纲锚定） |
| `code/sys1/sys1/engine.py` | 路由 → 打分 → 解码；`local` / `agent` / `auto` 三种引擎 |
| `code/sys1/sys1/serve.py` | Jev 兼容 HTTP：`/v1/systemone`、`/batch`、`/health`、中文演示页 |
| `code/sys1/sys1/mcp.py` | MCP over stdio：`system_one` 等 4 个工具 |
| `code/sys1/sys1/cli.py` | `decide` / `route` / `prompt` / `serve` / `mcp` / `eval` / `selfcheck` |
| `code/sys1/selfcheck.py` | 21 项离线自检（含真实 golden logits 的解码一致性） |
| `code/sys1/evaluate.py` | 证据报告：解码一致、路由一致、与 checkpoint 一致率、校准、延迟 |
| `code/sys1/demo_agent.py` | 6 个多语言案例：agent 打分 → laya 解码 |
| `results/sys1/EVAL.md` | 证据报告（自动生成） |
| `results/sys1/SELFCHECK.md` | 自检回执（自动生成） |
| `results/sys1/AGENT_DEMO.md` | agent 决策演示（自动生成） |
| `deliverable/sys1/LAYA_REVERSE.md` | laya 逆向报告 |
| `deliverable/sys1/JEV_REVERSE.md` | Jev（TypeSafe System One）协议逆向 |
| `deliverable/sys1/LOCAL_BRIDGE.md` | 与本机（Windows 值守）打通的状态与步骤 |

---

## 30 秒上手

```bash
cd code/sys1

# 1) 离线自检（21 项，约 1 秒）
python3 selfcheck.py

# 2) 用 agent 的分数做决策（这就是"不调 API"的主路径）
python3 demo_agent.py

# 3) 起一个 Jev 兼容服务（默认 0.0.0.0:8000），浏览器打开就是中文演示页
python3 -m sys1 serve
curl -s localhost:8000/health

# 4) 给 MCP 客户端用（Claude Desktop / 任何 stdio MCP host）
python3 -m sys1 mcp
```

`python -m sys1 decide` 的两种用法：

```bash
# 本地词法引擎
python3 -m sys1 decide --state "I was charged twice, refund me today." \
  --questions @examples/ticket_questions.json

# agent 引擎：每个问题给 k 个数（0 = 中立，正数 = 支持该选项的证据）
python3 -m sys1 decide --state @examples/ticket_state.txt \
  --questions @examples/ticket_questions.json \
  --agent-logits @examples/ticket_agent_logits.json --json
```

MCP 里 `engine="agent"` 且未带 `agent_logits` 时，工具不会瞎猜：它返回
`status: needs_agent_scores`、laya 渲染好的 prompt、选项顺序和确切 schema，agent 填完
再调用一次即可。这样"决策"确实发生在 agent 侧，而一致性由 sys1 保证。

---

## 证据（全部本地生成，可复跑）

`python code/sys1/evaluate.py` → `results/sys1/EVAL.md`：

| 维度 | 结果 |
|---|---|
| 解码一致（真实 checkpoint logits → 答案） | **87/87**，容差 1e-4（概率、`confidence`、`answer_confidence`） |
| 路由一致（800 个对抗 state，4115 条决策） | 脚本 100%、`is_english` 90.9%、`language` 86.0%、`route_model` **96.3%** |
| 与 checkpoint 的决策一致率（同 state/问题） | **76.8%**（choice 83.3/66.7/83.3%，noul 90.9/54.5/81.8%，score MAE 0.40） |
| 本机词法引擎校准 | held-out ECE **0.177**（T=1）；拟合温度反而 0.233，故不发布 calibration.json |
| 延迟（CPU，3 题/决策） | p50 **1.74 ms**、p95 **2.06 ms**、**575 决策/秒** |
| 自检 | **21/21 PASS**，含 HTTP 契约、MCP、socket 阻断、确定性 |

### agent 引擎的实际输出（`AGENT_DEMO.md` 摘要）

| 案例 | 问题 | 决策 | 置信度 |
|---|---|---|---|
| 英文退款威胁 | department | `billing` | 0.904 |
| 英文退款威胁 | urgency (score 0-2) | 1.86 | 0.869 |
| 英文退款威胁 | churn (noul) | P=0.976 | 0.976 |
| 中文重复扣费 | department | `billing` | 0.946 |
| 西语退款 | intent | `refund` | 0.914 |
| 德语宕机 | department | `technical` | 0.948 |
| JSON 工单 | department | `billing` | 0.949 |
| 模糊 noul | churn | P=0.007 | 0.993 |

这些数字不是"模型准确率"，而是**协议在 agent 打分下能产出什么形状的结果**：
可复现、可审计、每题都有分布。

---

## 诚实的边界

* 没有加载 laya 的 421M/322M 权重（沙箱无 GPU）。因此 76.8% 是**与 checkpoint 的
  一致性**，不是准确率；解码一致 87/87 才是"逆向正确"的硬证据。
* `local` 词法引擎是**兜底**，不是模型：它靠 cue 词表 + 量纲锚定，遇到训练分布外的
  表达会退化。要更准，就把 `engine="agent"` 或换成任意能打分的函数。
* 校准只基于 45 个 golden 案例（87 行），样本太小；因此默认 T=1，不发布拟合温度。
* Jev 的托管模型权重不可见，本报告只逆向**协议与数值口径**，不猜测其内部结构。

---

## 为什么这算"不调 API"

1. 决策来自 agent 对选项的判断（数字写在请求里），或来自本地词法打分器；
2. 解码是纯 Python 算术，无外部调用；
3. HTTP/MCP 都只监听本机/stdio，`selfcheck.py` 在禁用 socket 时仍通过；
4. 依赖审计：`sys1/*.py` 里除 `serve.py` 的测试外，不允许出现 `urlopen`/`requests`/`httpx`。
