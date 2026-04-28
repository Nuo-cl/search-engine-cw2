# Search Engine Tool — 功能设计与技术方案

## 项目概述

针对 https://quotes.toscrape.com/ 构建一个命令行搜索引擎工具，支持网页爬取、倒排索引构建、持久化存储和高级搜索功能。

---

## 技术栈

| 类别 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.10+ | 类型提示、match 语法 |
| HTTP请求 | `requests` | 爬虫核心 |
| HTML解析 | `beautifulsoup4` + `lxml` | lxml 作为解析器后端，速度更快 |
| 终端交互 | `prompt_toolkit` | 实时自动补全、历史记录、交互式输入 |
| 终端美化 | `rich` | 彩色输出、表格、关键词高亮 |
| 测试 | `pytest` + `pytest-cov` | 单元/集成测试 + 覆盖率报告 |
| Mock | `responses` 或 `pytest-mock` | mock HTTP 请求，测试不依赖真实网站 |
| 序列化 | `json` | 索引持久化，人类可读 |
| 代码规范 | `ruff` | lint + format，兼容 PEP 8 |

---

## 项目结构

```
search-engine/
├── src/
│   ├── __init__.py
│   ├── crawler.py          # 网页爬虫（作业要求）
│   ├── indexer.py           # 倒排索引构建与管理（作业要求）
│   ├── search.py            # 搜索引擎：查询解析、排名、建议（作业要求）
│   ├── main.py              # 入口，命令分发（作业要求）
│   ├── storage.py           # 索引序列化/反序列化
│   ├── query_parser.py      # 查询语法解析器
│   ├── trie.py              # 前缀树（实时自动补全）
│   ├── spell.py             # 拼写纠错
│   └── ui.py                # 终端交互界面（prompt_toolkit + rich）
├── tests/
│   ├── __init__.py
│   ├── test_crawler.py      # （作业要求）
│   ├── test_indexer.py      # （作业要求）
│   ├── test_search.py       # （作业要求）
│   ├── test_storage.py
│   ├── test_query_parser.py
│   ├── test_trie.py
│   ├── test_spell.py
│   └── test_integration.py  # 集成测试
├── data/                    # 编译后的索引文件
├── docs/
│   └── design_plan.md       # 本文档
├── requirements.txt
└── README.md
```

> 注：`crawler.py`、`indexer.py`、`search.py`、`main.py` 和 `test_crawler.py`、`test_indexer.py`、`test_search.py` 是作业明确要求的文件，必须保留。其余模块为功能增强。

---

## 爬取策略

**只爬名言列表页**（`/page/1/` ~ `/page/N/`），不爬作者详情页和标签页。

理由：
- 标签页内容与列表页完全重复，爬取会导致同一名言被索引两次
- 作者详情页的生平简介文字量大，大量生僻词会稀释索引质量，且搜索语义模糊
- 列表页已包含每条名言的作者名和标签，作为结构化元数据提取即可

每条名言提取以下结构化数据：
- 名言文本（用于文本搜索的主要内容）
- 作者名（用于 `--author` 筛选）
- 标签列表（用于 `--tag` 筛选）

---

## 模块设计

### 1. 爬虫模块 (`crawler.py`)

**职责**：爬取目标网站所有列表页，提取名言文本和结构化元数据。

**核心功能**：
- 从首页开始，自动发现并跟踪分页链接（`/page/1/`, `/page/2/`, ...）
- 提取每条名言的文本、作者名、标签
- 严格遵守 6 秒礼貌窗口（`time.sleep`）
- 错误处理：超时重试（指数退避）、连接错误优雅恢复、HTTP 状态码检查
- 去重：记录已访问 URL，避免重复爬取

**数据输出**：
```python
@dataclass
class Quote:
    text: str
    author: str
    tags: list[str]

@dataclass
class CrawledPage:
    url: str
    quotes: list[Quote]
    crawled_at: datetime
```

---

### 2. 索引模块 (`indexer.py`)

**职责**：将爬取内容构建为倒排索引，同时维护作者和标签的结构化映射。

**倒排索引结构**：
```python
{
    "word": {
        "df": 5,                            # 文档频率（出现在多少个页面中）
        "postings": {
            "/page/1/": {
                "tf": 3,                    # 词频
                "positions": [12, 45, 89],  # 词在页面中的位置（用于精确短语匹配）
                "tfidf": 0.72               # TF-IDF 权重（预计算）
            },
            "/page/3/": {
                "tf": 1,
                "positions": [7],
                "tfidf": 0.31
            }
        }
    }
}
```

**结构化映射**：
```python
# 作者 → 页面列表
authors: {
    "albert einstein": ["/page/1/", "/page/3/"],
    "j.k. rowling": ["/page/2/", "/page/5/"]
}

# 标签 → 页面列表
tags: {
    "love": ["/page/1/", "/page/7/"],
    "inspirational": ["/page/1/", "/page/2/", "/page/3/"]
}
```

