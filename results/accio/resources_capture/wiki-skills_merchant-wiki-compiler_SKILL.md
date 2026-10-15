---
name: merchant-wiki-compiler
description: |
  从已解析好的 md 文本，按八域本体 Schema v3 编译商家私域知识 Wiki（商品/店铺/客户/经营/平台/资产/接待/概念）。
  Use when: 编译商家wiki / 商家知识编译 / 按schema生成wiki / 本体wiki /
  从数据生成wiki / 商家知识结构化 / merchant wiki / compile wiki / ontology wiki / entity-concept wiki
version: 3.0.0
author: yinxi.zc
time: 2026-08-25 11:30
triggers:
  - 编译商家wiki
  - 商家知识编译
  - 本体wiki
  - merchant wiki
  - compile wiki
  - 从数据生成wiki
  - 按schema编译
install_method: upload
share_id: 996e6c96ca941419e505abcc8914cd4
install_source: local
enabled_at: 1787629958515
---

# Merchant Wiki Compiler

从已解析好的 md 文本，按八域本体 Schema v3 编译出结构化商家私域知识 Wiki。八域：商品 / 店铺 / 客户 / 经营 / 平台 / 资产 / 接待 / **概念**。概念域独立成域，是各域字段口径的唯一出处。

## Schema 来源说明（渐进式读取）

字段定义全部内置在 `references/schema/` 目录，按两层渐进读取，**不要一次性读全**：

1. **`references/schema/_index.md`（Level 1，每次必读）**：路由层。承载八域共用的通用约定（总原则、页面物理结构、顶层字段、三层字段义务、披露边界、正文章节约定、引用规则）、八域选择表，以及输出目录结构 + PRINCIPLES/INDEX/log 模板。
2. **`references/schema/{域}.md`（Level 2，命中才读）**：单域字段定义。结合 Phase 1 的 raw 打标结果确定本次涉及哪些域，只读命中域的单域文件（如 `references/schema/商品.md`）。概念页无论属于哪个域，写法统一遵循 `references/schema/概念.md`。

简言之：**先读 `_index.md` 掌握通用约定与域路由，再按命中域读对应单域文件。**

**`references/schema/` 是字段清单的唯一来源，没有例外。** 具体地：

- 不存在需要额外寻找的外部规范，也不再向 wiki 目录写 `_schema.md`。
- **wiki 目录下若存在历史遗留的 `wiki/_schema.md` 或 `wiki/{域}/_schema.md`，一律视为已废弃的过期文件，禁止读取、禁止参照、禁止按其字段清单编页。** 这类文件多为早期版本从 raw 表头反向"学"出来的 schema（英文 key、平台规格参数列名等），与 `references/schema/` 的中文私域认知字段完全不是一套。读到它们只需在 log.md 记一句「发现遗留 _schema.md，已忽略」，继续按 `references/schema/` 执行。
- 同理，**既有 wiki 页面的 frontmatter 结构不构成规范依据**。增量编译时旧页可能是历史版本产物（缺字段块、带 `元字段` 嵌套、用英文 key），不得因为"原页就是这么写的"而沿用；一律按当前 `references/schema/` 归一。

## 硬约束（贯穿全流程，任何阶段违反即编译无效）

1. **禁止写入 user_id**：任何目录、任何文件中都不得出现 user_id 字段或其值。
2. **引用格式**：正文引用格式 `[src: 原始文件名#L行号]`（Excel 加 Sheet 名：`[src: 文件名#Sheet名#L行号]`），行号指编译时内存数据行号。**`[src]` 只用于正文章节，frontmatter 字段不带**，页级来源由顶层 `resource` 承载。
3. **md 链接路径忠实原始文件名**：禁止 percent-encoding 中文路径。
4. **时间戳只能用 `get_time` 工具获取**：禁止自行编造或推测时间。
5. **相对路径**：Read/Write/Grep/Glob 使用 `llm_wiki` 根目录下的相对路径（如 `wiki/INDEX.md`、`raw/local/xxx.md`），宿主系统自动补全绝对前缀。若路径解析失败，先用 Glob 确认实际路径再操作。
6. **Schema 读取顺序**：进入 Phase 2 前必须先 Read `references/schema/_index.md`，再按命中域 Read `references/schema/{域}.md`；禁止跳过 schema 直接编 entity。
7. **缺席语义 = 留空不编造**：raw 无数据的字段一律留空不写；**建页锚点缺失时放弃建页而非编造**；必备章节或必抓字段因无数据留空的，记入 log.md「达标待办」，不硬凑覆盖率。三层义务（必出现 / 必有值 / 必抓）的边界见 `references/schema/_index.md`「四、三层字段义务」，不得相互套用。
8. **Concept 也要 [src]**：Concept 页面各正文章节至少 1 条 `[src: ...]` 支撑；无来源的判定/规则视为幻觉，删除或降级为草稿。
9. **机密字段过滤**：披露等级为「机密」的字段（价格底线、成本、客户名单、财务数据等）不得进入 Concept 通用规则、接待域话术模板与任何对外文档；话术只存变量占位（`{规格}`/`{包装形式}` 等）。字段级披露声明优先于页级。
10. **接待域两条 L1 硬规则**：证据不足/置信度低的策略（`策略状态` 只能停在「候选」）不得标为「启用」直接上线；`画像` 正文引用的策略不得指向 `策略状态: 废弃` 的策略页，属断链必须修复。
11. **frontmatter 必须经脚本生成**：禁止模型直接编写或修改最终 Wiki 页面的 YAML frontmatter。每页必须先用 `scripts/frontmatter.py template` 生成完整锁定模板；模型只替换模板中的值，不得增加、删除、改名或移动任何 key；再用 `render` 校验、清空值并拼接正文。脚本返回非零状态时禁止写入最终页面、禁止进入下一阶段。`商家自定义字段` 同样锁定为 Schema 已声明的 key，新增自定义 key 必须先修改单域 Schema。

