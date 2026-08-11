# doog-hololive-fangame 修复记录

> 闭环轮次：run1（2026-08-11 19:04）1169/17 失败 → run2（2026-08-11）
> 1194/21 失败（F13 恢复 33 条哑跳过进池）· 写回 1109 PASS
>
> 本轮聚焦**失败分类判定 + 哑信号治理**——run1 17 条失败全部低影响
> （F9/F10/F11 防护生效，无逻辑功能损坏），其中 4 条触发 F12 修复；
> run1 跳过文本逐条判定发现 33 条 xml value 哑信号，触发 F13 修复。
> 全部为系统性修复，无单游戏特判。

## run1 失败分类总表

| # | 原文 | 译文 | 分类 | 处置 |
|---|---|---|---|---|
| 4, 12 | `Language: ENGLISH` | `I AM GOD HAND! WAO! 翻译成…` | 模型乱译（4 次重试稳定乱译 → newline/line_content mismatch 恒败） | **F12-A 已修复**：语言选项词典直填 |
| 14, 17 | `林まか (pixiv: 10768714)` | `林まか (Pixiv: 10768714)` | 作者署名+作品 ID 被模型改动大小写，损坏引用信息 | **F12-B 已修复**：识别层署名形态跳过 |
| 13 | `JAPONÉS` | `JAPONÉS`（回显） | 语言名回显惯例——游戏语言列表从不翻译语言名（业界惯例） | 豁免，无修复 |
| 5-11 | `ア↗ハ↘ハ↗ハ↘` / `ぴーらっぱっぱらっぽぅ` / `はろーぼ〜` / `あさココ（@ _ @）` / `ころね` / `ふっふっふっ` / `さいだい20もじ` | 全部回显 | 1.8B 对日语假名拟声词/名字/歌词的输出能力边界（拟声词不可译、ころね是 VTuber 名）；`さいだい20もじ`（最大20文字）是可译文本但回显失败——保留原文安全 | 能力边界合理失败，保留原文，无修复 |
| 1, 3 | `Sui-chan wa kyou mo kawaii!` | `Sui-chan今天真可爱！` | **译文质量好**（专名保留+语义完整翻译），但残留罗马字专名 `Sui-chan` 被判 target_script_mismatch | 质量门保守误杀，观察 |
| 2 | `el 100%` | `100%` | 西语冠词 `el` 被吞，核心信息 `100%` 保留 | 半翻可接受，观察 |
| 15 | `Doom transition effect based on code by David Walsh.` | `基于David Walsh编写的Doom过渡效果。` | **译文质量好**被链误杀（直调质量门 passed=True） | 质量门保守边界观察 |
| 16 | `The End` | `结束` | **译文质量好**被链误杀（同上） | 质量门保守边界观察 |

统计：F12 修复 4 条（2 形态 ×2 出现）、惯例豁免 1 条、能力边界
7 条、质量门保守误杀 5 条。写回 1102 条全部 PASS（94 扩容），无
回退（revert 0）——doog 对象以 TextAsset/xml 显示文本为主，无
输入绑定/UnityEvent 结构对象。

## F12-A 语言选项词典直填

**现象**：`Language: ENGLISH` 模型输出「I AM GOD HAND! WAO! 翻译成
我就是上帝的使者！哇哦！……」（把选项当例句逐条「翻译成」），
4 次重试稳定乱译 → newline/line_content mismatch 恒败。

**根因**：语言选项标签（`Language: <语言名>`）是**封闭集合**，
但对 1.8B 来说是无上下文短文本——模型把「Language: ENGLISH」当成
「翻译指令示例」幻觉展开，输出多行注释式文本。这类条目不该走 LLM。

**修复**（`knowledge.py::language_option_translation` +
`batch_translator._chat_each`）：
- `_LANGUAGE_OPTION_ZH` 直填表：英语→英语/西班牙语→西班牙语/
  日语→日语/俄语→俄语 等 40+ 常见语种（英文名 + 原语名两套拼写）
- `_LANGUAGE_LABEL_RE` 标签正则：`language|lang|languagemode|言語|
  言语|idioma|язык` 6 种写法 + 半角/全角冒号
- NFKD 去重音归一化（Español→espanol，先分解再丢组合记号——
  casefold 不吞组合符）
- 接入点：`_chat_each` 修复链最前（中文源放行后、模型调用前），
  命中即直填，不走 LLM
- 纯语言名（`ENGLISH`/`Español`）→ None 不动：语言选择器显示文本
  保留原名是业界惯例（`_is_language_name` 豁免已有）

**验证**：`Language: ENGLISH` → 「语言：英语」确定性直填；`言語：
日本語` → 「语言：日语」；`Idioma: Español` → 「语言：西班牙语」；
`Volume: High` → None（非语言标签不误伤）。

## F12-B 署名形态跳过

**现象**：`林まか (pixiv: 10768714)` 模型改成 `(Pixiv: …)`——署名是
**引用信息**（作者名 + 作品 ID），不是游戏内显示文本，改动大小写即
损坏引用。

**根因**：识别层没有署名形态 → 当普通显示文本放行 → 模型「翻译」
（实际只是改了大小写）→ 半翻失败。

