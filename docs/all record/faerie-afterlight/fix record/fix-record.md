# faerie-afterlight 修复记录（F21 + F22）

## F22-1 引擎控制码串识别跳过

**触发**：faerie 第 1 轮 340 条失败中 186 条含 `^`，其中 178 条是引擎
控制码串 `'.^.b'` 纯回显——模型把引擎样式/命令标记当文本翻译成乱码，
或回显后被判 target_script_mismatch。样本：
`来源：sharedassets12.assets` 原文 `'.^.b'` 译文同形回显。

**形态特征**：`^` + 非字母数字 ≤2 + 字母段 1-12（`^b`/`^tr`/`^denvis`）。
剥除全部控制码后无 ≥3 字母 ASCII 词 → 该串无真实文本内容。

**防误伤**：`x^2 + y^2`（数学幂）剥后仍有单字母碎片 + 数字，不误伤
（测试反例固化）。

**实现**：`hanhua/core/placeholders.py` `_ENGINE_CTRL_CODE` +
`_ENGLISH_WORD_MIN3`，`is_hard_structural` 的 `_KEYBOARD_NOISE` 分支后。
**接入点**：识别层（结构跳过，不进入翻译池）。

**判定依据**：与既有 `_KEYBOARD_NOISE`/混合符号 token 同类——无语言
内容的结构串不进翻译池（全大写熵串/日志模板同源规则）。

**实证**：第 2 轮（12:41 写回）——第 1 轮失败 340 条中 187 条
skipped（识别层跳过不进池不进导出），其中 178 条引擎控制码串
（`'.^.b'` 类）；写回 PASS 后发布目录 level1-15 无控制码乱码写入。

## F22-2 键位绑定后缀豁免

**触发**：faerie 10 条失败——`Press {0} to open Map of ...</color>.:map`
译文 `点击 {0} 可以打开...的地图。:map` 完整正确，仅因 `map` 在 UI
词典被当英文残留。

**形态特征**：原文 `:xxx` 后缀（`:([a-z]{2,})`），键位绑定显示标记
（`.:map`/`.:interact`/`.:jump`）。

**防过宽**：译文新增原文没有的 `:newkey`（模型幻觉）→ 不豁免。

**实现**：`batch_translator.py` `_has_disallowed_chinese_target_letters`
中 `keybind_suffix_words` 从原文提取，两个残留词循环（短语循环 +
单词循环）豁免。**接入点**：质量门判定层。

**实证**：第 2 轮——340 条中 35 条转 translated（F22-2/3/4 豁免
合集，补翻 36 成功中 35 条是第 1 轮失败条目）；键位后缀类
（`Press {0} to open Map...:map`）译文保留后缀写回，实机测试
按键交互正常（菜单导航/移动/跳跃/暂停全部响应）。

## F22-3 TitleCase 短语段 / 多语言段保留豁免

**触发**：faerie 78 条 zh_partial + 12 kana + 6 accent——模型保留专名/
外语段只译其余，被当英文残留：
- `Before Pish Shop\tBefore Pish Shop` → `Pish Shop之前`（商店专名）
- `Wispy's Chat (Auto Dialogue)` → `Wispy's Chat (自动对话)`（频道专名）
- `Solium dual\tPolar-Solium` → `Solium dual：双极型电池`（物品专名）
- `Vallon noir III : ...` → `Vallon noir III：…`（法语物品名）
- `Perhaps the voice really is coming from Lucentia.,Wispy: Mungkin
  suara itu sungguh datang dari Lucentia.,Wispy: Tal vez` → 英语段译出、
  印尼语/西语段保留（多语言打包对话）

**形态特征**：
1. 段首 TitleCase 词（≥3 字符、首大写、非功能/动作/UI 词典/术语词）
2. 后续词 gap≤3 字符延续（容 `'s` 属格、冒号/标点），段长≥2 且含非
   功能词 → 全段豁免
3. **外语间隙放宽**：译文含非 ASCII 字母（且非中文表意字）→ gap≤7
   （`¿Acaso se me cayó por` 中 `se me` 两个 2 字母西语功能词被
   `_ENGLISH_WORD` ≥3 过滤 → 间隙 7 > 3 断开 → cayo/por 漏豁免；
   外语文本特征触发放宽）

