# 222am 修复记录

## 修复 5：_glossary_keep_echo（hiss pop collection 回显豁免）

- **现象**：`hiss pop collection` 译文回显英文 → glossary_mismatch / 失败
- **根因**：keep 型术语（source==target casefold，learn_proper_names 自动
  沉淀的专名保留映射）是模型**按规范保留**——回显不是失败。质量门
  glossary_mismatch 把保留当漏译
- **修复**（`hanhua/core/quality.py` `_glossary_keep_echo`）：
  keep 型术语全部覆盖原文 + 译文无中文 + 字母序列一致 → 豁免
- **验证**：222am run4 66 条 0 失败（本游戏闭环）

## 待办 A（登记，不在本游戏特判）

NOTES AND CREDITS.txt 20 条音效/场景标签行（shower、wind_1 等）识别阶段
跳过，同文件 17 条同类行（night driving、window 等）进入翻译池——跳过
判定规律未定位到代码层（与长度/词数/相邻行无关）。后续游戏出现同类
现象时以真实样本锚点定位识别判定，统一修复。

## 过程修复（本游戏未使用，历史沉淀）

- 知识库译例注入：hiss pop collection→Hiss Pop Collection（proper_name,
  keep）——format_reference_pairs 并入 glossary references
- 六库知识库体系（2026-08-11 全局升级，见 `docs/知识库体系.md`）
