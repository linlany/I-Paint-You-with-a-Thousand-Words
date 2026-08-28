# Literary Image Collage

一个面向 Codex/LLM 工作流的 Skill 骨架：把用户上传的图片拆解为结构化视觉线索，再从指定作家或历史人物的公版语料中做多路检索、重排、逐条引文核验，最后生成带来源账本的文学拼贴。

它刻意区别于“模仿某位作者文风”：成品只使用语料中可定位、可核验的真实片段，或者明确标注为用户要求的非引文连接文字。

## 能做什么

- 图片 → `observations`（可见事实）+ `associations`（检索联想）的结构化分析
- 按对象/动作、空间/光线、构图、氛围/抽象概念生成多路查询
- 兼容关键词、BM25、向量检索或外部搜索后端的候选片段输入
- 基于语义贴合、视觉覆盖、场景锚点、来源质量、片段完整性、多样性和冲突风险 rerank
- 多样性按作品/文章计算：共享语料库级 `source_id` 的不同作品不会被误判为同一来源；同一作品的后续片段只会被软性降权，仍可在证据不足或匹配明显更强时入选
- 严格 quote-only 拼接，拒绝改写、拼接造句和无法定位的“名言”
- 输出作品、章节/位置、来源 URL、快照标识、核验状态和检索时间
- 标注版权/公版范围、翻译关系、OCR 不确定性和图像解读边界

## 目录

```text
literary-image-collage/
├── SKILL.md
├── README.md
├── agents/openai.yaml
├── config/example.yaml
├── schemas/
│   ├── corpus-record.schema.json
│   ├── image-analysis.schema.json
│   ├── candidate-passage.schema.json
│   └── collage-output.schema.json
├── prompts/
│   ├── image-analysis.md
│   ├── retrieval-query-planner.md
│   ├── composition.md
│   └── verification.md
├── scripts/
│   ├── build_queries.py
│   ├── ingest_corpus.py
│   ├── retrieve.py
│   ├── rerank.py
│   └── verify_quotes.py
├── examples/
│   ├── fixture-corpus.jsonl
│   ├── image-analysis.json
│   ├── candidates.jsonl
│   └── collage-output.json
└── tests/test_scripts.py
```

## 快速开始

需要 Python 3.9+；脚本只使用标准库。

```powershell
cd E:\skill\literary-image-collage

# 1) 将 corpus JSON/JSONL 规范化为可检索记录
py scripts\ingest_corpus.py examples\fixture-corpus.jsonl --out work\corpus.jsonl

# 2) 根据已完成的图片分析生成多路查询
py scripts\build_queries.py --analysis examples\image-analysis.json --out work\queries.json

# 3) 用内置的本地词法检索器取回候选片段
py scripts\retrieve.py --corpus work\corpus.jsonl --queries work\queries.json --out work\candidates.jsonl

# 4) 对候选片段做基线重排；读取场景匹配、rerank 权重和作品多样性设置
py scripts\rerank.py --analysis examples\image-analysis.json --candidates work\candidates.jsonl --config config\example.yaml --out work\ranked.jsonl

# 5) 针对 corpus 逐条核验最终拼贴中的引文
py scripts\verify_quotes.py --corpus work\corpus.jsonl --collage examples\collage-output.json --report work\verification.json

# 6) 运行离线测试
py -m unittest discover -s tests -v
```

内置检索器是可解释的词法 baseline；没有内置视觉模型、向量数据库或联网抓取器。生产接入时，让视觉模型按 `prompts/image-analysis.md` 输出 JSON，让联网或向量检索后端输出 `schemas/candidate-passage.schema.json` 记录，再把结果交给这些脚本核验。

## 推荐的数据流

```text
uploaded image
    ↓
image analysis JSON
    ↓
query facets ──→ keyword/vector/hybrid retriever
                          ↓
                  candidate passages
                          ↓
                   baseline reranker
                          ↓
             exact quote + provenance verifier
                          ↓
                    collage composer
                          ↓
               collage output + audit ledger
```

## corpus 约定

每条记录应至少包含：`text`、`author`、`work`、`source_url`、`source_id`、`location`、`license_status`；建议同时提供由语料导入阶段生成的 `record_id` 和用于作品级多样性判断的 `work_id`。生产数据还应保留原始文本快照哈希、下载时间、版本/提交号、语言、翻译信息和字符范围。

首选：Project Gutenberg、Internet Archive 中已确认公版的版本、官方档案馆开放资料、用户明确提供且许可清楚的文本。公版判断取决于司法辖区、作者死亡年份、版本和翻译；不确定时保持 `rights_review`，不要自动标为可复用。

## 输出原则

内部结果仍保留完整 provenance 与核验信息；用户在聊天中默认只看到最终文学结果。用户明确要求出处、核验或方法时，再显示相应的来源信息。

默认拼贴是断裂的联想式并置，不强求逻辑、因果、语法或叙事连贯；但片段仍应与图片的主要视觉锚点相关。只有用户明确要求连贯文本时才补充连接文字。

候选片段的来源多样性以作品/文章为单位，而不是以语料库或集合级 `source_id` 为单位。默认优先覆盖不同作品，但不硬性禁止同一作品再次出现。

在千言/长篇模式中，优先增加已核验的原文片段；用户使用中文时，默认可将这些片段译为中文，但内部始终保留原文和翻译状态。不使用大段原创仿写来填充篇幅。

内部结果包含：

1. 文学拼贴正文（每段绑定 `quote_id`）
2. 视觉观察与检索联想摘要
3. provenance ledger（逐条原文、来源和核验状态）
4. 版权/语料范围与翻译说明
5. 不能被可靠证据支持的部分，以及被拒绝的候选片段

“诗意”不能替代证据。无法核验的片段应被舍弃或标为 `unverified`，不能放入严格引文正文。
