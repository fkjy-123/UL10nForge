# 修复 22：译文判定两项修正（拼写变体豁免 / 单残留词补译）

## 问题

83 条失败中 2 条是**真实游戏文本被误判**——质量门把正确译文判失败 →
重试耗尽恒败（玩家反而看不到任何翻译）：

### 1. 连字符拼写变体误判（hihat cymbal）

原文 `hihat cymbal` → 模型译文 **`Hi-hat 钹`**——正确（Hi-hat 是踩镲
标准拼写，连写 hihat 拆成标准写法）。但 `_ENGLISH_WORD` 把译文拆成
`Hi`/`hat`，`hat` 不在原文词集（原文是连写 `hihat`）→ 当普通词残留
→ target_script_mismatch 恒败。

### 2. 单残留词术语半保留（Uka-Uka 长句）

原文 `You collected an invitation to an Uka-Uka Trial...` → 模型译文
**高质量中文**仅 `warp` 残留（「站在 warp 房间的中央」——warp room
传送房间术语半保留）。词级补译（_repair_word_residue）只处理英文
**短语**（`_ENGLISH_PHRASE` 两词+间隔），`warp 房间` 中 warp 是孤立
单残留词 → 无补译路径 → 判定失败 → 重试模型稳定输出 warp 残留 →
死循环恒败。

## 修复方案

### 拼写变体豁免（batch_translator._apply_quality）

```python
# 译文连字符词去连字符后等于原文词 → 合法拼写变体（hihat↔Hi-hat），
# 其分词（hat）残留豁免。要求原文真含连写词（防幻觉）
for vm in re.finditer(r"[A-Za-z]{2,}(?:-[A-Za-z]{2,})+", semantic_ascii):
    if vm.group(0).replace("-", "").casefold() in source_terms_cf:
        dehyphenated_variants.update(findall(vm.group(0)))
```
单词循环与短语循环均加 `if word.casefold() in dehyphenated_variants: continue`。

### 单残留词补译（batch_translator._repair_word_residue）

- 收集：译文残留孤立小写词（3-16 字符、在原文、非功能词/UI 词典/
  物理键、译文已含中文、短语覆盖的不重复）→ 补译（限 2 词防请求爆炸）
- 补译输出翻译 → 整词边界替换（`_replace_word_first` 防 the→other 子串）；
  回显 + confirmed 非空 → 模型确认术语保留 → word_residue_exempt 豁免放行
  （短语回显仍维持失败，防漏翻偷懒）

## 修复代码位置

| 文件 | 位置 |
|---|---|
| hanhua/core/batch_translator.py | dehyphenated_variants 计算 + 两处循环豁免；_repair_word_residue 单残留词收集/替换/回显豁免；_replace_word_first |
| tests/test_batch_translator.py | 4 个测试（变体豁免正反 + 单词补译正反） |

## 验证

- 1522 passed（+7 本轮全部修复）
- hihat→Hi-hat 钹：True（原 False）；Uka-Uka 首译含 warp：False→
  词级补译回显确认 → True
- 第二跑 crash-back-in-time：见 analysis

## 防复发

- 连写-拆写变体是术语常见拼写差异（hihat/hi-hat、warp-room 类）——
  原文真含连写词才豁免，无幻觉空间
- 单残留词补译继承词级补译的全部防幻觉条件（词在原文/非功能词/
  非词典），只放宽「必须成短语」一条——术语半保留获得与专名同等的
  确认路径
