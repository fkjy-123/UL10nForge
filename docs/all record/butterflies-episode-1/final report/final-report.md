# butterflies-episode-1 最终报告（闭环）

闭环跑：2026-08-11 ｜ 工具版本：0.25.0 前夜（butterflies 九类修复 + 知识库六库升级）

## 总体状态：✅ 干净闭环（修复后重跑通过）

| 模块 | 结果 | 说明 |
|---|---|---|
| 识别 | 9 项结构规则新增 | § 键码 97 / credit 名单 8 / 键位映射 4 / EN/ / XXXX / ft. 名单 |
| 翻译 | **2065 成功 / 0 失败** | 首轮 2561/114 → 修复 9 项 → 2065/0 |
| 写回 | 1880 条写入 | 重开验证 PASS，原子发布 |
| 清理 | `_汉化` 目录已删 | 做完一个删一个 |

## 修复（fix-13，9 项全通用机制）

1. `_SECTION_KEY`：§ 前缀语言键码结构跳过（97 条最大单类）
2. `_CREDIT_ALIGNED`：多空格对齐 credit 名单跳过（8 条）
3. `_SINGLE_CHAR_KEYMAP_LINES`：多行单字符键位映射跳过（4 条）
4. proper_name_echo 跳过驼峰技术缩写（VSync 回显放行）
5. `_LANG_CODE_WITH_SLASH`：EN/ 语种分隔行跳过
6. `_XXXX_PLACEHOLDER_NAME`：占位名跳过
7. quoted_proper_terms 放宽：引号内黑话词豁免（"funk" 放行，"play" 仍拦）
8. `_FT_CREDIT`：ft. 音乐合作名单跳过
9. learn 入口过滤结构键（§ 键码污染修复 + 清理 2 条错误入库）

## 知识库（六库蓝图升级，本场首启）

- 六库种子规则 21 条（新增 unity_struct/text_type/component/quality/
  writeback_verify 12 条）
- 失败案例库 20 条（FAIL-00001~00020，标准格式）+ record_case/search_cases
  接口 + runner 自动沉淀钩子

## 验证

- 全量测试 **1487 passed + 27 skipped，0 失败**（新增 8 回归 + 4 反例）
- 关键条目译文抽查：黑话词引号保留 / VSync 保留原文
- 写回 1880 条 PASS

## 结论

butterflies 是地毯式排查至今最大文本量游戏（4969 条目），114 条失败 9 类
模式全部修复为通用机制并闭环；知识库从「text/file/rule 三形态」升级为
六库蓝图，真实案例开始持续积累。进入下一游戏。
