# fix-10 多语言源文本全链路（检测 → 双跳 → 同对象译例 → 重音归一化）

游戏：alisa-demo（闭环于 2026-08-10，818/818 干净闭环）

## 背景

alisa-demo 是**四语言打包游戏**：同一对象（obj）存英/法/意/日四版同一文本。
模型 Hy-MT2 是英中翻译模型，对日语/意语/法语源文本倾向输出**英语译文**
（准确但目标语错误），质量门 target_script_mismatch 正确拒绝但普通重试
仍然失败。初跑 31 条失败 → 多轮修复 → 最后 1 条（[6] 法语便条 Pulsomètre）
在重音专名碎片误判上卡死。

## 修复（全部通用机制，无单游戏特判）

| # | 内容 | 文件 |
|---|---|---|
| 1 | **多语言源检测 `_is_multilingual_source`**：日文假名 `[぀-ヿㇰ-ㇿ]` / 重音拉丁 `[À-ÖØ-Þßà-öø-ÿ]` / ASCII 罗曼功能词（il/lo/la/di/da/de/ne/ve/ci/vi/che…）三路识别；知识库 BUILTIN_RULES 加 `text/multilingual_source` 种子规则，learn 沉淀回显条目 | `knowledge.py` |
| 2 | **双跳翻译**：多语言源失败 + 译文无中文 + 含英语词 → 以英语译文为中间源再译中文（模型英译中强项）。失败不截断，继续降级链 | `batch_translator.py` |
| 3 | **同对象译例**：`self._obj_results` 桶（asset_file+obj 键）记录同 obj 兄弟条目成功译文 → 失败条目重试注入 `"Reference translations from the same item"` chat prompt → 模型复用（Clé en Fer → 铁钥匙） | `batch_translator.py` |
| 4 | **引文豁免 quote_words**：原文引号内引文（铭文/题词 "To the house of ..."）译文保留原文不算英文残留（要求已含中文） | `batch_translator.py` |
| 5 | **段内双跳**：multiline 逐段修复时段输出英语 → 段内第二跳英译中；罗曼功能词表补 ne/ve/ci/vi（意语长句漏行根因） | `batch_translator.py` |
| 6 | **proper_name_echo 多语言源限制**：多语言源 + 同 obj 有成功译文 → 不得豁免回显（Clé Pomme 漏网之鱼）；孤立专名（Stefánsson/Korone 人名）仍豁免（不误伤历史专名测试） | `batch_translator.py` |
| 7 | **multiline 修复失败不截断**：`if repaired is not None: return` → `and repaired[2]`，失败继续降级链（双跳/同 obj 译例/普通重试） | `batch_translator.py` |
| 8 | **重音归一化 `_ACCENT_TO_ASCII`**：`_ENGLISH_WORD` 纯 ASCII 正则把 "Pulsomètre" 拆成 "Pulsom"+"tre" 碎片，"tre" 是小写普通词 → 误判英文残留。语义英文词提取前做重音拉丁→ASCII 一对一词符映射（长度不变，索引对齐保持）；非 ASCII 字母检查仍用原串（假名/西里尔残留照常拒绝） | `batch_translator.py` |
| 9 | **同对象译例竞态修复**：record 从 run() 主线程的 `consume_native_result` 回调移到 `_chat_each.work` 内（worker 返回前）——worker 完成当前条目后立即取下一个 work，record 与兄弟条目译例读取形成竞态（同批 Clé en Fer 偶发读不到 Iron Key 译例 → 回显失败；-s 输出捕获的 IO 延迟掩盖了该竞态）；单 worker 下先 record 后读取，多 worker 由 `_obj_lock` 保证一致读 | `batch_translator.py` |

## 关键实证链

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 日语 26 条（釣り竿 等） | 输出准确英语（Right-hand key）被拒 | 双跳 → 右手钥匙 |
| 法语 Clé en Fer | 回显（模型不认识） | 同 obj 译例注入 → 铁钥匙 |
| 英文截断 "Excuse me, I -" | 回显 | 同 obj 对话流兄弟译文 → 打扰一下，我—— |
| 三语言版引文 [9][10][11] | 保留引文被误判残留 | quote_words 豁免 → 保留 "To the house of ..." |
| 意语长句 [1]（Ve ne preghiamo） | 段 5 漏行英语回显 | 补 ne/ve/ci/vi 词表 + 段内双跳 → 闭环 |
| 法语 TitleCase 物品名 Clé Pomme/Chapeau Cône Vert | proper_name_echo 豁免漏翻 | 多语言源限制 → 苹果钥匙/绿色圆锥帽 |
| [6] 法语便条 Pulsomètre | 重音专名拆碎片 "tre" 误判残留 | 重音归一化 → 脉搏计/借用的设备完整中文 |
| 同 obj 译例（回归） | 竞态偶发读不到兄弟译例 | worker 内 record → 稳定命中 |

## 验证

- alisa-demo 最终跑：**818 条翻译 0 失败，全部写回**（初跑 31 失败 → 817/1 → 818/0）
- 多语言源全部干净：法语/意语/日语条目全部产出中文（抽检 25+ 条全部正确）
- 知识库沉淀：multilingual_source 形态 3 条法语回显（Clé Pomme/Chapeau Cône Vert/Clé Arbre）
- 全量测试 **1454 通过 + 27 skipped，0 失败**（新增 TestMultilingualSource + 重音归一化 + 竞态回归）
- D:/游戏/alisa-demo `_汉化` 目录与备份已删（做完一个删一个）

## 遗留（模型能力边界）

- 无失败条目。个别多义词（如有）人工校对可见（记录文件可筛选），
  1.8B 模型流畅误译质量门无法拦。
