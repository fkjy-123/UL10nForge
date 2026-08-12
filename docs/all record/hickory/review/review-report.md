# hickory 语义审核报告

- 审核模型：Qwen3.5-4B-Q4_K_M
- 审核条数：18（跳过回显/未翻译）
- 不合格：1 条（语义一致性 1 条）
- 术语沉淀：0 条词对 → 全局术语库（C5 门禁拒绝 0 条污染风险词对）

## C5 门禁拒绝清单（高频普通词单 token，无语境强制会误杀其他语境，不入全局库）


## 不合格清单

[e6] Hickory_Data/data.unity3d:asset#level0#395/str/0
  原文：So much chaos! Desolo and Benjamin pulled through like always. Jonathan saw for loops in Daniel's shaders. Wirovin's pul
  译文：Jonathan 在 Daniel 的着色器代码中发现了循环结构。
  问题：语义一致性——译文严重偏离原文含义，将编程概念（for loops, shaders）错误地翻译为游戏测试术语，且将“项目”误译为“测试”，导致语义完全错误。
