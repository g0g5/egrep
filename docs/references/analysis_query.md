# RAG Query 写法调研：自然语言问句 vs 名词/关键词形式

## 结论

RAG 检索时不要固定只用一种 query 写法。自然语言问句更适合 semantic/vector retrieval；名词、关键词、标识符形式更适合 BM25/关键词检索；生产系统通常用 hybrid，把两种检索都跑一遍，再做融合或 rerank。

| 场景 | 更推荐的 query 形式 | 原因 |
| --- | --- | --- |
| 向量检索 / embedding search | 自然语言问句或完整意图句 | embedding 模型更容易捕捉“我要找实现位置/机制/原因”等语义意图 |
| BM25 / keyword search | 关键词、名词短语、标识符 | BM25 主要看 query tokens 和文档 tokens 的精确匹配，废词/泛词容易加噪声 |
| hybrid RAG | 两者都用 | natural query 给 vector，keyword query 给 BM25，最后 rerank/fuse |
| 代码库 RAG | hybrid 更重要 | 代码里既有自然语言注释/文档，也有函数名、类名、常量、文件名、错误码、API 名 |

## 例子

自然语言问句：

```text
where is key authentication implemented?
```

这个形式更适合给 vector search 或 reranker，因为它表达了任务意图：找“实现位置”。

名词/关键词形式：

```text
key authentication
```

这个形式更适合给 BM25 或 exact search，但可能太窄。更好的关键词 query 可以扩成：

```text
key authentication api key auth authenticate middleware authorization
```

更实用的做法是同时生成两路 query：

```text
semantic_query: where is key authentication implemented?
keyword_query: key authentication api key auth authenticate authorization middleware
```

如果只能发一个 query 给 hybrid 检索，可以用这种折中形式：

```text
where is API key authentication implemented? api key auth authentication middleware authorization
```

如果系统支持分别传给 vector/BM25，更干净的做法是分开传。

## 调研要点

1. Dense retrieval 的经典 DPR 论文针对 open-domain question answering，把“问题”和“passage”学到同一 embedding 空间；在 QA 检索场景下，自然语言问题是主输入形式。
2. BM25 文档明确说明它基于 query tokens 的精确匹配、词频、逆文档频率、停用词处理；所以关键词和实体/术语更关键。
3. Microsoft 的 RAG 检索指南建议根据 query 类型选择 vector、full-text、hybrid，并提到 full-text 常用“从 query 提取关键词”，query rewriting 要兼顾 keyword-based 和 semantic-similarity search。
4. Weaviate、Redis 等搜索系统文档都强调 hybrid：semantic search 处理自然语言和概念相似，keyword search 处理精确术语、ID、代码、错误码。
5. 代码搜索领域的 CodeSearchNet 把 semantic code search 定义为“给定自然语言 query 检索相关代码”，但传统代码检索仍依赖 identifier/API/keyword matching，所以代码库场景尤其适合 hybrid。

## 建议

- 如果 RAG 是纯向量：用自然语言问句，短而具体。
- 如果是纯 BM25：用关键词、实体、标识符，去掉 `where is` 这类功能词。
- 如果是 hybrid：保留自然语言意图，同时提取关键词；最好两路检索后 rerank。
- 对代码库问题：自然语言问句加 domain keywords，必要时再加可能的符号名，例如 `api_key`, `auth`, `middleware`, `authenticate`。

## Sources

- [Microsoft Learn: Develop a RAG Solution - Information-Retrieval Phase](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-information-retrieval)
- [Weaviate: Keyword Search BM25](https://weaviate.io/developers/weaviate/concepts/search/keyword-search)
- [Weaviate: Hybrid Search](https://docs.weaviate.io/weaviate/search/hybrid)
- [Dense Passage Retrieval for Open-Domain Question Answering](https://arxiv.org/abs/2004.04906)
- [CodeSearchNet Challenge: Evaluating Semantic Code Search](https://arxiv.org/abs/1909.09436)
- [Redis: Semantic Search vs. Keyword Search](https://redis.io/en/blog/semantic-search-vs-keyword-search/)
- [RQ-RAG: Learning to Refine Queries for Retrieval-Augmented Generation](https://arxiv.org/abs/2404.00610)
- [Query Expansion Techniques for Information Retrieval: A Survey](https://arxiv.org/abs/1708.00247)