## 可用工具（仅限以下）

所有文件操作**必须使用以下内置工具**，禁止通过 Bash 调用 `cat`/`echo`/`sed`/`awk` 替代：

| 工具 | 用途 | 调用示例 |
|------|------|--------|
| `Read` | 读取文件内容 | `Read({"file_path": "references/schema/_index.md"})` |
| `Write` | 创建/覆写文件 | `Write({"file_path": "wiki/商品/entities/xxx.md", "file_content": "..."})` |
| `Glob` | 按模式匹配文件路径 | `Glob({"path": "wiki", "query": "**/*.md"})` |
| `Grep` | 正则搜索文件内容 | `Grep({"path": "wiki", "regex": "user_id"})` |
| `Bash` | 仅执行 `python3 scripts/frontmatter.py ...`、测试命令及确无替代的 `mkdir`；不得用 shell 读写 Wiki 内容 | `Bash({"command": "python3 scripts/frontmatter.py template --schema 商品 --output meta/frontmatter-work/商品.yaml"})` |
| `get_time` | 获取当前日期时间、时区与 Unix 时间戳 | `get_time({})` |

> **路径优先使用相对路径**，宿主系统自动补全绝对前缀。
> **子 skill**（如 revise）通过 `Skill("名称")` 调用，子 skill 有自身的额外工具声明（如 `report_edit_result`），不在主流程可用工具范围内。

## 输出根目录

宿主系统将 `llm_wiki` 根路径注入到工具层。调用 Read/Write/Grep/Glob 时传相对路径即可。

**防幻觉规则**：
- 禁止凭记忆拼接绝对路径（尤其长数字串目录）
- 若需创建目录，优先通过 `Write` 自动创建父目录；仅在确无替代时用 Bash `mkdir -p`

## 执行流程（阶段路由）

### Phase 0：编译前预检（必须先执行）

判断传入 raw 文件是否与商家业务知识相关。

- **业务相关**：继续后续流程。
- **业务无关**：调用 `mark_content_unrelated({"raw_path":"当前路径","reason":"简短原因"})`，标记后**立即结束**当前文件处理——不得继续模式判定、打标、编译或写入任何产物。
- 判定依据：是否包含可沉淀的商品/店铺/客户/经营/平台/资产/接待等业务信息；纯日志、空白、系统说明视为无关。
- **接待域特殊**：对话挖掘 T+1 产物直接判为业务相关，按接待域走后续流程。

### Phase 1：模式判定 + 读 Schema

1. **模式判定**：`wiki/INDEX.md` 存在 → Read `references/incremental_compile.md`（增量）；不存在 → Read `references/full_compile.md`（全量）。
2. **读 Schema（渐进式）**：
   - 先 Read `references/schema/_index.md`，掌握通用约定、八域选择表与目录/PRINCIPLES/INDEX/log 模板。
   - 依据 Phase 1 的 raw 打标结果，只 Read 命中域的 `references/schema/{域}.md`；未命中域不读。
   - 需要沉淀口径/规则/分层/方法论时，Read `references/schema/概念.md`（概念页统一按它编写，无论落在哪个域的 concepts/）。
   - **命中客户域时**，还须 Read `application/aicrm/schema.yaml`，按其 `dimensions` 四维度对齐客户页正文的覆盖点（细则与禁入内容见 `references/schema/客户.md`「AICRM 画像对齐」）。
   - 从单域 YAML 解析：**建页锚点**（实体识别字段，第一个字段作 identity；缺失则放弃建页）、**实体子类型**（取自单域文件顶部的「实体子类型」枚举声明，只能照抄其中一项；接待/经营/平台/概念/资产五域必填，商品/店铺/客户为单一形态域须省略。该值只写在 frontmatter 顶层，实体识别字段内不再重复类型字段）、**领域字段集**（分组 → 字段 + `〖硬性〗` 必抓标记）、**意图字段集**（检索路由）。后续 Phase 2-4 以此为准。
