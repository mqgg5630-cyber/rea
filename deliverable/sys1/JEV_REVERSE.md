# Jev（TypeSafe System One）逆向报告

Jev 是 TypeSafe 托管的 System One 推理服务，`https://api.typesafe.ai/v1/systemone`。
Laya 把自己定位成它的**离线替身 + 超集**：同一套 choice/score/noul 语义，一段本地
encoder 前向，外加 `LAYA_JEV_STRICT=1` 的严格兼容投影。

本报告依据：`docs.typesafe.ai/api/system-one`、`/concepts/system-one`、laya 的
`docs/http-api.md` 与 `laya/serve.py` 的 strict 投影实现、`laya/confidence.py` 的
`jev_confidence`。

---

## 1. 端点与鉴权

```http
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <TYPESAFE_API_KEY>
Content-Type: application/json
```

* `model`: `"jev-latest"`（解析到具体版本，如 `jev-1.13.0`）；
* 可选 header：`TypeSafe-Danger-Zone-Long-Context: true`（超长上下文）、
  `TypeSafe-Danger-Zone-Images: true`（图片资产）；
* 响应里回显**实际** `model`，不是别名。

---

## 2. 请求体

```json
{
  "model": "jev-latest",
  "state": "文本 | 对象 | 数组",
  "questions": {
    "team": {
      "type": "choice",
      "instructions": "Which team?",
      "criteria": {"billing": "payments and refunds", "technical": "bugs and outages"}
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgent?",
      "criteria": ["low", "normal", "high"]
    },
    "churn": {"type": "noul", "instructions": "Threatens to cancel?"}
  }
}
```

| 类型 | `criteria` | 选项数 | 语义 |
|---|---|---|---|
| `choice` | `{选项: 描述}`（有序） | 2–20（官方文档）；宿主上限 255 | 分类，返回标签 + 概率 |
| `score` | 有序数组，2–10 个等级 | 2–10 | 返回**期望分**（可为小数）+ `legend` |
| `noul` | 不需要（固定 true/false） | 2 | 二元判断，返回 P(true) |
| `box` | 文档中的边界框/检测类型 | — | 视觉任务用，文本逆向不涉及 |

限制与定价（官方文档）：

* 单请求 64k token（state + questions）；其中 state + 最长 question ≤ 32k；
* 超出预算不会报错，会截断——所以"模型没看见"和"模型判断错"在线上很难区分；
* $0.042 / 1M input token，按输入计费，输出 token 恒为 0。

---

