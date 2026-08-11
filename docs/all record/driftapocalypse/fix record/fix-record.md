# driftapocalypse 修复记录

> 闭环轮次：run1 4 失败 → run2 3（F18）→ run3 0（F19）· 写回 156 PASS
>
> 本轮暴露**专名短语边界**（Play Games Plugin）与**缩写回显门不一致**
> （MAX vs proper_name_echo）两个判定边界，修复 F18/F19，全部系统性
> 通用规则，无单游戏特判。

## F18 专名短语中 UI 词典词豁免

**现象**：`*** [Play Games Plugin 0.10.12] ERROR: Failed to format
DateTime.Now` 译文 `[Play Games Plugin 0.10.12] 错误：无法格式化
DateTime.Now` 被判 target_script_mismatch。

**根因**：译文保留 `Play Games Plugin`（Google Play Games 插件专名）
和 `DateTime.Now`（.NET API 名）都正确，但 `Play` 在 UI 词典
（play→播放）且是英文短语 `Play Games Plugin` 的**首词**——短语分支
的 left_title/right_title 豁免要求词典词夹在 TitleCase 词**之间**
（i=0 时 left_title=False）→ Play 误判为漏翻动词残留。DateTime 本身
已被驼峰缩写豁免（非触发词），Play 是唯一误杀点。

**修复**（`batch_translator.py` 短语分支 + 单残留词循环对称）：
UI 词典词（TitleCase 形态）右侧连续 **≥2 个非词典 TitleCase 专名词**
→ 专名短语（'Play Games Plugin' 的 Play 是品牌词）→ 豁免。判定用
全局词序列（`_ENGLISH_PHRASE` 被标点断开的 `Plugin` 也能覆盖）。

**守卫**（不误放行真漏翻）：
- `Play Button`/`Play Store` 短组合（右侧仅 1 个专名词）→ 仍判失败
  （Play Store 实际由语义层 `_service_phrases` 剥除，天然豁免）
- 全词典词序列（`Play Settings Resume` 漏翻回显）→ 右侧专名词全在
  词典 → `any(非词典)` False → 仍判失败

**验证**：重跑 4 → 3（DateTime.Now 译出）；测试
`test_brand_ui_word_in_proper_phrase_allowed`（Play Games Plugin 豁免
+ Play Store 语义层豁免）+ `test_ui_word_short_proper_combo_still_fails`
（Play Button 漏翻/纯回显/全词典序列仍失败）。

## F19 全大写 ≤3 缩写回显豁免

**现象**：`MAX` ×3（data.unity3d level1 668/678 + DLL us#116）模型
回显 MAX，被判 untranslated_text 失败（重试耗尽仍回显）。

**根因**：MAX 是「Maximum」全大写 3 字母缩写，1.8B 模型对单 token
缩写**稳定回显**（count-my-coins 'SFX' 实证同类）。max 在 UI 词典
→ quality 的 untranslated_text 判失败；而 batch_translator 的
proper_name_echo 侧已有同形态豁免（1847 行 `len(word) <= 3 and
word.isupper()`，注释明确 SFX/BGM/UI 缩写是界面标准术语）——**两个
质量门规则不一致**，缩写回显在 target_script_mismatch 侧放行、
untranslated_text 侧拦截。

**修复**（`quality.py` untranslated_text 分支）：
`short_abbr_echo`——译文残留词全为 ≤3 全大写缩写且非动作指令 →
豁免（与 proper_name_echo 侧规则对齐）。守卫：
- `TOSS TRASH` 动作指令（special_action）→ 不豁免（knowledge 规则）
- `QUIT` 4+ 字母 UI 词典词、`MAX SPEED` 多词组合 → 不豁免
- `GAME OVER` 不在 UI 词典 → 走既有路径（无小写词+非词典 → 本来
  不判失败，行为不变）

**验证**：重跑 3 → 0（MAX 放行，回显跳过保留原文——缩写保留符合
界面惯例）；测试 `test_short_uppercase_abbreviation_echo_allowed`
（MAX/SFX/UI/OK 豁免 + QUIT/MAX SPEED/TOSS TRASH 仍失败）。

## 观察项（不修复，记录判断依据）

1. **`Grippier` 音译**：车辆属性文本 `Grippier, boosts back` 译文
   「格里皮尔，提升回程能力」——Grippier（更抓地）被 1.8B 当专名
   音译。模型翻译质量问题（形容词比较级误判专名），非判定系统问题；
   车辆属性描述轻度失真，不影响逻辑与可玩性。
2. **CREDITS 译文波动**：run1「致谢」→ run3「来源/署名」——模型
   对 CREDITS 一词翻译不稳定，两种译法均正确，无影响。
3. **eggs-for-bart 字体 runtime=WARN**：静态字体替换未命中（无内嵌
   字体对象）→ 走 BepInEx 运行时插件，font-health.json 需游戏实际
   运行才写入（工具不自动启动游戏，安全设计）→ payload_deployed
   （WARN 不阻断）。drift 静态替换命中 → runtime_verified（PASS）。
   属预期行为差异，非缺陷。
