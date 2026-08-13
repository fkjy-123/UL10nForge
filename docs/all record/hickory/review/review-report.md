# hickory 语义审核报告

- 审核模型：Qwen3.5-4B-Q4_K_M
- 审核条数：13（跳过回显/未翻译）
- 不合格：1 条（术语一致性 1 条）
- 术语沉淀：0 条词对 → 全局术语库（C5 门禁拒绝 0 条污染风险词对）

## C5 门禁拒绝清单（高频普通词单 token，无语境强制会误杀其他语境，不入全局库）


## 不合格清单

[e12] Hickory_Data/data.unity3d:asset#level0#401/field/k:m_text
  原文：As was tradition with most of our jam games (starting around 2022) they've always featured a boss or some sort of huge e
  译文：Jam 游戏；Daniel 统一为丹尼尔，Emiliano 统一为埃米利亚诺，Coco 统一为科科，Yishan 统一为伊山，Wirovin 统一为维罗文
  问题：术语一致性——译文存在术语不规范及人物关系指代不清问题，且部分专有名词翻译未统一。