**处理流程**：
- 文本预处理：小写化、去标点、分词
- 记录每个词的位置（position），用于精确短语匹配
- 预计算 TF-IDF 权重，搜索时直接使用
- 构建作者和标签的反向映射
- 统计全局信息：总页面数、总词数、词汇表大小

**TF-IDF 计算**：
```
TF(t, d) = 词 t 在文档 d 中的出现次数 / 文档 d 的总词数
IDF(t) = log(总文档数 / 包含词 t 的文档数)
TF-IDF(t, d) = TF(t, d) × IDF(t)
```

---

### 3. 存储模块 (`storage.py`)

**职责**：索引的持久化存储与加载。

**功能**：
- 序列化：将索引结构保存为 JSON 文件
- 反序列化：从 JSON 文件加载索引
- 同时保存元数据（爬取时间、页面数、词汇量等）
- 文件完整性校验（保存 checksum，加载时验证）

**存储格式**：
```json
{
    "metadata": {
        "created_at": "2026-04-28T12:00:00",
        "total_pages": 10,
        "total_words": 8421,
        "checksum": "sha256:..."
    },
    "pages": {
        "/page/1/": {
            "url": "https://quotes.toscrape.com/page/1/",
            "quotes": [
                {
                    "text": "The world as we have created it...",
                    "author": "albert einstein",
                    "tags": ["change", "deep-thoughts", "thinking", "world"]
                }
            ]
        }
    },
    "index": {
        "word": { "df": 5, "postings": { ... } }
    },
    "authors": {
        "albert einstein": ["/page/1/", "/page/3/"]
    },
    "tags": {
        "love": ["/page/1/", "/page/7/"]
    }
}
```

---

### 4. 查询解析器 (`query_parser.py`)

**职责**：解析用户查询语法，生成结构化查询对象。

**支持的查询语法**：

| 语法 | 含义 | 示例 |
|---|---|---|
| `word` | 基础搜索 | `find love` |
| `word1 word2` | AND（默认，取交集） | `find good friends` |
| `"phrase"` | 精确短语匹配 | `find "to be or not"` |
| `word1 OR word2` | OR（取并集） | `find love OR hate` |
| `-word` | 排除包含该词的页面 | `find love -war` |
| `--tag tag` | 按标签筛选 | `find love --tag inspirational` |
| `--author name` | 按作者筛选 | `find --author Einstein` |
| 混合 | 组合使用 | `find love --tag inspirational --author Einstein` |

**解析输出**：
```python
@dataclass
class Query:
    must_include: list[str]        # AND 词
    phrases: list[list[str]]       # 精确短语（按位置验证词序）
    should_include: list[str]      # OR 词
    must_exclude: list[str]        # 排除词
    filter_tag: str | None         # 标签筛选
    filter_author: str | None      # 作者筛选
```

---

### 5. 搜索模块 (`search.py`)

**职责**：基于倒排索引执行搜索，排名并返回结果。

**搜索流程**：
1. 解析查询 → `Query` 对象
2. 如有 `--tag` / `--author`，先从结构化映射中获取候选页面集合
3. 根据 `must_include` 在倒排索引中取交集
4. 根据 `should_include` 取并集
5. 根据 `must_exclude` 排除
6. 精确短语匹配：利用 positions 验证词序是否连续
7. 与步骤 2 的候选集取交集（实现筛选）
8. 按 TF-IDF 综合分数排名
9. 拼写纠错：如无结果，检查是否拼写错误并建议
10. 生成结果摘要（snippet），高亮关键词

**搜索结果**：
```python
@dataclass
class SearchResult:
    url: str
    score: float              # TF-IDF 综合分数
    snippet: str              # 包含关键词的上下文摘要
    matched_terms: list[str]  # 命中的词
```

---

### 6. 前缀树 (`trie.py`)

**职责**：支持实时自动补全。

**功能**：
- 基于索引词汇表构建 Trie
- 前缀匹配：输入 `fri` → 返回 `friends, friendship, friday`
- 按文档频率排序建议结果（高频词优先）
- 限制返回数量（默认 Top 10）
- 同时为作者名和标签名提供补全数据源

---

### 7. 拼写纠错 (`spell.py`)

**职责**：检测拼写错误并建议正确词。

**实现**：
- 计算查询词与词汇表中所有词的编辑距离（Levenshtein Distance）
- 返回编辑距离最小的 Top 3 候选词
- 优化：只比较首字母相同或长度接近的词，避免全量计算
- 阈值控制：编辑距离 > 3 的不建议

---

### 8. 终端界面 (`ui.py`)

**职责**：交互式命令行界面，集成实时补全。

**实时自动补全**（`prompt_toolkit` 自定义 `Completer`）：

| 用户正在输入 | 补全来源 | 示例 |
|---|---|---|
| 行首（命令位置） | 命令列表 | `build`, `load`, `find`, `print`... |
| `find ` 后的普通文本 | 倒排索引词汇表（Trie） | `fri` → `friends, friendship` |
| `find --tag ` 后 | 标签列表 | `l` → `love, life, learning` |
| `find --author ` 后 | 作者列表 | `ein` → `Albert Einstein` |
| `print ` 后 | 倒排索引词汇表（Trie） | `non` → `nonsense, none` |

