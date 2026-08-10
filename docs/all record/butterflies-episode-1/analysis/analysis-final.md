# butterflies-episode-1 分析（最终跑）

时间：2026-08-11 ｜ 模型：Hy-MT2-1.8B-Q6_K ｜ 2065 条翻译 0 失败（修复后闭环）

## 首轮失败 → 修复 → 闭环

首轮 **2561/114 失败**（本轮最大失败量，9 类失败模式全为真实模型跑出），
修复 9 项通用机制后重跑 **2065/0 干净闭环**（差值 496 条为识别层新增结构
跳过——§ 键码/credit 名单/键位映射等无译义文本不再进翻译管线）。

## 成功文本逐条验证（关键条目抽检）

| 原文 | 译文 | 评价 |
|---|---|---|
| (...the funk she just call me?) | （……她刚才说的“funk”是什么意思？） | ✅ 黑话词引号保留 + 中文解释，本地化惯例 |
| VSync | VSync | ✅ 驼峰技术缩写保留原文（界面标准术语） |
| outstanding citizen（他场样本） | 杰出的公民 | ✅（此前修复覆盖） |

## 失败模式 → 修复对照（114 条全灭）

| # | 失败形态 | 条数 | 根因 | 修复 |
|---|---|---|---|---|
| 1 | §m_quit ### 等语言键码 | 97 | localization 键值模板的键且值缺失，无译义；en 后缀被罗曼功能词误判 multilingual_source 反向送译 | `_SECTION_KEY` 结构跳过 + learn 入口过滤结构键 |
| 2 | kangaroovindaloo    qubodup 名单 | 8 | 制作人名单两列多空格对齐，credit 判定未覆盖 | `_CREDIT_ALIGNED` → is_credit_like |
| 3 | k\nm\n/\nh 键位映射 | 4 | 键盘快捷键提示，多行单字符形态未覆盖 | `_SINGLE_CHAR_KEYMAP_LINES` 结构跳过 |
| 4 | VSync | 1 | 驼峰缩写+UI 词典词：camel 豁免过质量门，proper_name_echo 的 UI 词检查仍拦截 | proper_name_echo 跳过驼峰技术缩写 |
| 5 | EN/ | 1 | 双语 TextAsset 语种分隔行 | `_LANG_CODE_WITH_SLASH` 结构跳过 |
| 6 | XXXX t'a | 1 | 未命名角色占位名 | `_XXXX_PLACEHOLDER_NAME` 结构跳过 |
| 7 | “funk” 黑话词引号保留 | 1 | quoted_proper_terms 只豁免 TitleCase | 放宽：全 TitleCase 或全非 UI 词典词 |
| 8 | Highraiser ft. inkoutlines | 1 | ft.（featuring）合作署名行 | `_FT_CREDIT` → is_credit_like |
| 9 | （learn 污染）§m_language_en ### | 2 条入库 | 结构键被学习闭环当成 multilingual_source | learn 入口 should_skip 过滤 + 清理错误条目 |

## 知识库联动（本轮首启六库蓝图）

- **失败案例库（fail_case 域）**：20 条真实案例入库（FAIL-00001~00020，
  含本场 8 类），runner 自动沉淀钩子：后续每款游戏失败模式自动聚合入库，
  命中历史案例时打印复用提示
- **六库种子规则**：unity_struct / text_type / component / quality /
  writeback_verify 域 12 条内置知识（21 条种子全就位）
- **learn 污染修复**：结构键（should_skip 命中）不再进入知识库学习

## 遗留

- 无失败条目。写回 1880 条 PASS。

## 结论

2065/0 干净闭环。butterflies 是当前最大文本量游戏（4969 条目），暴露的
9 类失败全部修复为通用机制；§ 键码（97 条）是首个「语言文件键值模板」
样本，识别层 + learn 侧双重修复杜绝复发。进入下一游戏。