**防过宽**（对照测试固化，真半翻译必须仍失败）：
- `I like 吃披萨`——I 单字符段首不成立
- `Press 按钮以继续`——Press 交互动作词
- `Slash key`→`Slash 键`——slash 术语表命中优先
- `Adjust spring pressure 调整 spring 压力`——**Adjust/Change 命令
  动词**：`_ACTION_VERB_ZH` 操作动词词表类目完整化 +40 词
  （adjust/change/set/select/toggle/enable/disable/move/delete/add/
  update/edit/apply/import/export…），命令句动词不成立段首
- `The Fidelity`——The 功能词段首不成立

**实现**：`batch_translator.py` `_phrase_seg` 段构建 + `title_phrase_words`
豁免集（两循环接入），`_foreign_gap` 外语间隙放宽；knowledge.py
`_ACTION_VERB_ZH` 词表扩展。**接入点**：质量门判定层。

**实证**：第 2 轮——专名/多语言段（Pish Shop/Wispy's Chat/Vallon
noir III/Mungkin 印尼语段）保留原文写回；法语对话
`Hé, c'est encore vous !` 类 9 条按原文翻译（encore=又/再）不再被
glossary 安可词条误杀。

## F22-4 glossary 词义双关豁免

**触发**：faerie 10 条 glossary_mismatch：
- 9 条法语对话 `Hé, c'est encore vous !`——encore=又/再（日常副词），
  术语表 (encore, 安可) 是演出借词含义
- 1 条 `Hani: I... I miss my father so much.`——miss=想念（动词），
  术语表 (miss, 未命中) 是音游 HUD 判定标签（deadbeat 沉淀）

**形态特征**：
1. 法语特征：重音字母（àâäéèêëîïôöùûüçñÿœ）或法语功能词
   （c'est/qu'est/les/des/une/un/vous/nous/je/tu/ma/mes/ses/est/sont/
   il/elle/chez/avec/pour/dans/sur）→ 英语术语表不适用
2. 动词双关：术语词前邻主语代词（I/you/he/she/we/they/it/me/him/her/
   us/them）或 be 动词（am/is/are/was/were/be/been）→ 动词用法

**防过宽**：
- 英语原文 `Encore! Encore!`（音乐会）无法语特征 → 术语照常生效
- `miss: 999` 前邻冒号 → 不豁免
- 前邻正则词边界 `(?<![A-Za-z])`：`the` 的 `he` 不得匹配（Slash key
  回归案例）

**实现**：`quality.py` `_french_marker()` + `_glossary_verb_usage`
前邻正则扩展（+词边界）。**接入点**：质量门 glossary 检查层。

**实证**：第 2 轮——340 条失败逐条比对：glossary 双关类（法语
encore×9 + miss 想念×1）全部从失败清单移除（转 translated 或
不再误杀）；`I miss my father` 译文「我想念我的父亲」正确写回。

## 附带修复

### reviewer 批量审核配置（基础设施，ffs 实证）

deepseek-v4-flash 是 reasoning 模型：thinking 块吃光 8192 max_tokens
→ text 块为空 → JSON 缺失 → 整批丢弃（ffs 6224 条实证 reviewed 0）。
改 `_REVIEW_BATCH_SIZE 120→60` + `max_tokens 8192→32768`，实测
60 条/批 end_turn 完整返回（~7KB JSON/批、~45s/批）。

### runner 启动预检语言分布（多语言游戏盲区）

faerie 实证：法语/日语/印尼语条目混在英文池。扫描后统计原文语言
特征（假名/中文/西里尔/重音拉丁/ASCII）写入 summary「语言分布」，
分析者第一眼识别多语言游戏。抽样统计 faerie：英文 19826、日语 1765、
中文 1661、重音拉丁 1415。

## 附带修复 2：审核词对提取正则崩溃（2026-08-12 根因修复）