**其他交互功能**：
- 上下键翻阅查询历史
- `rich` 彩色输出搜索结果
- 关键词高亮显示
- 结果分页（每页 10 条）

---

## 命令列表

### 基础命令（作业要求）

| 命令 | 说明 |
|---|---|
| `build` | 爬取网站 → 构建索引 → 保存到文件（一条命令完成三步） |
| `load` | 从文件加载索引到内存 |
| `print <word>` | 打印某个词的倒排索引详情 |
| `find <query>` | 搜索查询，支持高级语法，按 TF-IDF 排名 |

### 扩展命令

| 命令 | 说明 |
|---|---|
| `tags` | 列出所有标签及其名言数量 |
| `authors` | 列出所有作者及其名言数量 |
| `history` | 显示查询历史 |
| `stats` | 显示索引统计信息（页面数、词汇量、爬取时间等） |
| `help` | 显示帮助信息、命令说明和查询语法 |
| `exit` | 退出程序 |

> 注：`suggest` 不再作为独立命令，其功能由实时自动补全替代（输入时自动弹出建议）。

---

## 输出格式示例

### `print` 命令

```
Search Engine > print nonsense

Word: "nonsense"
Document Frequency: 3 pages
Total Occurrences: 5

  /page/2/  — TF: 2, Positions: [5, 18], TF-IDF: 0.45
  /page/5/  — TF: 1, Positions: [32],    TF-IDF: 0.21
  /page/8/  — TF: 2, Positions: [11, 44], TF-IDF: 0.19
```

### `find` 命令 — 基础搜索

```
Search Engine > find love

Found 12 results (0.03s, ranked by TF-IDF):

  1. [0.82] https://quotes.toscrape.com/page/3/
     "...the opposite of love is not hate, it's indifference..."

  2. [0.71] https://quotes.toscrape.com/page/7/
     "...where there is love there is life..."

  3. [0.65] https://quotes.toscrape.com/page/1/
     "...love looks not with the eyes, but with the mind..."

Page 1/2  [n: next, p: previous]
```

### `find` 命令 — 高级查询

```
Search Engine > find love --tag inspirational

Found 5 results (0.02s, filtered by tag: inspirational):

  1. [0.82] https://quotes.toscrape.com/page/3/
     "...the opposite of love is not hate, it's indifference..."
  ...
```

### `find` 命令 — 拼写纠错

```
Search Engine > find lovee

  "lovee" not found. Did you mean: love, lovely, lover? (y/n) y

Found 12 results (0.03s, ranked by TF-IDF):
  ...
```

### 实时自动补全

```
Search Engine > find fri
                    ┌──────────────────┐
                    │ friends    (15)  │
                    │ friendship  (2)  │
                    │ friday      (3)  │
                    └──────────────────┘
```

### `tags` 命令

```
Search Engine > tags

All Tags (42):
  inspirational   (25 quotes)
  love            (18 quotes)
  life            (15 quotes)
  humor           (12 quotes)
  ...
```

### `authors` 命令

```
Search Engine > authors

All Authors (50):
  Albert Einstein      (10 quotes)
  J.K. Rowling         (8 quotes)
  Marilyn Monroe       (6 quotes)
  ...
```

### `stats` 命令

```
Search Engine > stats

Index Statistics:
  Pages crawled:    10
  Total quotes:     100
  Unique words:     8,421
  Unique authors:   50
  Unique tags:      42
  Index file size:  1.2 MB
  Built at:         2026-04-28 12:00:00
```

---

## 测试策略

| 测试类型 | 覆盖范围 | 工具 |
|---|---|---|
| 单元测试 | 各模块核心逻辑（爬虫解析、索引构建、查询解析、TF-IDF计算、Trie、拼写纠错） | pytest |
| 集成测试 | 完整 build → load → print → find 流程 | pytest |
| Mock 测试 | 爬虫网络请求 mock，不依赖真实网站即可测试 | responses / pytest-mock |
| 边界测试 | 空查询、特殊字符、不存在的词、超大索引、空索引 | pytest |
| 性能测试 | 搜索响应时间、索引构建时间 | pytest + time |
| 覆盖率 | 目标 ≥ 85% | pytest-cov |

---

## 开发优先级

| 阶段 | 模块 | 说明 |
|---|---|---|
| P0 | crawler + indexer + storage + main | 核心功能，满足 build/load/print/find 基础要求 |
| P1 | search (TF-IDF) + query_parser | 搜索排名 + 高级查询语法（精确短语、OR、排除、作者/标签筛选） |
| P2 | trie + spell + ui | 实时自动补全 + 拼写纠错 + 美化界面 |
| P3 | tests（全面） | 补全测试覆盖率至 85%+ |
| P4 | README + 视频录制 | 文档和演示 |
