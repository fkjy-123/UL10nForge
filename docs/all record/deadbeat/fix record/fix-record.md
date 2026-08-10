# deadbeat 修复记录

> 闭环轮次：run7（2026-08-11 17:15）· 0 失败达成
>
> 本轮修复聚焦**超长歌词翻译链路**（1.8B 模型的能力边界与配置不匹配），
> 全部为系统性修复，无单游戏特判。

## F0 歌词单次输出上限 → translate_lyrics 分块

**现象**：`Modern-day killers` 3183 字符歌词译文只有 703 字符——
max_tokens 放大后模型 ~430 tokens 主动 EOS（1.8B 对超长歌词的固有
输出上限），输出为「摘要式」：开头 + 结尾，中间 2/3 丢失。

**根因**：单次请求中模型只能稳定输出 ~700 字符译文，之后自行结束。

**修复**（`translator.py::translate_lyrics`）：超长歌词（> 700 字符）
按 `_chunk_source` 分块（无换行按词切 ≤700 字符块），逐块走
`_translate_lyrics_single`（中文引导 + repeat_penalty 1.35），块间按
切分单位（空格）拼接。每块 ≤700 字符 → 模型对每块输出完整译文。

**验证**：3 条 3183 字符歌词分块后输出 1316-1356 字符完整译文，
质量门全过（reasons 空），末尾无衰减回显。

## F1 max_tokens 缩放错误（英语假设）

**现象**：译文 1200 字符后截断并回显原文英文。

**根因**：`min(config.max_tokens, len(source_text) // 3 + 32)` ——
`len//3+32` 按英语假设（3 字符/token）；中文译文 1 字符 ≈ 1.2 token，
3183 字符歌词只给 1093 tokens 预算，~850 tokens 后预算耗尽，模型
续写原文填充，被判 target_script_mismatch。

**修复**（`translator.py`）：缩放改为 `len(source_text) + 128`
（1 字符 ≈ 1 token + 余量），上限仍受 `config.max_tokens`（4096）约束。

## F2 本地模型 ctx 4096 装不下完整输出

**现象**：prompt（3183 字符 ≈ 1100 tokens）+ 完整译文（~3100 tokens）
= 4200 > 4096。

**修复**：`local_context_size` 默认值与持久化设置 4096 → **6144**
（用户指示）。llama-server 重启生效（签名含 ctx，ensure_running
自动检测重启）。实测 prompt + 完整译文 4411 < 6144 ✓。

## F3 歌词译文分行被判 newline_mismatch

**现象**：引擎单行存储超长歌词（原文无 \n），模型按句分行输出译文
（歌词节奏的自然渲染）→ newline_mismatch + line_content_mismatch
拒绝完整中文译文。

**修复**（`quality.py::validate_translation_quality`）：`_is_lyric_like`
（len≥200 + 假名/汉字/括号音乐标记）判定的歌词豁免 newline /
line_content 检查——分行是歌词的自然渲染，非结构破坏。非歌词文本
（原文单行译文多行）仍判失败。

## 本轮知识库沉淀

- 歌词输出上限案例（F0）：1.8B 单次输出 ~700 字符上限 → 分块
- max_tokens 缩放案例（F1）：中文 1 字符 ≈ 1.2 token 预算法则

## 关联待办（不属于本轮修复）

- **222am 待办 A**（shower 等 20 条音效/场景标签跳过）：根因已定位为
  `DISPLAY_WORDS` 白名单盲区（165 词固定表，shower/city/bedroom 等
  常见场景词不在表内 → 被 `is_key_style_identifier` 判为键风格标识符
  跳过）。系统性修复方案：常见英语词典判定或数据驱动扩充白名单，
  登记治理，不特判。
