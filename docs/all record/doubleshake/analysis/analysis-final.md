# doubleshake 分析终稿

> 闭环轮次：run3（2026-08-11 21:10）· 4329 翻译 / 41 失败 / 4198 写回
>
> 本轮聚焦**测试噪音文本治理 + 判定边界分类**——doubleshake 是
> 开发者测试填充文本混入的游戏（4370 条目，level0-3 场景资源含大量
> 乱串/filler），暴露 F15（长度头子串误报）、F16（乱串/连字符专名
> 豁免）、F17（术语动词用法豁免）三修复。
> 68 → 53（F16）→ 41（F17）失败收敛，全部系统性修复无单游戏特判。

## 1 失败分类总表（41 条 = 8 唯一原文）

| # | 原文 | 译文 | 分类 | 处置 |
|---|---|---|---|---|
| 1 | `reset catkus corral data` ×15 | `重置 catkus 数据` | catkus 是游戏核心专名（catkusBreed_00~09/catkusTrait/catkusInfo 130+ 键名 + Box Catkus/Lightbulb Catkus 写回成功佐证），模型保留专名正确 | **能力边界观察项**：纯小写专名与普通词漏翻（ram/ragdoll 测试固化）形态不可区分，豁免即误放行；保留原文安全 |
| 2 | `áÁéÉ` ×15 | `áÁéÉ`（回显） | 无语言内容符号串，模型无法翻译 | 能力边界合理保留 |
| 3 | `eng` ×4 | `eng`（回显） | ISO 语言代码（结构串，进池属识别盲区） | 能力边界合理保留（语言代码保留惯例） |
| 4 | `8<e@` ×4 | `8<e@`（回显） | 无语言内容符号串 | 能力边界合理保留 |
| 5 | `Take off the` ×1 | `Remove it from` | **原文碎片**（textpack_eng.json opt_wear_this3 拆句键值，无完整语义——模型回译英文） | 能力边界合理保留 |
| 6 | `The favorite drink of sleepy islanders...` ×1 | 译文把 `<c=hl_effect>` 改成 `<br>c=hl_effect>` | 模型破坏 rich-text 结构（placeholder/rich_text mismatch） | **质量门正确拦截**（结构破坏必须拒绝） |
| 7 | `catvilla` ×1 | `catvilla`（回显） | 专名（猫主题地点名，模型无法确定译法） | 能力边界合理保留 |
| 8 | `Howdy, Loam-arino!...`（F16 修复） | `嗨，Loam-arino！...` | 连字符专名 `arino` 段被当英文残留 | **F16 已修复** |
| 9 | `Come to Caliko Coast!!!!`+乱串 ×11、`Come to Caliko`+乱串 ×3（F16 修复） | `快来卡利科海岸吧！！！`+乱串保留 | 测试噪音块（aksjdhashd/asdlajsdhasjkdh/asd）保留被当英文残留 | **F16 已修复** |
| 10 | `Hm, I think 4 should do...`（F17 修复） | `嗯，我觉得选4就可以了...` | (miss, 未命中) 术语在动词用法 `hard to miss`（错过）误命中 | **F17 已修复** |

## 2 修复统计

- **F15**（run1 验证）：长度头自证子串误报——写回从「3 对象报同一头值」到四态全 PASS
- **F16**（run2 验证）：68 → 53——乱串豁免（3+ 连续辅音含 j/q/z/k + 噪音块子串）+ 连字符专名段豁免（14 条）
- **F17**（run3 验证）：53 → 41——术语动词用法豁免（d_scrap14）+ `ready`×7/`!suplex`×4 模型波动译出（`准备就绪`/`！挤压`）

## 3 跳过文本判定（2911 条，无该翻而跳）

三轮跳过数恒定 2911：textpack 键名（catkusBreed_XX/catkusPower_XX 等）+ 结构串（GUID/路径/版本号）+ 单字符/纯符号 + 无空格标识符（Unity 运行时）。逐条抽检无「该翻而跳」——catkus 键族是按键名跳过，其值（Box Catkus 等）正常翻译写回。

## 4 写回逻辑层审计（F11 真实输出）

- 知识库 5 条规则启用（fit_bytes_nul_padding / placeholder_preserve /
  textasset_encoding_preserve / unityevent_binding_preserve /
  logic_key_compare）✓
- report 210 条（疑似逻辑键，占比 5.0% 阈值边界，全真按钮/短词文本：
  stamp→印章、eye→眼睛、field→领域——复核通过）✓
- note 321 条（短词/常见按钮文本，正常可译）✓
- 扩容 1391 条（译文 UTF-8 > 原文，长度头自证通过）✓
- 回显跳过 131 条（译文==原文未写入）· revert 0 ✓
- 四态全 PASS · runtime_verified ✓

## 5 结论

**✅ 可闭环**。41 条失败全部低影响：15 条 catkus 专名边界（保留原文
安全）、15 条符号串、4 条语言代码、4 条符号串、1 条原文碎片、
1 条质量门正确拦截、1 条专名——**无逻辑功能损坏**。F15/F16/F17
经真实链路验证生效。
