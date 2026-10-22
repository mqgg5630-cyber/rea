# laya 逆向报告

对象：`NandhaKishorM/laya` v0.4.13（commit `6f0496f`，Apache-2.0），Python 包 `laya/`，
以及 `laya-dotnet/tests/Laya.Tests/golden/` 下 110 个 golden fixture。

一句话：**Laya 不是聊天模型，而是一个"判题器"**——把 state 和一组带类型的
问题（choice / score / noul）编码成一条序列，用 ModernBERT/mmBERT 编码器做一次
前向，在选项位置的 `[MASK]` 隐状态上取 logits，再经温度缩放 + softmax 直接给出
答案与概率。没有生成、没有 token 循环、没有 tool call。

---

## 1. 三个 checkpoint

| 名称 | 骨干 | 上下文 | 用途 |
|---|---|---|---|
| `laya` (`convaiinnovations/laya`) | ModernBERT-large，421M | 512 | 英文 |
| `laya-multilingual` | mmBERT-base，322M | 1024（可配到 8192） | 100+ 语言，非英文默认 |
| `laya-typed-decisions` | 421M | 1024 | 多问题、结构化 workflow |

`Router` 按需加载（`Router()` 本身不下载权重）；`register(name, source)` 可注册私有
checkpoint，`revision`/digest 可锁定版本。0.4.0 起 `default` 是 multilingual，未知语言
不再落到英文模型。

### 路由优先级（`laya/router.py`，文档 `docs/routing.md` 同步）

1. `model=` 直接指定（非法名字抛 `ValueError`，不会静默回落）；
2. `task=`（含 `typed-decisions`）；
3. `auto_task_detection=True` 且问题 id 集合精确命中某个已知 workflow → `typed-decisions`；
4. `lang=`（`en/eng/english` → english，其余受支持语言 → multilingual；`C/POSIX/und/zxx/mul` 等**不作为证据**，继续往下走）；
5. 调用级 `lang_guess=`，再退到 `Router(lang_guess=...)`；
6. 内置脚本/语言检测；
7. `default`（multilingual）。

`Router.route()` 不加载权重、不推理，只返回 `RouteDecision{model, repo, reason, detection, workflow}`；
`reason` 是给人看的（例如 `"non-Latin script (han, 100% of letters); the English checkpoint cannot read it"`）。

### 语言检测（`laya/lang.py`）

* 先按 Unicode 区块统计脚本占比，得到 `script` + `script_profile`；
* 拉丁脚本再做**停用词 + 变音符频率**的启发式猜测，要求至少两票优势，否则
  `language_undecided=True`；
* 非拉丁脚本不猜具体语言，直接判 `is_english=False`；
* `LANG=C`、`POSIX`、`und`、`zxx`、`mul` 被显式当作"无语言证据"；
* 全大写（喊叫）文本有单独的停用词门槛（`_SHOUTED_MIN_STOPWORD=4`），避免把
  "REFUND NOW" 当成非英文。

仓库自带基准很说明问题：英文 checkpoint 在非拉丁文本上接近随机（Hindi 0.100、
Korean 0.103、Tamil 0.113，20 选项随机基线 0.050），拉丁语系明显更好
（French 0.487、Spanish 0.480）。所以"路由错了"不是精度问题，是能力边界。

---

## 2. 请求协议

`POST /v1/systemone`（本地 FastAPI，见 §5）：

```json
{
  "model": "multilingual",
  "state": "文本 / JSON 对象 / 消息数组",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team owns this ticket?",
      "criteria": {"billing": "invoices, refunds", "technical": "bugs, outages"}
    },
    "urgency": {"type": "score", "instructions": "How urgent?", "criteria": ["low", "normal", "high"]},
    "churn":   {"type": "noul", "instructions": "Does the customer threaten to cancel?"}
  }
}
```

* `state` 三种形态统一 `serialize_state()`：字符串原样；dict 按键排序后 JSON 化；list 视为
  多轮消息（`role: content`）。
* `choice`：`criteria` 是 `选项 -> 描述` 的有序映射，**键就是返回的标签**；选项数 2–255
  （Jev 托管版文档写 2–20）。
