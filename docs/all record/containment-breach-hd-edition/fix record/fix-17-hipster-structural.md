# 修复 17：hipster ipsum 占位文本结构跳过（翻译/回显双路径封死）

## 问题

第五跑残留 4 条失败（level3-6 assets）：

> 原文：`XOXO keytar glossier mumblecore. Tote bag listicle normcore kinfolk kogi hoodie four dollar toast meh…`
> 译文：`XOXO：Keytar风格，更精致、更柔和。`（模型**翻译**了占位文本）

模型对占位文本行为**随机**：回显 → `is_lorem_ipsum_placeholder` 豁免路径放行；
翻译成中文 → 多行/内容比对 newline_mismatch、line_content_mismatch **恒败**。
回显豁免只覆盖随机行为的一半，无法作为稳定出口。

## 根源

hipster ipsum 检测（第四跑加的词表）挂在 `is_lorem_ipsum_placeholder`（quality 层），
只处理「模型回显」分支；模型翻成中文时，占位文本已被正常译文对待，
quality 回显豁免路径根本不触发。

## 修复方案（跳过优先于翻译）

占位文本**根本不进翻译池**——结构跳过是唯一稳定出口（同古典 Lorem ipsum 先例）：

```python
if _LOREM_IPSUM.match(s) or is_hipster_ipsum(s):
    return True   # is_hard_structural：lorem/hipster 占位文本不翻译
```

- 词表 + `is_hipster_ipsum` **下沉到 placeholders.py**（无依赖）：quality 已导入
  placeholders，反向导入成环，词表不能留在 quality
- quality.is_lorem_ipsum_placeholder 复用 placeholders.is_hipster_ipsum（单一来源）

## 修复代码位置

| 文件 | 位置 |
|---|---|
| hanhua/core/placeholders.py | `_HIPSTER_IPSUM_WORDS`（37 词）+ `is_hipster_ipsum` + is_hard_structural 接入 |
| hanhua/core/quality.py | 删本地词表/`_is_hipster_ipsum`，改导入复用 |
| tests/test_placeholders.py | `test_hipster_ipsum_is_structural`（新，正 2 反 2） |

## 验证

- 1513 passed（+1；test_quality.py::test_hipster_ipsum_is_placeholder 保持——函数签名不变）
- 第六跑 containment 全流程：**0 失败**（level3-6 的 4 条占位文本 skipped，不进翻译）

## 防复发

- 跳过判定在翻译池入口（is_hard_structural），模型行为随机不再影响结果
- 词表单一来源（placeholders），quality/结构层引用同一检测
