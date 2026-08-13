# font_games：方框字反馈环最小 fixture 清单

Phase 0（审计 §9）：在不依赖某个商业游戏手工点击的情况下，稳定复现并
区分**字体缺字 / 编码损坏 / 图集缺失 / 未覆盖消费者**四种症状。
fixtures 是结构化合成数据（消费者—字体—图集引用链），并记录到真实
Unity 资产的映射——不携带二进制资产，纯数据可复现、可审计。

## 必须覆盖的最小样本（10 项）→ fixture 映射

| # | 样本（审计原文） | fixture | 症状/终态 |
|---|---|---|---|
| 1 | 两个 TMP 字体：一个可替换、一个 dynamic 0 glyph；旧逻辑会假 PASS | `tmp_replaceable` + `tmp_dynamic_zero_glyph` | 旧全局 PASS → 新 CANDIDATE_ONLY |
| 2 | 静态 TMP 缺译文生僻字；字形总数很大但覆盖失败 | `tmp_big_table_missing_rare` | MISSING_CODEPOINT（缺字回溯到 locator） |
| 3 | TMP 字体与 atlas 跨文件引用 | `tmp_cross_file_atlas`（atlas_ref 指向外部 .resS） | ATLAS_REFERENCE_UNRESOLVED |
| 4 | Legacy Font + TextMesh | `legacy_textmesh`（legacy TTF 替换命中） | COVERED |
| 5 | Mono 动态 TMP：插件启动前 pending、启动后 attested | `mono_dynamic_pending` / `mono_dynamic_attested` | PENDING_RUNTIME_ATTESTATION → COVERED |
| 6 | IL2CPP 动态 TMP，无 runtime provider | `il2cpp_dynamic` | BLOCKED（RUNTIME_PROVIDER_UNAVAILABLE） |
| 7 | NGUI / BMFont 证据 → unsupported/专用 provider | `ngui_bitmap` | CANDIDATE_ONLY（UNSUPPORTED_RENDERER） |
| 8 | 文本字节本身是 □□□□ → data corruption | `corrupted_data`（U+25A1 已写入） | DATA_CORRUPTION（不归因字体） |
| 9 | 非 BMP 字符：需求集不能拆成两个 surrogate | `non_bmp_text`（😀 = 0x1F600） | 单 scalar；surrogate 半码点不算覆盖 |
| 10 | `<sprite>`/图标字体不得当 CJK 替换目标 | `sprite_icon` | NOT_A_CJK_TARGET（不阻断） |

## 生成说明

- `fixtures.py` 提供合成构建器（`make_consumer(...)`、`make_entries(...)`），
  全部为纯数据，无 Unity 二进制依赖；测试直接导入。
- 真实资产对应关系：
  - TMP 静态字体 → `fonts/TMP_Font_AssetBundles_2025-12-08/<bundle>`
    （u55to2017/u2018/u2019/u2021/u2022/u6000，manifest.json 校验）；
  - 动态 0 glyph → TMP_FontAsset 的 `m_GlyphTable` 为空且 `m_AtlasTexture`
    stream 不可用（动态字体运行时按 TTF 生成字形）；
  - 跨文件 atlas → atlas 的 `m_StreamData.path` 指向同 bundle 外部
    `.resS`（`_atlas_stream_meta` 解析路径）；
  - NGUI/BMFont → fingerprint 层的 `mFont`/`mBMFont` 证据；
  - 数据损坏 → 写回文件内直接含 U+25A1/U+25AF/U+FFFD。
- 用法：测试按表取 fixture，先跑 `compute_coverage`/`diagnose_render`
  断言终态，再对照 README 的行确认与真实游戏症状一致。
