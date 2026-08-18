# Rendezvous SDF 条纹修复设计

## 目标

修复 Rendezvous 中文 TMP 字体出现水平条纹、笔画断裂和重影的问题，同时保持现有字符覆盖与排版。

## 根因与方案

源 SDF 图集为 4096×4096，但 bundle 骨架材质保留了 8192×8192 的 `_TextureWidth/_TextureHeight`，且梯度参数未与源资产一致。重建 bundle 时将材质采样契约固定为 4096×4096、`_GradientScale=10`，并部署 Unity 2019 bundle；字体表和图集数据不变。

## 验证

自动检查 bundle 的 Texture2D 尺寸与 Material 浮点参数一致，并运行现有字体/TMP 测试；最后将修复后的 bundle 复制到 Rendezvous 的 BepInEx 插件目录。
