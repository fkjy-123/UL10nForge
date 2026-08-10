# 修复 19：全大写 ≤3 字母缩写回显豁免（SFX/BGM/UI）

## 问题

第一跑残留 1 条失败：`SFX`（音效设置标签）——模型回显 SFX，
target_script_mismatch 恒败。SFX 在 BUILTIN_UI_TERMS（→音效），
proper_name_echo 的 UI 词检查不豁免 → 判失败 → 重试耗尽模型仍回显
（1.8B 模型对单 token 缩写稳定回显，非驼峰缩写故 VSync 式豁免不覆盖）。

## 根因

UI 词典回显判失败的**设计意图**是「模型应翻译词典词」（防漏翻）。
但对全大写缩写词（SFX/BGM/FPS/UI）模型**能力不足**：无上下文单 token
缩写，1.8B 模型译不动的概率极高——重试死循环，最终恒败。

## 修复方案（proper_name_echo UI 词检查）

```python
and not any(
    (word.casefold() in _DISPLAY_WORDS_CASEFOLD
     or word.casefold() in _BUILTIN_UI_TERMS_CASEFOLD)
    and not is_camel_tech_abbreviation(word)
    and not (len(word) <= 3 and word.isupper())   # ← 新增：全大写缩写豁免
    for word in _ui_check_words(proper_name_words)))
```

影响面验证：词典内仅 `sfx` 为全大写 ≤3 字母；其余词典词
（Quit/Volume/Settings/Continue…）不受影响，回显照常判失败重试。

## 修复代码位置

| 文件 | 位置 |
|---|---|
| hanhua/core/batch_translator.py | `_apply_quality` proper_name_echo UI 词检查 |
| tests/test_batch_translator.py | `test_vsync_echo_passes_proper_name_echo` 更新（SFX→True，QUIT 作对照 False）；`test_real_echo_still_target_script_mismatch`、`test_native_actionable_ui_*`、`test_chat_batch_*` 改用 QUIT 验证重试路径 |

## 验证

- 1515 passed（含 SFX 豁免正例 + QUIT 失败对照）
- 第三跑 count-my-coins：**0 失败**闭环

## 防复发

- 全大写 ≤3 字母 = 通用缩写形态（SFX/BGM/UI/FPS/FAQ…），保留原文是
  界面惯例；4 字母以上全大写（QUIT/TOSS）照常要求翻译
