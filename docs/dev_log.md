# 开发日志

## 2026-04-29 — P0: 核心功能实现

### 完成内容

- 搭建项目结构：`src/`、`tests/`、`data/`、`docs/`
- 实现四个核心模块：
  - **crawler.py**：网页爬虫，支持自动分页发现、6秒礼貌窗口、指数退避重试
  - **indexer.py**：倒排索引构建，存储词频(TF)、位置(positions)、预计算TF-IDF权重，同时维护作者和标签的结构化映射
  - **storage.py**：JSON持久化，保存/加载索引，SHA256完整性校验
  - **search.py**：基础搜索，多词AND查询，TF-IDF排名，摘要生成
  - **main.py**：命令行界面，支持 build/load/print/find/stats/help 命令
- 使用模拟数据验证全流程：索引构建 → 保存 → 加载 → 搜索，全部通过
- 创建GitHub仓库并推送初始代码

### 设计决策

- **爬取策略**：只爬名言列表页，不爬作者详情页和标签子页面。作者名和标签从列表页提取为结构化元数据，避免索引被无关文本污染
- **TF-IDF预计算**：在索引构建阶段预算好权重，搜索时直接查表，提高查询速度
- **索引完整性**：保存时计算SHA256 checksum，加载时校验，防止文件损坏

---

## 2026-04-29 — P1: 高级查询语法

### 完成内容

- 新增 **query_parser.py**：查询解析器，支持以下语法：
  - `"exact phrase"` — 精确短语匹配（利用位置索引验证词序连续）
  - `word1 OR word2` — OR查询（取并集）
  - `-word` — 排除词（过滤掉包含该词的页面）
  - `--tag tagname` — 按标签筛选
  - `--author name` — 按作者筛选
  - 以上语法可组合使用
- 重写 **search.py** 的 `find()` 方法，支持全部高级查询类型
- 新增 `tags` 和 `authors` 命令，列出所有标签/作者及其页面数量
- 更新帮助文本，展示完整查询语法

### 测试验证

使用构造的3页9条名言数据测试：

- 基础AND查询 ✓
- 精确短语匹配 ✓（验证了 "good friends" 匹配而位置不对的短语不匹配）
- OR查询 ✓
- 排除词 ✓
- 标签/作者筛选 ✓
- 组合查询 ✓
- 边界情况（空查询、不存在的词） ✓

---

## 2026-04-29 — 用户测试反馈与修改

### 问题

用户手动运行程序后发现：搜索结果中的名言文本被截断为120字符的片段，只显示关键词附近的上下文窗口，而非完整引文。

### 分析

原始设计参考了Google搜索的摘要风格（截断 + 省略号），适合长文档场景。但 quotes.toscrape.com 的名言本身较短（通常1-2句话），截断后反而丢失了语义完整性，用户体验不佳。

### 修改

调整 `_generate_snippet()` 方法：展示匹配名言的完整文本，并附带作者署名（`— Author Name`），不再截断。这样搜索结果更直观，视频演示效果也更好。

---

## 2026-04-29 — P2: 自动补全、拼写纠错与终端UI

### 完成内容

- 新增 **trie.py**：前缀树（Trie），基于索引词汇表构建，支持实时自动补全
  - 按文档频率排序建议结果（高频词优先）
  - 提供 `from_index()` 工厂方法，直接从倒排索引构建
- 新增 **spell.py**：拼写纠错器
  - 基于 Levenshtein 编辑距离算法
  - 优化：只比较长度相近的词，避免全量计算
  - 阈值控制：编辑距离 > 2 的不建议
- 新增 **ui.py**：交互式终端界面
  - `prompt_toolkit`：上下文感知的实时自动补全（根据命令位置、`--tag`、`--author` 自动切换补全数据源），上下键翻阅历史
  - `rich`：彩色表格输出搜索结果、索引详情、标签/作者列表，关键词高亮
- 重写 **main.py**：集成 UI 层，新增 `history` 命令
  - 添加 `interactive=False` 参数，支持在非终端环境（如 pytest）下运行

### 设计决策

- `suggest` 不作为独立命令，而是融入实时补全体验（输入时自动弹出建议）
- 保留 `tags` 和 `authors` 独立命令，因为补全弹窗一次只能看几个，有时需要浏览完整列表
- UI 层与核心逻辑完全解耦，不影响测试和非交互场景

---

## 2026-04-29 — P3: 全面测试套件

### 完成内容

编写 **173 个测试**，覆盖 9 个测试模块，总覆盖率 **86%**：

| 测试模块             | 测试数 | 覆盖目标                                         |
| -------------------- | ------ | ------------------------------------------------ |
| test_crawler.py      | 13     | HTML解析、mock爬取流程、重试、错误处理           |
| test_indexer.py      | 24     | 分词、TF-IDF、作者/标签映射、序列化往返          |
| test_search.py       | 27     | 基础/短语/OR/排除/标签/作者查询、snippet、print  |
| test_storage.py      | 9      | 保存/加载、checksum完整性、损坏检测、空索引      |
| test_query_parser.py | 29     | 全部查询语法变体和组合                           |
| test_trie.py         | 15     | 插入、建议、前缀匹配、边界情况                   |
| test_spell.py        | 21     | Levenshtein距离、建议、阈值、边界情况            |
| test_integration.py  | 9      | 完整 crawl→index→save→load→search 端到端流程 |
| test_cli.py          | 26     | 命令分发、require-index 检查、所有命令           |

