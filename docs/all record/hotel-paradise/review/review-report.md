# hotel-paradise 语义审核报告

- 审核模型：Qwen3.5-4B-Q4_K_M
- 审核条数：3（跳过回显/未翻译）
- 不合格：1 条（术语一致性 1 条）
- 术语沉淀：0 条词对 → 全局术语库（C5 门禁拒绝 0 条污染风险词对）

## C5 门禁拒绝清单（高频普通词单 token，无语境强制会误杀其他语境，不入全局库）


## 不合格清单

[e3] mainData:asset#mainData#105/str/0
  原文：A Game by Kai Clavier

<b>Paintings and Photos</b>
The City of Winnipeg Archives
Various public domain paintings
USGS De
  译文：KaiClavier 创作的《Vaporizer》
  问题：术语一致性——歌曲标题大小写错误、封面制作动词误用、部分专有名词未汉化。
