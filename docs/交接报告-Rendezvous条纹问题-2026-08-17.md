# Rendezvous NotoSerif 条纹问题——交接报告

> 生成时间：2026-08-17
> 交接对象：接手攻克"汉字水平条纹/碎片化"渲染问题的 agent
> 工具项目：`C:\Users\mingming\Desktop\AI项目\unity游戏汉化工具`
> 游戏：`C:\Users\mingming\Desktop\Rendezvous.rar_汉化_汉化`（用户实机测试目录）
> 原版备份：`Rendezvous_Data\sharedassets0.assets.pre-sdf.bak`（19:31 原始汉化版）

---

## 0. 一句话现状

**游戏可启动（无 corrupted）、文字数量/行数/位置正确，但每个汉字渲染为大量水平细密条纹（笔画碎片化、断裂、重影、错位）。当前部署 = 完整工具字体（NotoSerifCJKsc-Medium，8361 字形）状态，条纹现象可复现。**

---

## 1. 已确认的根因（缺字问题）

1. **场景 TMP 组件（TextMeshProUGUI，m_Script=(1,2000)）的 m_fontAsset 引用 Coda（2417）/arial（2410）等拉丁 SDF 字体**（sharedassets0.assets 内 pathID 2408-2419 共 7 个 TMP_FontAsset）→ 无中文字形 → 口口口
2. **游戏自带 NotoSansSC-Regular SDF（pathID 2409，385 字形简体中文，官方中文用的）**——组件引用改到 2409 后官方中文正常显示
3. **译文需求集 1316 码点 > 385 字形** → 需要完整中文字体（8361 字形）

## 2. 当前部署状态（NotoSerif 条纹状态）

```
sharedassets0.assets：
  pathID 2409 = TMP_FontAsset "NotoSerifCJKsc-Medium SDF"（8361 glyph / 8361 char / 7877 CJK）
    数据 = 手工组装（主文件格式，NotoSC 骨架 + NotoSerif 数据，687152B）
    FaceInfo: pointSize=33, scale=1.0, lineHeight=47.42, padding=6, renderMode=4165, atlas=4096²
    m_AtlasTextures[0] = (0, 3002)
  pathID 3002 = Texture2D "NotoSerifCJKsc-Medium SDF Atlas"（4096×4096 Alpha8，主文件格式，16777336B）
    数据 = 备份 753 头部（104B，len@104）+ .asset 像素（16777216B）+ 尾部 12B
  pathID 211 = Material（NotoSC 材质改造：_MainTex=(0,3002)、_TextureWidth/Height=4096、_GradientScale=7）
  pathID 753 = NotoSC 原版 atlas（已恢复备份）
level0-48：所有 TMP 组件引用 → (2,2409)（字体）/ (2,211)（材质）
```

## 3. 条纹问题排查记录（全部已验证正确的环节）

| 环节 | 状态 | 验证方式 |
|---|---|---|
| 字体数据 glyph 表（8361，rect/metrics） | ✅ 正确 | '中' rect=(4061,685,28,31)、'你' rect=(825,367,35,31)，metrics advance=33=1em |
| Atlas 像素（3002） | ✅ 正确 | 与 .asset `_typelessdata` 完全一致；'中'/'你' 区域字形完整 |
| 纹理数据布局（主文件格式） | ✅ 正确 | 头部 104B（name/ff/ds/w/h/cis/fmt/mips/len@104），UnityPy 重读 typetree OK |
| 材质（211） | ✅ 正确 | shader=(0,758) TextMeshPro/Distance Field、_MainTex=(0,3002)、尺寸 4096、GradientScale=7 |
| 组件引用（level） | ✅ 正确 | m_fontAsset=(2,2409)、m_fontSharedMaterial=(2,211) |
| m_AtlasWidth/Height | ✅ 4096 | 数据内搜索确认 |
| 引擎兼容（不 corrupted） | ✅ | 游戏启动正常 |

**结论：所有可验证的数据层正确，但渲染仍条纹 → 指向 mono 反序列化字段错位**（游戏 TMP 2.1.1 的 C# 字段布局与组装数据存在未发现的差异，某个字段被读错 → UV/采样参数错误）。

次修改无冲突