3. **生成页面锁定模板**：每个待创建或更新的页面都调用 `python3 scripts/frontmatter.py template --schema {字段Schema} --domain {所属领域} [--subtype {实体子类型}] --output {填写模板路径}`。Entity 的 `{字段Schema}` 等于所属领域；Concept 的 `{字段Schema}` 固定为 `概念`，`--domain` 填实际目录所属领域。禁止手写或复制模板。

### Phase 2-3：编译 Entity + Concept

详见 `references/full_compile.md` 或 `references/incremental_compile.md` 中的 Phase 2-3 章节。模型只生成两份中间内容：完整锁定填写模板（保留全部 key，仅替换有依据字段的 `null`）与不含 frontmatter 的 Markdown 正文。最终页面必须通过以下命令生成：

```bash
python3 scripts/frontmatter.py render --schema {字段Schema} --domain {所属领域} [--subtype {实体子类型}] --filled {填写模板.yaml} --body {正文.md} --output {最终页面.md} --workspace-root .
```

`render` 会拒绝结构变化、重复 key、Schema 外字段、错误枚举、空必填项、无效 `resource`、frontmatter 内 `[src]`、接待意图错配以及 title/H1/文件名不一致；随后递归删除 `null`、空字符串、空数组和空分组，并按 Schema 顺序输出 YAML。模板或正文可放在 `meta/frontmatter-work/`，不得把未经 `render` 的中间文件当成 Wiki 页面。

### 验收（全量/增量统一）

> 禁止 `rm`、`mv` 等删除/移动操作。

| # | 检查项 | 要求 |
|---|--------|------|
| 1 | 链接正确性 | INDEX.md 内跳转链接必须可达，错误立即修复 |
| 2 | 隐私合规 | 全目录 Grep 无 user_id 残留 |
| 3 | Schema 一致性 | entity frontmatter 顶层 `所属领域` 与所在目录一致；接待/经营/平台/概念/资产五域顶层 `实体子类型` 必填，取值须逐字落在该域单域文件顶部声明的枚举内（自创取值、近义改写一律不合格）；商品/店铺/客户三域不得出现该字段。实体识别字段内不得再出现 `实体类型`/`经营事项类型`/`知识类型`/`概念类型`/`资产类型` 等重复的类型字段，也不得重复 `置信度说明` |
| 3b | 域字段块存在 | 每个 entity 页 frontmatter 必须含 `实体识别字段` 与 `领域字段集` 两个块，且块内字段名逐字取自 `references/schema/{域}.md`（中文字段名，不得自创、不得用英文 key、不得从 raw 表头照搬列名）。只有顶层六项加归属四项、没有任何域字段块的页面判为空壳，不合格。concept 页同理，按 `references/schema/概念.md` 校验 |
| 3c | 必抓字段覆盖 | 逐页比对本域 `〖硬性〗` 字段清单：raw 中有支撑却未写入 frontmatter 的判为漏提，必须补；raw 中确无该信息的允许省略，但需在 log.md「达标待办」列出页面与字段名。不得以"raw 没有"为由跳过比对 |
| 3d | 脚本校验 | 本次新增或更新的每个页面均须执行 `python3 scripts/frontmatter.py check --schema {字段Schema} --domain {所属领域} [--subtype {实体子类型}] --page {页面路径} --workspace-root .` 且返回 0；Concept 的字段 Schema 固定为 `概念`。有子类型的页面必须传 `--subtype`，失败必须修复，禁止只记待办后放行 |
| 4 | 顶层字段 | 每页 frontmatter 最外层 `type`/`title`/`description`/`resource`/`tags`/`timestamp` 六项齐全且无空值，`所属领域`/`披露等级` 同样不得缺；`type` 取「实体」或「概念」且与所在目录（entities/concepts）对应、`title` 与正文 H1 及文件名一致；`description`/`tags` 不含机密字段内容；本次写入的页面不得出现 `元字段` 嵌套块，也不得出现 `页面类型`/`来源文件`/`更新时间`/`页面编号`/`证据次数`（前三项已上移顶层、后两项已废弃，出现即脏数据） |
| 4b | resource 可追溯 | 逐页取 `resource` 的每个值，必须是 `raw/` 起始的相对路径且该文件在 raw/ 下真实存在（用 Glob 逐个验证，不得目测放过）；出现域名/页面形态/目录名等非路径词（如 `店铺`）、裸文件名、缺 fileId 后缀一律判为不合格；纯派生概念页填上游 wiki 页面路径，该路径同样必须存在。不合格页记入 log.md「达标待办」并修正 |
| 5 | 缺席语义 | 空字段一律省略而非留空值；建页锚点缺失的页面不应存在；**frontmatter 字段内不得出现 `[src]`**（页级来源看顶层 `resource`），出现即判不合格 |
| 6 | Concept 溯源 | 各正文章节至少 1 条 `[src]`，无支撑则删除或降级 |
| 7 | 接待域 L1 | 无「策略状态=启用」却证据不足/低置信的策略；画像不引用「策略状态=废弃」的策略 |
| 8 | 网状互链 | 正文中提及的其他 entity/concept 页面名必须是 markdown 相对路径链接（非裸文字/书名号），断链或裸引用立即修复 |
| 9 | 接待意图枚举 | 每个接待域 策略/问答 entity 的 `接待意图` 必须且只填 1 个、取自受控词表 8 个中文值，且 `接待意图码` 与之一一对应匹配；`画像` 不得带该字段；不得出现第 9 个意图或改写字面；`关联意图`（若有）取值同样限这 8 值 |

