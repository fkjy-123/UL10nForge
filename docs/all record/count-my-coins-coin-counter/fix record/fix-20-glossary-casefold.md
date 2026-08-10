# 修复 20：术语保留映射大小写不敏感（KRAPOS→Krapos 变体）

## 问题

第二跑残留 1 条失败：`Krapos`（角色专名）回显被判 glossary_mismatch——
术语库自动沉淀 `KRAPOS→KRAPOS`（全大写保留映射），模型回显 TitleCase
变体 `Krapos`。

## 根因

`learn_proper_names` 的保留检测用 casefold（`n.casefold() in
e.translation.casefold()`——Krapos/KRAPOS/krapos 都算保留）→ 学到
KRAPOS→KRAPOS。但 quality 的 glossary_mismatch 检查
`target not in normalized` **大小写敏感**：全大写 target `KRAPOS`
不在 TitleCase 译文 `Krapos` 里 → 误判失败。**学习与检查自相矛盾。**

## 修复方案（quality.py glossary_mismatch）

```python
if (source_term_applies(source, entry.original)
        and target.casefold() not in normalized.casefold()):
```

- 专名保留映射与模型回显是**同一词的形态变体**（大小写变体）→ 放行
- 人工术语（中文 target）不受影响：模型回显英文（`Settings`）时
  target `设置` casefold 仍不在 `settings` 里 → 照常判失败

## 修复代码位置

| 文件 | 位置 |
|---|---|
| hanhua/core/quality.py | `glossary_mismatch` target 检查 casefold |
| tests/test_quality.py | `test_glossary_proper_name_echo_casefold_allowed`（正 1 反 1） |

## 验证

- 1515 passed（+1）
- 第三跑 count-my-coins：**0 失败**闭环

## 防复发

- 学习与检查两侧统一 casefold——任何全大写/TitleCase 变体自动覆盖
