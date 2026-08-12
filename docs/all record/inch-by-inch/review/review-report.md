# inch-by-inch 语义审核报告

- 审核模型：Qwen3.5-4B-Q4_K_M
- 审核条数：56（跳过回显/未翻译）
- 不合格：5 条（术语一致性 5 条）
- 术语沉淀：3 条词对 → 全局术语库（C5 门禁拒绝 0 条污染风险词对）

## C5 门禁拒绝清单（高频普通词单 token，无语境强制会误杀其他语境，不入全局库）


## 不合格清单

[e88] level0:asset#level0#1862/str/1
  原文：Play with Tutorial
  译文：开始教程
  问题：术语一致性——术语误用，Play 在游戏 UI 中应译为“开始”而非“播放”，且“与”字连接生硬，不符合游戏按钮动词习惯。
[e105] level1:asset#level1#3393/str/1
  原文：Shrinking Progress 100%
  译文：减少进度 100%
  问题：术语一致性——术语使用错误，'Shrinking' 在此语境下指进度条减少而非物理缩小，且'Progress'应译为'进度'而非'进度条'，整体表达不符合游戏 UI 规范。
[e112] level1:asset#level1#3455/str/1
  原文：RESUME WITH CURRENT SIZE
  译文：使用当前大小继续
  问题：术语一致性——术语严重错误，将游戏 UI 中的 Resume（继续）误译为简历，且未传达原文‘使用当前大小’的含义。
[e133] level1:asset#level1#3670/str/1
  原文：Carry Text
  译文：携带
  问题：术语一致性——术语使用错误，'Carry'在游戏UI中通常指'携带'或'持有'，而非'携带文本'这种生硬直译，且未体现游戏语境下的标准术语规范。
[e347] sharedassets2.assets:asset#sharedassets2.assets#36/str/2
  原文：Entering the wrong code would yield unexpted results.
I'd lose this Explodium and would have to start over!
  译文：我会失去这个 Explodium，不得不重新开始！
  问题：术语一致性——译文将原文中的游戏道具'Explodium'误译为'收入'，导致语义完全错误且术语使用不当。
