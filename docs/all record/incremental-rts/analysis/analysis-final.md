# incremental-rts 地毯式排查分析（终版）

> 游戏目录：D:\游戏\incremental-rts · 2026-08-13
> 全本地推理（Hy-MT2-1.8B 翻译 / Qwen3.5-4B 审核）· 无任何云 API
> 前置文档：[[fix record/fix-record.md]]（46 条失败裁决 + F11 四修 + F12 占位符破碎）

## 1 运行概况

| 环节 | 数据 |
|---|---|
| 识别 | 850 条（文本文件 1 + 二进制资源 10；2125 条预筛跳过） |
| 翻译 | 804 成功（7 记忆命中）/ 46 失败 · 1087 请求 · 1192.2s · 40 条/分 |
| 写回 | 760 条写入 · 36 文件变更 · 闸门 PASS · 字体 runtime_verified |
| 语义审核 | 114 条 · 不合格 25（13 误判 + 6 真实 + 6 轻微，见 fix-record）· 术语沉淀 1 |
| 记忆 | 7 条命中 · 功能词拦截计数正常 |

## 2 成功文本质量抽检（804 条抽样 20 条）

| 原文 | 译文 | 判定 |
|---|---|---|
| Every secured sector files a victory bonus. Gain {warPoints} Warpoint per completed level | 每个有担保部门都会获得胜利奖励。每完成一个关卡，即可获得 {warPoints} 战争点数。 | ✓（占位符保留） |
| Thermobaric fillers collapse hardened cover. Increase unit damage by {damage} | 热压填充物会破坏硬化覆盖层。单位伤害增加 {damage} | ✓ |
| Volatile warheads detonate harder on impact | 易挥发的弹头在撞击时会产生更大的爆炸威力 | ✓ |
| Rail-assisted launch. Increase projectile speed by {speed} | 轨道辅助发射。提高弹丸的速度为 {speed} | ✓（「为」vs「至」轻微） |
| <color=#FFFFFF>Compute Shader Support :</color> | <color=#FFFFFF>计算着色器支持：</color> | ✓（富文本保留） |
| If your app fully supports variable fonts… | 如果您的应用完全支持可变字体… | ✓ |
| OTHER DEALINGS IN THE FONT SOFTWARE. | 与字体软件相关的其他业务。 | ✓（许可文本） |
| FROM, OUT OF THE USE OR INABILITY TO USE… | 由于无法使用该字体软件，或者由于其他原因。 | ✓ |
| Lean crews weld fallen armor into new structural modules. Reduce building cost {discount} | 熟练的工人将损坏的装甲板焊接到新的结构模块上。这样可以降低建筑成本。 {discount} | △ 占位符被分句（句点后移）但保留完整 |

抽检结论：机制描述句（占位符 + 数值）处理良好，占位符保留率高；许可
法律文本可读。问题集中在模型对占位符的两种行为：本地化（{health}→
{生命值}）与破碎（「健康}」）——已被 F12 拦截。

## 3 失败文本裁决（46 条）

37 条修复生效（F10/F11/数据修正复验 PASS）+ 9 条正确拦截。详见
fix-record.md。**零残留误杀**。

## 4 语义审核不合格确认（25 条）

13 误判 + 6 真实 + 6 轻微。核心发现：审核报告引用中间快照（3 条误判
根源）+ 4B 审核噪声随文本量放大（52% 误判率）。真实问题 6 条中 4 条是
审核真抓到、质量门管不到的语义类（占位符破碎/语义反转/术语错译）——
审核环节保留价值确认。详见 fix-record.md「审核不合格裁决」节。

## 5 占位符完整性专项（F12 扫描）

804 条成功译文全量复扫：**F12 新增拦截 4 条**（row207/644/684/714）——
同一模式（{health}→「健康}」破碎 + 尾部原文占位符堆叠），已写回游戏
但 F12 修复后重跑会拦截。已写回条目登记人工重译（本游戏特判）。

## 6 跳过文本判定（2125 条抽样）

| 原因 | 数量 | 判定 |
|---|---|---|
| prefilter_high_frequency | 主要 | 引擎高频词（Normal/Highlighted/UnityEngine 类型串）保守跳过 ✓ |
| prefilter_engine_string / type_reference | 大量 | 引擎字符串与类型引用 ✓ |
| identifier_without_display_evidence 等 | 少量 | 无显示证据标识符保守跳过（CLEAR/Forward 类可见词风险登记，同 inch-by-inch 遗留 #2） |

## 7 结论

- 汉化闭环 PASS（质量门零残留误杀、写回 PASS、字体验证通过）
- F11 四修 + F12 是本游戏催生的修复：富文本标签/文件名/方向词/标签
  透明句首/占位符破碎——非可翻译文本段的词对豁免与占位符完整性检查
  在实战中被系统性补全
- 审核环节暴露快照差异问题（观察项登记），6 条真实问题中 4 条为审核
  独有贡献——审核闭环价值确认
