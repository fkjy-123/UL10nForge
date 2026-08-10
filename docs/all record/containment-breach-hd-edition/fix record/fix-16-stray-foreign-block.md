# 修复 16：外语混入块自愈升级（单字 → 独立实义词，容忍标点邻居）

## 问题

第五跑残留 2 条失败（EN 语言包 subtitles.jsonc / sceneStrings.subs 同一长句）：

> 原文：`Subject demonstrates extraordinary luck, and is able to fully control even the most fatal circumstances.`
> 译文：`该生物展现出了非凡的运气，能够完全掌控哪怕是最致命的 상황；同时…`

韩文「상황」（=情况，独立实义词）混入译文，**带空格隔开、右邻是中文分号「；」**。
第四跑的 `_cjk_surrounded`（左右邻都必须是汉字）判 False → 不清洗 → target_script_mismatch 恒败。

## 根源

外语混入形态升级：从单字助词（`该基金会의官方口号` 的 의）到**独立实义词**
（상황），左右邻是空格/中文标点而非汉字——旧判据「左右邻汉字」无法覆盖。

## 修复方案（块扫描替代单字邻接）

`_apply_quality` 外语自愈重写为块扫描：

```python
# 扫描连续的非中文非 ASCII 字母段（混入块）
spans: list[tuple[int, int]] = []
while i < n:
    if (ch.isalpha() and not ch.isascii()
            and not self._is_chinese_ideograph(ch)
            and ch not in entry.original):   # 原文回显的外语字符不构成块
        ...  # 向后扩展同类字符 → spans.append((i, j))
# 清洗条件：块 ≤4 字符 + 块前 8 字符与块后 8 字符内都有汉字
# （句中夹带才删——容忍空格/中文标点邻居）
# 删除时吞掉块前紧邻空白（'最致命的 상황' → '最致命的；'，不留悬空空格）
```

- **混入块**：连续的非中文非 ASCII 字母段（韩文/假名），段内字符不在原文
- **≤4 字符**：单字（의）、双字词（상황）、四字内夹带可删；实质外语内容（>4）不动
- **前后 8 字符内汉字**：句中夹带（前后都有中文语境）删除无损；
  **句尾独立词**（`爱丽丝 설정` 后无汉字）不清洗——那是译文主体内容而非夹带
- **原文含外语**（`게임 설정`→`設定です`）整体拦截，不清洗

## 修复代码位置

| 文件 | 位置 |
|---|---|
| hanhua/core/batch_translator.py | `_apply_quality` 外语混入块自愈段（`_cjk_surrounded` 方法删除） |
| tests/test_batch_translator.py | `test_stray_foreign_word_with_punctuation_healed`（新） |

## 验证

- 1513 passed（+2：韩文词带标点清洗；负例保持：爱丽丝 설정 / 設定です / Stefánsson 均不动）
- 第六跑 containment 全流程：**0 失败**（该 2 条清洗后通过）

## 防复发

- 判据从「单字符邻接」升级为「块 + 上下文窗口」，同时覆盖单字助词与独立实义词两种形态
- 标点/空格不再是屏障（中文标点是中文上下文的一部分），句尾独立词仍受保护