**触发**：ffs 语义审核 724 条 flag 完成（review.json 6101 条已写盘），
在 `extract_term_pairs` 沉淀词对时崩溃——`re.sub(r"[\"'「『\【【（( ]*[\"']?|[\"']?」』\】】）) ]*", ...)`
中 `|` 后的 `」』】】）)` 全部落在**字符类之外**，裸 `)` 未配对 →
`re.error: unbalanced parenthesis at position 32`。

**危害等级**：`_run_semantic_review` 的最后一步（审核报告写在词对提取
**之后**）——崩溃 → 整个审核函数异常 → runner 捕获后 review_results
置空 → **整场审核结果丢失**（回显过滤掉不算，审核批全部白跑）。

**为什么今天才暴露**：该 bug 自 reviewer.py 引入即存在（形态 2 词对
提取路径）。此前无 500+ flag 规模的数据触发（faerie 第 1 轮审核
reviewed 0——max_tokens 截断 JSON 缺失，flagged 0 → 词对循环空；
ffs 第 1 轮同样 reviewed 0）。ffs 第 2 轮 724 flag 才首次走到
`re.sub` 且有纯中文 suggestion。

**修复**：`|` 后装饰字符类补全 `[」』】）) ]`（同时去掉多余 `\【`
转义）+ 外层 try/except 防御（词对是附带产出，绝不允许拖垮审核
主流程——提取失败返回 [] 继续写报告）。

**验证**：修复后从 ffs review.json 提取 42 条词对成功（Trigger→扳机、
Hat→苦力帽、Stick→摇杆、Safe→保险/开火、Pinkie→小指按钮——方向盘
输入术语的首次沉淀）。

## 附带修复 3：--resume 写回缺清单 + 写回失败删库事故（2026-08-12）

**触发链**（faerie resume 全链路实证暴露两处缺陷）：

1. **写回被拒**：`--resume` 跳过扫描后 `write_all` 输入闸门
   `_last_source_manifest is None` → 「缺少成功扫描绑定的完整输入
   清单」——扫描绑定清单只在内存，续跑进程里没有。
2. **译文数据事故**：写回失败后 runner 仍执行
   `if not keep_library: _discard_sweep_library(project)` 无条件
   删库——faerie 库连同 18698 条译文被删；紧接着的空导出把
   text/translated.txt 覆盖为 0 条。

**恢复**：译文数据从 git HEAD（第 1 轮 03:38 导出 18698 条）恢复
——git checkout 导出文件 → scan_all 重建库（upsert 保留译文，
新代码识别更全 +154 条）→ 按 file_id+key_path 匹配导入 18683 条
（15 条未匹配均为输入设备串，新代码已识别跳过）→ 补翻 154 →
写回 PASS。

**修复（系统性）**：
1. 三个扫描绑定清单（source_manifest / il2cpp_input_hashes /
   text_scan_manifest）随 scan_all/scan/scan_v2 成功写入库 profile
   表（memory.py 通用 get/set/del_profile_value + 表缺失容错），
   Project.__init__ 从库恢复；校验不失效——恢复旧清单 vs 实际树
   hash 比对，输入被改动仍拒绝写回（IL2CPP 规范输入证据同理）。
2. runner 删库改条件：`if not keep_library and not writeback_error`
   ——写回失败保留库（与「写回失败不删 _汉化」同一原则，955 行）。

**防再犯**：库是 resume 续跑唯一凭据（译文 + 扫描清单都在库里），
删库 = 译文数据丢失风险；写回成功才删（keep_library=False 默认
语义不变）。已删库游戏恢复路径：tmp_restore_faerie.py（扫描重建
+ 导出导入）。

## 观察项（模型边界，不修复）

1. `Jump High`/`Jump Low` 回显——模型对孤立机制词回显
2. 印尼语人名串（denvis/prabubejoslamet）被当英文译乱
3. `Ailes de phalène\tMottenflügel` 法+德打包 → 韩文乱译
4. `d;߽` 二进制噪声
5. `The Fidelity` 专名回显（重试链路径）
6. clutch 方向盘轴名回显失败——**失败=系统自动保留原文**（输入映射
   不被破坏），若模型译出「离合器」则写回有映射风险 → 实机测试验证
   方向盘输入按名匹配还是索引匹配，若按名匹配则需识别层跳过轴名词表
