# final-shot 修复记录（F24 调试日志模板串豁免）

## 问题：2 条失败全为调试日志模板误杀（2026-08-12 首轮实证）

final-shot 首轮翻译失败 2 条，全部来自 `Assembly-CSharp-firstpass.dll`
的 #US 字符串（内存/音频监控模块的 Debug.Log 格式串）：

| 原文 | 译文 | 旧判定 |
|---|---|---|
| `MEMORY: cur = {0}MB, max = {1}MB` | `内存：cur = {0} MB，max = {1} MB` | target_script_mismatch（`cur…max` 被当英文短语残留） |
| `CHANNELS: real = {0}, total = {1}` | 回显 | untranslated_text |

**真相**：这是 Unity 调试日志模板串——全大写标签（MEMORY/CHANNELS）
+ 冒号 + 小写变量赋值（cur/real/max/total 是脚本标识符，无语义）+
`{n}` 占位符。译文保留变量名（第一条，含中文翻译，译文质量好）或
整行回显（第二条，模型确认不可翻）都是正确行为——与 ffs 769 条
low 置信系统串（AndroidJNIHelper 警告类）同属「调试/日志文本」，
玩家不可见或仅调试可见。

## 修复（F24，系统性通用规则）

1. **quality.py**：新增 `is_log_template(text)`——形态
   `^[A-Z]{3,}:\s*[a-z]{2,}\s*=\s*\{[0-9]+\}`（全大写标签 + 冒号 +
   小写变量 + 等号 + 占位符）→ 调试日志模板串
   - untranslated_text 判定加 `not is_log_template` → 回显放行
2. **batch_translator.py**：
   - `_has_disallowed_chinese_target_letters` 顶部豁免 → 译文含中文
     时变量名保留不再误判英文残留
   - `_apply_quality` 无中文分支加 `not is_log_template` → 回显放行

**防过宽**：普通 UI 模板（`Score = {0}`——标签非全大写+冒号）、真 UI
文本（`SETTINGS: Volume = 50`——值非占位符）不满足形态 → 照常强制
翻译（测试实证）。

## 实证

- 恢复导入：320/320 通过（含 2 条修复后转通过）
- 写回：320 条译文 PASS · failed 0
- 测试：test_glossary_sanitize.py +10（豁免 3 形态 + 非模板 2 例不
  豁免）→ 全量 1656 passed

## 附带：恢复脚本 parse_export 多行修复

恢复流程（faerie/ffs 先例）复用中发现：导出文件中多行原文/译文跨行
存储（`Damage\npopups` 存为两行），原单行解析截断丢行 → 重建 entry
不完整 → 320 条全部误判失败。修复：字段标记状态机（原文：/译文：
后的非字段行续行拼接），320/320 精确导入。
