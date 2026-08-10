# fix-13 butterflies 九类失败根因（§ 键码/credit 名单/键位映射/黑话词/驼峰缩写）

游戏：butterflies-episode-1（闭环于 2026-08-11，2065/0 干净闭环）

## 背景

butterflies 首轮 **2561/114**（当前地毯式排查最大失败量），9 类失败全为
真实模型跑出，逐条根因追查后 9 项通用机制修复 → 重跑 **2065/0 干净闭环**。
同时完成知识库六库蓝图升级（失败案例库首启，20 条真实案例入库）。

## 失败与修复（全部通用机制，无单游戏特判）

| # | 失败形态 | 条数 | 根因 | 修复 |
|---|---|---|---|---|
| 1 | `§m_quit ###` 语言键码 | 97 | localization 键值模板的键（§ 前缀+snake/camel 键名+` ###` 空值分隔符），值缺失无译义，模型回显恒败；**且** `en` 后缀是罗曼功能词 → `_is_multilingual_source` 误判 → learn 把结构键反向送译 | `_SECTION_KEY`（`^§[a-zA-Z0-9_]+ ###$`）→ 结构跳过；learn 入口 should_skip 过滤 + 清理 2 条错误入库 |
| 2 | `kangaroovindaloo    qubodup` | 8 | 制作人名单两列多空格对齐（双无空格 token + `{2,}` 空格），credit 判定只覆盖 from X/by X/created by/© 形态 | `_CREDIT_ALIGNED` → is_credit_like（无句子虚词才命中） |
| 3 | `k\nm\n/\nh` 键位映射 | 4 | 键盘快捷键组合提示（每行恰好 1 字符），无译义 | `_SINGLE_CHAR_KEYMAP_LINES`（`^(?:[^\r\n])(?:\n[^\r\n])+$`）→ 结构跳过 |
| 4 | `VSync` 回显 | 1 | VSync 是驼峰技术缩写 + UI 词典词：quality 门 camel_echo 已豁免 untranslated_text，但 proper_name_echo 的 UI 词检查仍拦截 → target_script_mismatch | proper_name_echo UI 词检查跳过驼峰技术缩写（全大写 SFX 仍拦截，反例测试） |
| 5 | `EN/` | 1 | 双语 TextAsset 语种分隔行，`_LOCALE_CODE` 只匹配 `^[a-z]{2}$` 不带斜杠 | `_LANG_CODE_WITH_SLASH`（`^[a-zA-Z]{2}/$`）→ 结构跳过 |
| 6 | `XXXX t'a` | 1 | 未命名角色/玩家标准占位名（XXXX 是名字占位符） | `_XXXX_PLACEHOLDER_NAME` → 结构跳过 |
| 7 | `（……她刚才说的"funk"是什么意思？）` | 1 | 译文质量高（黑话词引号保留+中文解释=本地化惯例），但 quoted_proper_terms 只豁免引号内 TitleCase 词，funk 小写 → target_script_mismatch | quoted_proper_terms 放宽：引号内全 TitleCase **或** 全非 UI 词典词（funk∉UI 词典 → 豁免；"play"∈UI 词典 → 仍判半翻，反例测试） |
| 8 | `Highraiser ft. inkoutlines, MC Cruel Addict` | 1 | ft.（featuring）音乐合作署名行，credit 判定未覆盖 | `_FT_CREDIT`（`\bft\.`）→ is_credit_like（无虚词才命中） |

## 知识库六库蓝图升级（与修复同步完成）

- **失败案例库**：KnowledgeBase.record_case()/search_cases() 接口（FAIL-00001
  标准格式：游戏/环境/问题/现象/根因/解决/影响范围/修复版本/失败类型）；
  20 条真实案例入库（baldis 12 项 + butterflies 8 项）；runner 自动沉淀
  钩子：每场失败按质量原因模式聚合入库 + 历史案例复用提示
- **六库种子**：unity_struct 2 / text_type 3 / component 4 / quality 2 /
  writeback_verify 2（共 12 条新增内置知识，总 21 条）
- **learn 污染修复**：结构键（should_skip 命中）不进 learn——§ 键码曾因
  `en` 罗曼功能词误判 multilingual_source 反向送译（2 条错误入库已清理）

## 关键实证链

| 场景 | 修复前 | 修复后 |
|---|---|---|
| §m_quit ### | 97 条回显恒败 | 结构跳过（识别层不进管线） |
| VSync | camel 豁免过质量门但 proper_name_echo 拦截 → 失败 | 驼峰缩写跳过 UI 词检查 → 放行 |
| "funk" 黑话词 | 引号内小写词不豁免 → 失败 | 引号内非 UI 词 + 在原文出现 → 放行 |
| 引号内 "play" | — | 仍是半翻 → 判失败（反例） |

## 验证

- butterflies 最终跑：**2065 条翻译 0 失败**，写回 1880 条 PASS
  （2561/114 → 2065/0，差值 496 条为识别层新增跳过）
- 全量测试 **1487 passed + 27 skipped，0 失败**（新增 8 个回归测试，
  含 4 条防误伤反例）
- 知识库：六库种子 21 条 + fail_case 20 条（FAIL-00001~00020）
- D:/游戏/butterflies-episode-1 `_汉化` 目录已删（做完一个删一个）