* `score`：`criteria` 是有序数组，2–10 个等级，返回的是**期望分**（可为小数）和 `legend`。
* `noul`：二元判断，固定 `false/true` 两个选项，返回 `noul` = P(true)。
* 可选：`option_order`（打乱选项以消除位置偏差，解码时再还原）、`max_len`、`head_max_len`、
  `min_confidence`、`task`、`lang`、`lang_guess`。

---

## 3. 序列构造（`laya/common.py:157` `build_sequence`）

```text
[CLS] <type> question: <instructions> [SEP]
      [MASK] <opt0>  [MASK] <opt1>  ...  [MASK] <optN>
      [SEP] <state> [SEP]
```

细节（都是逆向时容易踩的）：

* 每个选项前放一个 `[MASK]`，**读的是该 `[MASK]` 位置的隐状态**，不是选项文本的池化；
* 选项渲染：choice 为 `label: description`，score 为 `level i: criterion`，noul 为
  `false: … / true: …`；
* 头部预算默认 `head_max_len=192`：指令 + 选项；单个选项最多 48 token，超长从右侧截；
  选项多到放不下时，尾部选项会被丢弃（`collapsed_options`），布局在截断**之前**算好，
  避免最后一个存活选项"吞掉"被丢弃选项的位置；
* state 只拿剩下的 `max_len - head - 1` 个 token；默认**右截断**（保留开头），
  `truncate_left=True` 时保留结尾（聊天/工单更适合）；
* `return_truncation_stats=True` 才告诉你 `state_tokens_dropped` / `truncated`——issue #174
  的教训：调用方无法用字符阈值猜这个预算；
* `option_layout="parallel"`（transformers ≥5）把选项做成并行 span，顺序无关。

---

## 4. 解码数学（`laya/agent.py:1332` `_decode_answers`）

对每个问题：

```text
z = logits_at_masks / T[bucket]          # 温度缩放
p = softmax(z)                            # 数值稳定版
p = unpermute(p, option_order)            # 还原选项顺序
```

* `choice`：`argmax` + 全量 `probabilities`（键 = criteria 键）；
* `score`：`score = Σ i·p_i`（期望等级，小数），`legend` 把下标映射回等级文本；
* `noul`：`noul = p[1]`（P(true)），两个选项时 `max(p)` 与 `max(p, 1-p)` 等价。

三个**不能互换**的置信度（`laya/common.py`、`docs/http-api.md`）：

| 字段 | 定义 | 用途 |
|---|---|---|
| `answer_confidence` | `max(p)` | 温度缩放/ECE 校准的那个量，跨题型可比的闸门 |
| `confidence` | `choice/score`：归一化熵 `1 - H/log k`；`noul`：`max(p_true, 1-p_true)` | 旧字段，语义随题型变化 |
| `x_jev_confidence` | Jev 公式（见 Jev 报告 §4） | 只用于和 Jev 对表，**不要**拿 Jev 阈值闸 Laya 的熵 |

温度表（发布值）：

* english：`[1.6369, 1.2514, 1.9834]` + 按选项数的桶
  `{choice:2 1.9064, choice:3-5 1.7602, choice:6-10 1.0, choice:11+ 0.1006→clamp 0.5,
  score:3-5 1.2514, noul:2 1.9834}`；
* multilingual：全 1.0；typed-decisions：`[1.0148, 1.0374, 1.0575]`；
* 桶键 `"{type}:{2|3-5|6-10|11+}"`（`common.py:847` `temp_bucket`）。

两个已公开的坑，值得写进任何复现实现：

* **#394**：`choice:11+` 发布温度 0.1006 会把 logits 放大约 10 倍，0.24 的 top
  probability 被发布成 0.99。代码里 `TEMP_MIN=0.5` 强制夹住：仍锐化 2 倍，但不再
  把抛硬币说成确定。`clamp_temperature` 还拒绝 bool/NaN/inf。
* **#302**：从 Jev 迁过来的 `min_confidence` 阈值会在 Laya 的熵置信度上**反向**工作，
  因为两者分布不同；迁移必须重新按 held-out 数据选阈值。

---

## 5. 服务面（`laya/serve.py`）

单个 `POST /v1/systemone` 的实际顺序：