**修复**（`extractor.py`）：
- `_SIGNATURE_CREDIT_RE`：pixiv/twitter/facebook/instagram/artstation/
  deviantart/newgrounds/sketchfab/youtube/furaffinity/booth/fantia
  12 平台名 + `[:：]?` + ID（`@?[\w.-]{2,}`）
- `_structural_reason` 返回 `signature_credit` → 识别层跳过
- 正文谈平台（`Follow us on twitter!`）无冒号+ID 结构 → 不命中，
  照常翻译

**验证**：`林まか (pixiv: 10768714)`/`Kenney (twitter: kenneyNL)`/
`Twitter: @dev` → skipped；`Follow us on twitter!` → 正常文本。

## 观察项（不修复，记录判断依据）

1. **质量门 target_script_mismatch 对罗马字专名过度敏感**：[1][3]
   `Sui-chan今天真可爱！` 译文完整（专名保留是正确翻译策略），
   残留罗马字 `Sui-chan` 触发 script mismatch。若后续游戏批量出现
   「译文含中文+罗马字专名」失败，考虑 script 判定对专名罗马字豁免
   （参照已有拼写变体豁免思路）。
2. **质量门对「质量好译文」误杀**：[15][16] 直调质量门 passed=True
   但整链判失败——失败记录与质量门直调矛盾（推测修复链某步覆盖
   quality_reasons）。下一游戏对观察是否复现，复现则查修复链状态
   覆盖路径。
3. **`el 100%` 冠词吞删**：西语冠词属可接受省略（核心信息 100%
   保留），不修。

## F13 结构化格式 value 节点豁免软猜测降级（run1 分析期发现）

**哑信号**：跳过文本逐条判定发现 39 条 xml `messages/message[N]/value`
位置（显示文本）被后置降级闸门误杀 33 条（+6 条单字符/纯符号合理跳）：

| 误杀规则 | 样本 | 真相 |
|---|---|---|
| key_style 混合大小写 | FeeNGAh/PaNChee/RoCKTSu 等 | hololive 罗马音歌词 |
| 引擎串 PascalCase 形态 | FeeNGAh（`^[A-Z][a-z]+[A-Z]...`） | 同上 |
| `_QUALIFIED` 连字符标识符形态 | Konbanmio-n/Haro-bo | 罗马音台词 |
| credit_like 句子署名 | Get revived by Hololive's resident necromancer | 英文成就句 |
| log_template 冒号结尾 | Seleccione dificultad: | 西语 UI「选择难度」 |

**根因**：后置降级闸门是「无结构上下文」的形态猜测规则，对 raw scan
有意义；但格式解析器（xml_format）已按**结构**判定文本节点（key/value
位置、_ID_LIKE 键名过滤），其输出即显示文本证据——软猜测规则不得
推翻格式判定（证据分层，同 typetree_display_field 的 credit 豁免）。

**修复**（`extractor.py`/`engine_strings.py`）：
- `_should_downgrade_pending` 格式化分支：`textasset_format=xml` 且
  inner_path 含 `/value` → 只做确定性硬结构降级（URL/GUID/JSON/数字/
  输入设备/绑定路径/base64/路径/`is_engine_string_core` 已知词表）+
  无语言内容短串；key_style/PascalCase/credit_like/log_template/
  _QUALIFIED 全部豁免
- `engine_strings.is_engine_string_core`：拆出形态标记明确的确定性
  分支；`is_engine_string` = core + 编程命名形态猜测（raw scan 无结构
  上下文仍用全判定）
- xml **key 位置不豁免**：PICKUP_BACKPACK 全大写键名仍 key_style 跳过
  （键名翻译即断键，边界对照测试）

**验证**：run2 重跑——value 936 pending（+33 恢复）/6 skipped（单字符
纯符号合理）；key 945 全跳过不变；测试 1580 通过（+2）。

## run2 结果（F12/F13 验证）

- **F12-A 生效**：Language: ENGLISH ×2 不再进失败清单（确定性直填）✓
- **F12-B 生效**：署名 ×2 识别层跳过 ✓
- **F13 生效**：33 条 value 恢复进池——其中 8 条日语假名内容（こん
  かぷ〜/パンチ/ぶき 等）模型回显/误译失败（1.8B 能力边界，保留原文
  安全，有记录可见非哑跳过）；罗马音台词（FeeNGAh 等）回显跳过 85 条
  记录内 ✓
- 21 条失败 = 17 − 4（F12）+ 8（F13 恢复进池后失败），全部低影响合理
- 写回逻辑层审计段（F11）真实输出验证：知识库 5 条规则启用 ✓ ·
  report 15 条（全真按钮文本，复核通过，占比 1.4% 无召回率告警）✓ ·
  revert 0（doog 无代码对象/UnityEvent，零命中预期）✓

## 下一游戏对验证点

- 语言选项条目不再进失败清单（`deterministic_fill=language_option`）
- 署名形态无显示文本误杀（正文「Follow us on twitter!」可翻）
- F11 逻辑键回退段非空或确认零命中（需含代码对象/UnityEvent 结构的
  游戏验证 revert 真实路径——doog 零命中属预期）