### 技术要点

- 使用 `responses` 库 mock HTTP 请求，测试不依赖真实网络
- 使用 `conftest.py` 共享 fixture（示例HTML、构造好的 indexer/search_engine）
- `SearchEngineCLI` 添加 `interactive=False` 解决 `prompt_toolkit` 在非终端环境下的报错

---

## 2026-04-29 — 性能优化与基准测试

### 优化内容

**优化1：短语匹配位置查找 — list → set**

- `PostingEntry` 新增 `position_set: set[int]`，与 `positions: list[int]` 并存
- 短语匹配时使用 `position_set` 做 O(1) 哈希查找，替代原来 `positions` 列表的 O(n) 线性扫描
- 保留 list 用于 `print` 命令的有序展示

**优化2：AND 交集 — 小集合优先**

- `_intersect_terms()` 先按各词的 posting 集合大小排序，从最小的开始交集
- 减少中间集合大小，加速多词查询
- 原理：集合交集 O(min(|A|, |B|))，从小集合开始让中间结果更小

**保留对比基线**

- 旧方法保留为 `_unoptimized` 版本（`_intersect_terms_unoptimized`、`_check_phrase_on_page_unoptimized`）
- benchmark 脚本直接对比优化前后性能

### 基准测试

新增 `tests/benchmark.py`，分三部分：

1. **真实数据**（10页, 682词）— 各操作实际耗时
2. **大规模模拟**（500页, 5000名言, ~10000词）— mock 生成数据，测试压力下表现
3. **规模扩展对比**（50/200/500页）— 展示搜索时间如何随数据量变化

### 关键发现

- 搜索查询耗时 ~10-30us，几乎不随数据量增长（哈希表 O(1) 查找）
- 索引构建时间线性增长：50页 23ms → 500页 437ms（O(N)）
- 拼写纠错从 ~3.5ms（682词）增长到 ~62ms（10092词），暴力编辑距离 O(V × L²)
- 小数据集上优化前后差异不大（预期内），但数据结构选择在大规模场景下是必要的

### 文档

- 新增 `docs/benchmark.md`：复杂度分析、优化原理、测试结果

---

## 2026-05-05 — P4: README、索引文件与 Git 标签

### 完成内容

- 编写 **README.md**：项目概述、安装说明、所有命令用法示例、查询语法、交互功能、项目结构、测试和 benchmark 说明、依赖列表
- **索引文件提交**：将 `data/index.json`（10页，100条名言，682词）纳入版本控制，用户克隆仓库后可直接 `load` 使用
- **Git 标签**：为每个开发阶段打 annotated tag（v0.1.0 ~ v1.0.0），展示增量式开发过程

---

## 2026-05-05 — 用户测试反馈：多词作者名查询问题

### 问题

用户测试时发现 `find --author albert einstein` 返回 0 条结果，预期应该匹配 Albert Einstein 的名言。

### 分析

查询解析器 `_extract_flag()` 的设计是 `--author` 后只取一个空格分隔的词作为 filter 值：

- `--author einstein` → `filter_author="einstein"`，正确（部分匹配）
- `--author "albert einstein"` → `filter_author="albert einstein"`，正确（引号包裹）
- `--author albert einstein` → `filter_author="albert"`，`einstein` 被当成搜索关键词 → 在名言正文的倒排索引中查找 "einstein" → 未命中 → 返回 0 结果

### 考虑的方案

**方案 A（被否决）**：让 `--author` 贪婪地吃掉后续所有词直到行尾或下一个 flag。

问题：`find love --author albert einstein` 中 `love` 会被正确识别为搜索词吗？`albert einstein` 之后如果还有搜索词怎么处理？边界情况复杂，容易产生歧义。

**方案 B（采用）**：保持现有 parser 逻辑不变，多词作者名/标签名必须用引号包裹。

理由：
- 语义明确，无歧义——引号清楚地界定了 filter 值的边界
- 与精确短语搜索的引号语法保持一致（`find "good friends"` 也用引号）
- 符合 shell/CLI 工具的通用惯例（如 `git commit -m "multi word message"`）

### 修改

1. **Help 文本**：在查询语法参考中新增 `find --author "albert einstein"` 示例，明确说明多词需要引号
2. **自动补全**：`SearchCompleter` 对包含空格的作者名自动包裹引号，用户选择补全项后直接插入 `"albert einstein"` 而非 `albert einstein`
3. **Parser 不变**：不引入贪婪解析，避免歧义

---

## 当前项目状态

### 已完成

- P0：核心功能（crawler / indexer / storage / search / main）
- P1：高级查询语法（精确短语 / OR / 排除 / 标签 / 作者筛选）
- P2：自动补全（Trie）/ 拼写纠错 / Rich 终端 UI
- P3：173 个测试，86% 覆盖率
- 性能优化 + 基准测试
- P4：README.md、索引文件、Git 标签

### 待完成

- 视频录制
