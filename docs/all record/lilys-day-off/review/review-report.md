# lilys-day-off 语义审核报告

- 审核模型：Qwen3.5-4B-Q4_K_M
- 审核条数：98（跳过回显/未翻译）
- 不合格：2 条（自然度/风格 1 条、语义错误 1 条）
- 术语沉淀：0 条词对 → 全局术语库（C5 门禁拒绝 0 条污染风险词对）

## C5 门禁拒绝清单（高频普通词单 token，无语境强制会误杀其他语境，不入全局库）


## 不合格清单

[e259] sharedassets0.assets:asset#sharedassets0.assets#257/field/k:m_Text
  原文：For making Lily's Day Off my most successful game yet!
  译文：这真是我迄今为止最成功的游戏！让莉莉的休息日如此美好！
  问题：自然度/风格——译文语序生硬，未体现原文感叹语气，且将游戏名称误译为普通名词。
[e652] Managed/Assembly-UnityScript.dll:us#32544
  原文：Save it for the judge. You're coming downtown with us.
  译文：记住它，以便法官使用。
  问题：语义错误——原文'Save it'在上下文中意为'记住它'或'记下它'，译文将其错误理解为'保存文件'，属于严重的语义偏差和幻觉。
