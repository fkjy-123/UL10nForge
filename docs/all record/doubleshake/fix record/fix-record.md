# doubleshake 修复记录

> 闭环轮次：run1 68 失败 → run2 53（F16）→ run3 41（F17）· 写回 4198 PASS
>
> 本轮聚焦**测试噪音文本 + 判定边界治理**——doubleshake 暴露 3 个
> 修复（F15/F16/F17），全部为系统性通用规则，无单游戏特判。

## F15 长度头自证子串误报

**现象**：写回失败「译文 '任务被发现啦！' 长度头 1048146803 ≠ 实际
字节 21（字符串边界被破坏）」——3 个对象报同一头值 1048146803
（0x3E797373 = "ssy>"）。

**根因**：`<w=sassy>Quest Discovered!`（26B 含标签）与 `Quest
Discovered!`（17B）是相邻独立字符串，写回后译文在 raw 中出现两次
——标签字符串内部（前 4 字节 "ssy>"）+ 独立字符串（前 4 字节长度头
21）。`raw.find(payload)` 找到第一个位置（标签内）把标签文本当长度头
误读。

**修复**（`logic_audit.py::verify_string_length_headers`）：find 循环
遍历**所有**出现位置，任一位置长度头匹配即通过；全部不匹配才判定
边界破坏。子串位置（前 4 字节非长度头）不再误报。

**验证**：doubleshake 重跑写回 PASS（四态全 PASS）· 测试
`test_verify_length_headers_skips_embedded_substring`（标签内子串不
误报）+ `test_verify_length_headers_detects_broken_header`（真破坏
仍报）。

## F16 乱串/连字符专名豁免

**现象**：`Come to Caliko Coast!!!!`+多行乱串（测试文本）译文保留
`aksjdhashd`/`asdlajsdhasjkdh`/`asd` 被判 target_script_mismatch
（14 条）；`Howdy, Loam-arino!` 译文保留 `arino` 被判
target_script_mismatch（1 条）。

**根因**：
- 原文是开发者测试噪音文本（乱串 + filler + 彩蛋句同条目），模型
  正确翻译可译部分（Caliko→卡利科海岸、filler→填充物）、保留不可译
  噪音串——`_kept_word_plausible` 的键盘噪音判定只认「重复 3-gram」
  （sdfsdfsdf），一次性乱串（aksjdhashd 无重复 3-gram）漏判
- `Loam-arino` 连字符专名的第二段 `arino` 是专名的一部分，被当
  独立小写词英文残留

**修复**（`batch_translator.py`）：
- `_noise_blocks`：原文噪音块判定 = ≥8 字符 + 重复 3-gram 或 ≥6
  字符 + **罕见辅音连缀**（3+ 连续辅音含 j/q/z/k——英语真实词中
  j/q/z 不参与辅音连缀、k 仅双连，length 的 ngth/spring 的 spr 等
  真实组合不含这些字母，照常判漏翻）
- `_kept_word_plausible` 扩展 3 条形态特征：
  ① ≥6 字符 + 罕见辅音连缀（aksjdhashd 类一次性乱串）
  ② 词是原文噪音块子串（asd ⊂ asdasdasdasd）
  ③ 词是原文连字符专名段（Loam-arino 的 arino）
- 普通英语词（ram/ragdoll/name/length/spring）不具备上述特征 →
  仍判漏翻失败（测试固化不破）

**验证**：重跑 68 → 53（15 条修复）；测试
`test_noise_and_hyphen_proper_names_allowed` +
`test_rare_consonant_run_noise_allowed` +
`test_common_word_leftovers_still_target_script_mismatch` 扩展
（spring/length 真词仍失败）。

## F17 术语动词用法豁免

**现象**：`Hm, I think 4 should do. The seeds grow in high places
around the island, and shouldn't be hard to miss.` 译文「嗯，我觉得
选4就可以了。这些种子生长在岛屿上的高处，应该不会容易遗漏吧。」——
译文语义完整正确，被判 glossary_mismatch。

**根因**：知识库 loaned_word 术语 `miss → 未命中`（deadbeat 音游 HUD
判定标签 `miss: 999` 实证）在 `shouldn't be hard to miss` 中被整词
匹配——此处的 miss 是动词「错过/遗漏」（译文「遗漏」正确），与术语表
的标签含义无关。`source_term_applies` 是纯词级匹配，无语境区分。

**修复**（`quality.py::_glossary_verb_usage`）：术语词在原文中前邻
to 不定式或助动词（can/could/will/would/should/may/might/must/
do/does/did/not/never/缩写）→ 该出现是动词用法，与术语表含义无关
→ 豁免。守卫与 `_glossary_proper_phrase` 一致（UI 词典词/专名形态
术语不适用）。`miss: 999` 标签格式前邻冒号 → 不豁免（deadbeat
修复触发不受影响）。

**验证**：重跑 53 → 41（d_scrap14 修复 + ready/!suplex 模型波动
译出）；测试 `test_glossary_verb_usage_exempted`（动词用法豁免 +
标签格式仍失败）。

## 观察项（不修复，记录判断依据）

1. **纯小写专名（catkus）与普通词漏翻形态不可区分**：`reset catkus
   corral data` 15 条失败——catkus 是游戏核心专名（130+ 键名 +
   写回成功样本佐证），模型保留正确，但纯小写 6 字符非词典词与
   ram/ragdoll（测试固化须失败）在形态/结构上无可靠区分信号。
   豁免即误放行（test_common_word_leftovers 固化场景），需外部
   知识（术语表先例/词频表）才能判定的边界。保留原文安全。
2. **`ready`/`!suplex` 模型波动**：run2 回显失败 11 条 → run3 译出
   （准备就绪/！挤压）——1.8B 对无上下文短词输出不稳定，非代码问题。
3. **`Take off the` 原文碎片**：JSON 拆句键值（opt_wear_this3），
   原文本身无完整语义，模型回译英文——保留原文安全。
4. **rich-text 标签破坏被质量门正确拦截**：模型把 `<c=hl_effect>`
   改成 `<br>c=hl_effect>`（placeholder/rich_text mismatch）——
   质量门工作正常，无修复。
