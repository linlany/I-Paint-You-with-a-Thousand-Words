# Retrieval query planner prompt

根据 `image-analysis.json` 和目标作者/人物的 corpus manifest，生成多路检索查询。只输出 JSON 数组，每个元素包含：

```json
{
  "query_id": "q-001",
  "facet": "observations|associations|composition|lighting|visual_anchors|text_visible",
  "query": "简短查询",
  "terms": ["term1", "term2"],
  "why": "该查询对应哪些视觉线索",
  "risk": "low|medium|high"
}
```

规则：

- 至少覆盖 `observations`、`associations` 和 `visual_anchors`，并覆盖一个构图/光线 facet；不要只生成一个总括句。
- `visual_anchors` 优先生成具体、可见、能代表画面的检索词；先用原始可观察词，再用较弱的抽象词；不要把抽象联想伪装成图片事实。
- 可生成同义词和跨语言词，但每个查询保留可解释的 `terms`。
- `scene_conflicts` 不用于生成正向查询；将其作为 rerank 阶段的负向过滤/惩罚条件传递，不要让冲突意象因为知名度提高排名。
- 不检索人物身份、敏感属性、医疗/犯罪判断或与图片无关的传记事实。
- 查询是检索条件，不是让模型续写作者文风的指令。

脚本 `scripts/build_queries.py` 可在没有 LLM 查询规划器时生成一个确定性的基线结果。