1. 可选 Bearer 鉴权；
2. `_admit`：并发超过 `LAYA_MAX_CONCURRENT`（默认 16）直接 503；
3. 体积/形状检查：缺 `questions` 400、超限 413、选项数/参数非法 422、孤立代理对 400；
4. `_resolve_model`：已发布的 Hub id 锁定；`convaiinnovations/laya`、`jev-*` 走自动路由；
   传本地路径或未发布 id → 422；
5. token 预算 ≤ `LAYA_MAX_TOKEN_BUDGET`（8192）；
6. 推理在一把 `asyncio.Lock` 后串行（编码器不是线程安全的）；
7. 响应头带 `Server-Timing: inference;dur=…` 与 `X-Inference-Time-Ms`；
8. 错误：`HTTPException` 原样、`ValueError`→422、其他→500 `inference failed`
   （traceback 只进服务端日志）。

默认响应是"完整 Laya 载荷"（含 `routing`、`usage`、`answer.action.act_probability`、
每题的 `x_jev_confidence`）。`LAYA_JEV_STRICT=1` 时投影成 **严格的 Jev 形状**：
只留 `{model, answers, usage}`，choice 为 `{type, choice, confidence, probabilities}`，
score 为 `{type, score, confidence, probabilities, legend}`，noul 为 `{type, noul}`。

`POST /v1/systemone/batch`：`{states, questions}`，同样控制参数；按
`LAYA_MAX_BATCH_TOKENS`（131072）自动切块，返回 `{results: [...], total_usage}`。
`diagnostics` 之类"只为本地调试"的出参一律 422（避免线上沉默地改变返回形状）。

`/health` 返回已加载 checkpoint、revision、device、CPU fallback 计数。

---

## 6. 其它值得逆向的模块

* `laya/confidence.py`：`check_min_confidence`（标量或 `{bucket: 阈值}` 映射）、
  `resolve_min_confidence`（桶 → `default` → 0.0）、`flag_low_confidence`
  （阈值 0.0 会**清掉**旧标记，#910）、`apply_confidence_gate`
  （给每题加 `abstention ∈ passed|abstained|unevaluated` + `abstention_threshold`，
  未配置时一个字段都不写）。
* `laya/shortlist.py`：选项很多（几百个）时先用 embedding 余弦筛 K=20，再走
  `predict_tournament`（分组 16），结果里带 `shortlist{labels,scores,k,n,passthrough}`；
  被筛掉的选项没有 `option_order`（会 `RuntimeWarning`）。
* `laya/structured.py`：把 Pydantic/JSON Schema 编译成 choice/score/noul 问题。
* `docs/staged-adoption.md`：shadow → 对比（分歧≠错误，抽样人工看）→ 用 held-out
  证据定策略（记录 owner/method，`laya-evals run --json` 固化
  `config.revisions`/`dataset_sha256`/`questions_sha256`/阈值）→ 有界放量 + 回滚。
  这是"决策引擎进生产"的正确路径，比单看 accuracy 有用。

---

## 7. 我们复现/验证了什么

| 项 | 结果 | 方法 |
|---|---|---|
| 解码 1e-4 级一致 | **87/87** | 用 golden 里的真实 logits，跑 `sys1` 的 softmax/温度/`confidence` |
| 路由一致 | 脚本 100%、`is_english` 90.9%、`language` 86.0%、`route_model` 96.3% | 800 个对抗 state、4115 条决策 |
| 与 checkpoint 的决策一致率 | 76.8%（score MAE 0.40） | 同样 state/questions，比较 top-1 与期望分 |
| CPU 延迟 | p50 1.74 ms、p95 2.06 ms、575 决策/秒 | 3 题/决策，纯 Python |

**没有做**：加载 421M/322M 权重做前向（沙箱无 GPU，且不是本任务目标）。因此
"一致率"是**与 checkpoint 的教师一致性**，不是准确率；它衡量协议复现得对不对。

---

## 8. 对"用 agent 替代模型"的含义

Laya 的决策质量来自两件事：**协议**（怎么问、怎么读）和**权重**（谁打分）。
本报告证明协议可以完全复现；权重这一层，`sys1` 允许把 `[MASK]` 位置的 logits
换成 agent 自己对每个选项给出的证据分（nats），后面温度、softmax、`choice/score/noul`、
`confidence`、`abstention` 全部保持 Laya 的语义。也就是说：**换掉打分器，不换判题规则**。
