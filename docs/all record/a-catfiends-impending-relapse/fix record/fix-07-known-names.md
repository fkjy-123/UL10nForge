# 修复 7：专名自动收集注入（known_names 从未生效）

## 问题

a-catfiends 第六跑残余 2 条专名误译（253 条中）：
1. `GREATER LABYRINTH` → 「大咽部」（LABYRINTH 被误译成解剖词，专名丢失）
2. `GLISLYA SPECIALIST FROM THE ACADEMY OF CORRADAILE` → 「来自科拉达莱学院的专业讲师」（GLISLYA 丢失）

## 根源

`hanhua/core/prompts.py` 的 `build_system_prompt(profile, glossary_lines, known_names=None)` 定义了
【已确认专名·全游戏保持一致】注入段，但**全项目没有任何调用方传入 `known_names`**——两处调用
（`ui/pages/translate_page.py:374`、`scripts/all_record_runner.py`）都只传 `(profile, glossary_prompt)`。
专名保护段形同虚设，HY-MT2-1.8B 对全大写造词（GLISLYA/WRECCA/KALKAM/LABOLIS-7）的保留不稳定。

## 修复方案（通用机制，非单游戏特判）

### 1. `hanhua/core/prompts.py`：新增 `collect_known_names`

**启发式**：全大写词 `[A-Z][A-Z0-9]{2,}(?:-[0-9]+)?`（含 LABOLIS-7 型带数字造词），
排除英语基础词表后，按「频率 ≥2 或 长度 ≥5」判定为疑似专名，注入 prompt。

**词表**：`wordfreq top_n_list('en', 5000)` ∪ 内置游戏叙事补充词表
（cavern/caution/quest/dungeon 等游戏高频词）∪ 词形变化匹配
（`_is_common_word`：复数 s/es、过去式 ed、进行时 ing 去尾查词干，含去 e 变体）。

**防误收**：
- 间隔大写（`* Y A W N *`）拆成单字母，正则天然排除
- 全大写普通词（YOU/THE/DEATH/CAUTION/BACTERIAL）全部命中词表被过滤
- wordfreq 缺失时降级为内置词表（保守多收，不阻断流程）

**实证**（a-catfiends 全池 1595 条）：收 31 词 → 真专名 12 个
（GLISLYA/WRECCA/KALKAM/KUR/LYNCH/LABOLIS-7/KARKINOS-9/UCLA/USAFA/ACOLYTES/MAELSTROM/HYPERSPACE）
全收；噪音（BACTERIAL/PHENOMENA 等叙事词）被词表过滤大半，残余噪音回显时有质量门
「无小写词 → 专名回显合理放行」豁免，风险可控。

### 2. `scripts/all_record_runner.py`：接入注入

翻译前从全部提取文本收集专名：

```python
entries = [_entry_from_row(r) for r in project.store.get_entries()]
system = build_system_prompt(
    profile, glossary_prompt,
    known_names=collect_known_names([str(e.original or "") for e in entries]),
)
```

（`entries` 提取从 system 构建之后移到之前；`TextEntry` 用 `.original` 属性而非 dict `.get`。）

## 修复代码位置

| 文件 | 位置 |
|---|---|
| hanhua/core/prompts.py | `collect_known_names` / `_is_common_word` / `_GAME_COMMON_WORDS` / `_build_common_words` |
| scripts/all_record_runner.py | run_game 翻译段（build_system_prompt 调用） |
| tests/test_v2.py | `test_collect_known_names` / `test_known_names_injected_into_system_prompt` |

## 验证

- 单测：`test_collect_known_names`（专名必收/常见词必不收/排序/空输入）、
  `test_known_names_injected_into_system_prompt`（注入段实际生效）— 全量 329 passed
- 第七跑 a-catfiends 全流程重跑验证（专名保留 + 新速度参数质量不降）

## 防复发

- 注入段有了真实输入，专名保护不再空转
- 词表是通用语言资源 + 通用启发式，任何游戏生效，无单游戏特判
- 测试锁定行为，回归即失败

## 关联修复

同轮速度优化：`local_concurrency 2→4`（GPU 上限）、`local_batch_size 16→24`
（请求数 -33%）。质量不变量：模型、单条 prompt 结构不变，仅并行度与批大小。