## 3. 响应体

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "team":   {"type": "choice", "choice": "billing",
               "confidence": 0.87, "probabilities": {"billing": 0.91, "technical": 0.09}},
    "urgency":{"type": "score", "score": 1.86,
               "legend": {"0": "low", "1": "normal", "2": "high"},
               "confidence": 0.78, "probabilities": {"0": 0.01, "1": 0.12, "2": 0.87}},
    "churn":  {"type": "noul", "noul": 0.976}
  },
  "usage": {"input_tokens": 214, "output_tokens": 0}
}
```

要点：

* `answers` 的键 = 请求里 `questions` 的键；每题必带 `type` 判别字段；
* `choice`、`score` 有 `probabilities` 与 `confidence`；`noul` **没有** `confidence`、
  没有 `probabilities`，只有 `noul`；
* `score` 是浮点期望值，`legend` 的键是字符串下标；
* 没有 `routing`、没有 `model` 内部信息、没有逐 token 输出——这是"决策 API"而不是聊天 API。

---

## 4. 置信度的真实含义

Jev 的 `confidence` 不是 softmax 最大值，而是按题型定义的：

```text
choice: (p_max - 1/n) / (1 - 1/n)        # 扣掉均匀基线后的相对置信度
score : max(0, 1 - Σ p_i·|i - mode| / uniform_spread)
noul  : |2·p_true - 1|                   # 距离 0.5 的绝对偏移
```

Laya 的 `laya/confidence.py::jev_confidence` 逐字实现了这三条（choice/score 与上面一致，
noul 走二项），并在答案里以 `x_jev_confidence` 暴露——**只在 `LAYA_JEV_STRICT=1` 之外**，
strict 模式的 `confidence` 用的是它自己的定义（Laya 的熵），这点必须注意：
**strict 只保证字段形状，不保证数值口径**。

`docs/http-api.md` 明确指出：三个数不可互换——

1. `answer_confidence = max(p)`：温度缩放与 ECE 校准的对象；
2. `confidence`：choice/score 是归一化熵 `1 - H/log k`，noul 是 `max(p,1-p)`；
3. `x_jev_confidence`：Jev 公式，只用于对表。

拿 Jev 的阈值直接闸 Laya 的 `confidence` 是**已知会反向**的错误（laya #302：
从 Jev 迁来的阈值必须重新按 held-out 数据标定）。

---

## 5. 与 Laya 的差异表

| 维度 | Jev（托管） | Laya（本地） |
|---|---|---|
| 打分器 | 云端私有模型 | ModernBERT / mmBERT 编码器 |
| 输出 | 同一套 typed answers | 同左 + `routing`、`usage`、`act_probability`、`x_jev_confidence` |
| 选项上限 | 2–20（文档）/255 | choice 2–255，单题选项受 `head_max_len` 限制 |
| 置信度 | 公式见 §4 | 多给一个校准过的 `answer_confidence` |
| 批量 | 单请求 | `POST /v1/systemone/batch` + 自动切块 |
| 温度 | 不可见 | 按 checkpoint/桶发布，可覆盖 |
| 严格兼容 | — | `LAYA_JEV_STRICT=1` 投影成 §3 的形状 |
| 计费/联网 | $0.042/1M input | 0，完全离线 |
| 超长文本 | danger-zone header | `max_len` 到 8192，超出截断并报告 `truncated` |

严格投影的实现（`laya/serve.py::_project_jev_strict`）做的正是：

* 删掉 `routing`/`sys1`/`action`/`x_jev_confidence`；
* `usage` 只留 `{input_tokens, output_tokens}`；
* 每个 answer 只留 §3 列出的键；
* 保证 `score` 的 `criteria` 是纯字符串（结构化等级会被渲染成 JSON 文本，见
  `_decode_answers` 的注释）。

---

## 6. 用 agent 替代 Jev 调用

Jev 的价值在于"给一个状态和几个选项，拿回一个带概率的决策"。这个契约不需要
托管模型才能满足：

1. **同样的请求**：`state` + `questions`（choice/score/noul）；
2. **agent 打分**：对每个选项给出一个实数（nats 证据，0 = 中立）；
3. **同样的解码**：温度 → softmax → `choice/score/noul` + `confidence`；
4. **同样的响应**：`{model, answers, usage}`，可选 strict。

`code/sys1` 就是这条路径：

```bash
# 1) agent 只出 logits：sys1 返回 laya 渲染好的 prompt 和 schema
python -m sys1 mcp            # MCP stdio: system_one(engine="agent") 先返回 needs_agent_scores

# 2) agent 把每个选项的分数交回：解码完全用 laya 的数学
python -m sys1 decide --state @case.txt --questions @q.json \
                      --agent-logits @logits.json --json
```

`results/sys1/AGENT_DEMO.md` 里有 6 个多语言状态的完整结果（英文退款威胁、中文重复扣费、
西语退款、德语宕机、JSON state、模糊 noul），全部由对话中的 agent 打分、由 laya 的
解码器出答案，**没有任何网络请求**（`selfcheck.py` 会在 `socket.create_connection`
被打断的情况下重跑一遍决策来证明这一点）。

---

## 7. 复现清单

| 断言 | 证据 |
|---|---|
| 响应形状（single / strict） | `selfcheck.py` 的 `HTTP Jev contract`、`system_one` 的 `project_jev_strict` 检查 |
| noul 无 confidence | `project_jev_strict` 单测 + `AGENT_DEMO` 输出 |
| choice 置信度公式 | `jev_confidence` 单测：p=(0.5,0.25,0.25) → 0.25 |
| score 置信度公式 | p=(0.2,0.6,0.2) → 0.4 |
| 批量形状 | `POST /v1/systemone/batch` → `{results, total_usage}` |
| 离线 | 依赖审计（`serve.py` 之外不允许 `urlopen`/`requests`/`httpx`）+ socket 阻断测试 |