### Phase 4：生成可选 query 与接待意图索引

> 生成 `meta/query.json` 时必须先 `Read("references/build_query.md")` 获取精确格式，逐字段对照生成。禁止凭记忆发挥。

| 文件 | 格式参考 | 说明 |
|------|----------|------|
| `meta/query.json` | `references/build_query.md` | 可选产物；需要能力类型 query map 时生成或刷新 |
| `meta/intent_index.json` | `references/build_query.md`「meta/intent_index.json 构建规范」 | 仅当本次涉及接待域时生成/重建：接待意图倒排索引（封闭 8 键，中文值↔英文码，映射到命中的接待策略/问答页） |

## 最佳实践

1. **没有数据不造知识**——宁可标注"知识空白"也不编造；缺席字段一律省略。
2. **引用追溯是刚需**——Entity 每个字段值、Concept 每个章节都能回溯到原始 raw 位置。
3. **Concept 独立于 Entity**——concept 不能只描述一个 entity 的情况。
4. **PRINCIPLES 先于编译**——先确定披露边界，再按披露等级（可对外/仅内部/机密）三档过滤字段。
5. **覆盖度留白坦然**——entity 只有 2/20 就写 2/20，不凑数。
6. **Schema 是唯一字段清单来源**——字段枚举只来自 `references/schema/{域}.md`，不在 skill 其它位置另行定义；`scripts/frontmatter.py` 每次从「字段定义」YAML 代码块动态提取模板。
7. **模型只填值**——保留模板全部 key 和层级，缺失值保持 `null`，由 `render` 统一清理；不要让模型直接输出最终 frontmatter。

## 关于八域与打标的关系

编译覆盖八域（商品/店铺/客户/经营/平台/资产/接待/概念），但 raw 文件打标（`references/raw_file_tag.md`）覆盖七域：商品/店铺/客户/经营/平台/资产，外加**接待域（仅对上传的接待类物料打标**，如客服话术、SOP、FAQ、AI 业务员人设、培训文档）。两类不参与打标：
- **对话挖掘 T+1 产物**：Phase 0 直接判为业务相关并直连接待域编译流程，不经过打标。
- **概念域**：不来自 raw 上传文件，在编译中按各域字段的「口径见 concepts/xxx.md」派生，无需打标。

## References

| 文件 | 用途 |
|---|---|
| `references/schema/_index.md` | Schema 路由层：通用约定 + 八域选择表 + 目录/PRINCIPLES/INDEX/log 模板（每次必读） |
| `references/schema/{商品,店铺,客户,经营,平台,资产,接待,概念}.md` | 八域单域字段定义（命中才读） |
| `references/full_compile.md` | 全量编译 Phase 1-4 详细执行步骤 |
| `references/incremental_compile.md` | 增量编译流程与规范 |
| `references/raw_file_tag.md` | raw 文件打标规则（仅 Phase 0 判定业务相关后使用，覆盖六域 + 接待上传物料） |
| `references/build_query.md` | query.json 构建规范 |
| `scripts/frontmatter.py` | 从八域 Schema 提取锁定模板，校验填写结果并渲染最终 Wiki 页面 |
| `requirements.txt` | frontmatter 脚本依赖（PyYAML） |
| `application/aicrm/schema.yaml` | AICRM 客户画像维度定义；**命中客户域时必读**，用于对齐正文覆盖点（只取 `dimensions` 一节） |
| `revise/prompt.md` | wiki 节点定向修改子 skill（有独立工具声明） |
