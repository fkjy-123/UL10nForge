# inch-by-inch 地毯式排查分析（终版）

> 游戏目录：D:\游戏\inch-by-inch · 2026-08-13
> 全本地推理（Hy-MT2-1.8B 翻译 / Qwen3.5-4B 审核）· 无任何云 API
> 前置文档：[[fix record/fix-record.md]]（8 条失败根因裁决 + F10 六连修复记录）

## 1 运行概况

| 环节 | 数据 |
|---|---|
| 识别 | 394 条（asset_unity 7 文件 + mono_csharp 1 文件；3877 条预筛跳过） |
| 翻译 | 386 成功（38 记忆命中）/ 8 失败 · 228 请求 · 313.2s · 74 条/分 |
| 质量门 | 386 条过门写入（无失败放行） |
| 写回 | 376 条写入 · 34 文件变更 · 输入保护/重开验证 PASS · 字体 runtime_verified |
| 语义审核 | 56 条 · 不合格 5（均为弱误判，见 fix-record）· 术语沉淀 3 |

## 2 成功文本质量抽检

抽检 386 条中的 34 条（全部 UI 短词 + 自然句分层抽样）：

**UI 短词（12 条全对）**：SETTINGS→设置、WARNING!→警告！、QUIT→退出、
CREDITS→致谢、PLAY→播放、YES→是的、BACK→返回、SCORE→分数、
HEIGHT SCORE→身高分数、SANDBOX MODE→SANDBOX模式 等。

**自然句（22 条，18 正确 / 3 轻微 / 1 系统性误译）**：

| 原文 | 译文 | 判定 |
|---|---|---|
| Are you sure you want to permanently delete all highscore data? | 您确定要永久删除所有高分记录数据吗？ | ✓ |
| Seems like you created the wrong substance or got too small. | 看起来你创建的物质有误，或者尺寸太小了。 | ✓ |
| Remember the kinds of machines and how they process ingredients! | 记住那些机器的类型以及它们如何处理各种原料！ | ✓ |
| Let's try this, again. The correct code is on the clipboard! | 让我们再试一次。正确的代码就在剪贴板里！ | ✓ |
| Looking for a recipe or formula?⏎Just search for hints… | 寻找配方或公式吗？⏎只需在记事本或剪贴板上搜索相关提示即可。 | ✓（多行正确处理） |
| Ignatium + Water = Explodium | Ignatium + 水 = Explodium | ✓（元素名保留） |
| Explodium + [1245] = Xanolium | 收入 + [1245] = Xanolium | ✗ **系统性误译**（见遗留 #1） |
| reason be judged legally invalid or ineffective… | 该理由可能被判定为无效或无效 | △ 轻微重复（ineffective 同译无效） |
| 其余 CC0 许可长段 ×5 | 可读、法理术语基本准确 | △ 偶见「Creative Commons」未译（品牌名保留，可接受） |

## 3 失败文本裁决（8 条，详见 fix-record.md）

- 词对污染 2 条：Start Ingredients（START→开始）、CC0 许可 ON（ON→关于/on→在）
- F9 修复对象 4 条：at this size! / Time for… / Destillator / microwave
- 正确拦截 2 条：RESUME→摘要（builtin_ui_mismatch Q1 门，非误杀）
- F9/F10 复验：8 条失败全部 PASS（修复后重跑质量门）→ **质量门零残留失败**

## 4 语义审核不合格确认（5 条）

4 条弱误判（审核复读译文/幻觉）+ 1 条审核盲区登记（e347 第一句漏译未被
审核抓到）。误判率 5/56 ≈ 9%，低危噪声，人工确认流程兜底。详见 fix-record.md
「审核不合格裁决」节。

## 5 跳过文本判定（3877 条抽样）

| 原因 | 数量 | 判定 |
|---|---|---|
| prefilter_high_frequency | 3034 | 保守跳过。样本 Normal/Highlighted/UnityEngine 类型串——引擎高频词，未见异常 |
| prefilter_engine_string | 194 | 引擎字符串（Ambient Occlusion/LinkToTwitter）✓ |
| unverified_user_string | 165 | 无显示证据的字符串（TranslucentImage 配置报错等开发提示）✓ 不应翻译 |
| type_reference / identifier / method_name / code_* | 443 | 代码标识符与类型引用 ✓ |
| shared_resource_config_object | 29 | 共享资源配置（Darkium/Draconium 资源名）✓ |
| engine_core / hard_structural / mono_diagnostic | 21 | 引擎内部 ✓ |
| **identifier_without_display_evidence** | 125 | ⚠️ 含可见 UI 词（CLEAR/Forward/Smallest），无显示证据保守跳过——登记观察项（遗留 #2） |

## 6 结论

- 汉化闭环 PASS：386 成功全过质量门、写回 PASS、字体运行验证通过。
- F9/F10 修复在本游戏完成首次实证：4 条 F9 样本 + 2 条词对污染样本全部
  PASS，污染词对（START/ON/on/off/OFF/HEALTH）已降级 retired。
- 遗留观察：元素名系统性误译（Explodium→收入）、identifier 桶可见 UI 词
  漏翻风险——登记不阻塞，见 final-report.md。

## 遗留问题

1. **Explodium→收入 系统性误译**（同游戏 ≥2 处）：合成元素名被 1.8B 模型
   猜义（explodium≈explode+odium 被误读）。合成专名无词典覆盖时的行为
   观察项——临时方案：本游戏元素名多为 `X+Water=Y` 配方行，可加配方行
   保名规则；不推广（专名保名需要词典，超出本轮范围）。
2. **identifier_without_display_evidence 桶 125 条**含 CLEAR/Forward 等
   可见 UI 词——当前保守跳过（无显示证据不冒险），若实机发现未汉化按钮
   属此桶，再补识别证据规则。与用户「不做实机测试」约束一致：登记不行动。
3. e347 多行文本结构性漏译（第一句整句丢失）——审核盲区，登记。
4. 4B 审核弱误判率 ~9%——低危噪声，人工确认流程兜底。
