# Rendezvous 条纹问题——已解决（根因记录）

> 2026-08-18 攻克。条纹根因 + 修复方法，供后续同类问题参考。

## 根因

手工组装 TMP_FontAsset 数据（主文件 2019.4 格式）时，**m_fontInfo 段少了 4 字节**：

- NotoSC 原版（渲染正常）：m_fontInfo 段 = `len 字段(4B) + 23 floats(92B)` = 96B
- 组装数据（渲染条纹）：复制时从 @36360 开始（只复制了 92B floats），**漏了开头的 4 字节 len 字段**

后果：mono 反序列化 TMP_FontAsset 时，m_fontInfo 之后的所有字段（m_AtlasWidth/m_AtlasHeight/m_AtlasPadding/m_AtlasRenderMode/tail）**全部偏移 4 字节** → 引擎读到错误的 atlas 尺寸 → UV 计算错乱 → 每个字形采样错误区域 → **水平细密条纹（笔画碎片化、断裂、重影）**。

## 修复

组装时 m_fontInfo 段用**完整 96B**（`tmpl[36356:36452]`，含 len 字段），而不是 92B（`tmpl[36360:36452]`）。

验证方法：组装后步进解析，断言 `floats_bytes == 92`（23 floats，与 NotoSC 一致）。

## 完整正确的主文件格式 TMP_FontAsset 组装骨架

```
m_GameObject(12) m_Enabled(4) m_Script(12) m_Name(str)
hashCode(4) material(12) matHashCode(4) m_Version(str) m_SourceFontFileGUID(str) m_SourceFontFile(12)
m_AtlasPopulationMode(4) m_AtlasTextureIndex(4)
m_FaceInfo: family(str) style(str) + 17 数值(68B: int pointSize + 16 floats)
m_GlyphTable(count + N×48B)     # idx(4)+metrics(20)+rect(16)+scale(4)+atlasIdx(4)
m_CharacterTable(count + N×16B) # elementType(4)+unicode(4)+glyphIdx(4)+scale(4)
m_AtlasTextures(count + N×12B)  # PPtr fileID(4)+pathID(8)
m_AtlasTextureIndex(4)
m_UsedGlyphRects(count + N×16B)
m_FreeGlyphRects(count + N×16B)
m_fontInfo: len(4) + 23 floats(92B)   # ← 关键：必须 96B 含 len 字段
m_AtlasWidth(4) m_AtlasHeight(4) m_AtlasPadding(4) m_AtlasRenderMode(4) m_AtlasPopulationMode?(4)
[tail: m_glyphInfoList/m_KerningTable/m_FontFeatureTable/m_FallbackFontAssetTable/m_CreationSettings/m_FontWeightTable...]
```

## 其他已验证的关键点（本次会话）

1. **跨格式移植（bundle 2019.1 → 主文件 2019.4）的已知差异**：
   - m_AtlasTextureIndex 位置：bundle 在 m_AtlasTextures 数组后；主文件在 m_AtlasPopulationMode 后**且**数组后也有
   - 纹理数据布局：save_typetree 输出与主文件差 8-9 字节（image data len 字段位置：主文件 @104）
   - 主文件纹理格式：头部 104B（name/ff/ds/w/h/cis/fmt/mips/.../len@104）+ 像素 + 尾部 12B
2. **主文件 Font 替换**（sharedassets0 15 个 Font + resources.assets Font#40 + 内置 Arial）→ 工具 TrueType（16.5MB SourceHanSansSC-Medium.otf）
3. **组件引用替换**：TMP 组件 m_fontAsset → (2,2409)、m_fontSharedMaterial → (2,211)——level 文件字节级 PPtr 替换（fileID=2 + pathID int64）
4. **NotoSerif SDF 资产**：`fonts/SDF_Font_Asset/NotoSerifCJKsc-Medium SDF.asset`（用户 Unity 6000 导出，8361 glyph + 4096² atlas）——验证过 atlas 与 glyph rect 配套
5. **部署状态**：sharedassets0 中 2409=NotoSerif 字体（687156B）、3002=纹理（16777336B 主文件格式）、211=材质（_MainTex=3002、_TextureWidth/Height=4096、_GradientScale=7）、753=NotoSC 原版 atlas
