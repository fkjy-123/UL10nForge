# Rendezvous TMP 静态 SDF 运行时兜底设计

## 目标

解决问题 #001：Rendezvous 汉化文本在冷启动、主菜单和游戏内大量显示方块。修复必须保留现有 Legacy/UGUI 字体链路，并能通过冷启动截图、插件日志和 `font-health.json` 共同验收。

## 已确认事实

- 游戏为 Unity 2019.4.22f1、Mono、TextMeshPro 2.x。
- 官方思源黑体 OTF 的 cmap 没有问题，Legacy 字体验证为 1769/1769。
- 全新进程的动态 TMP 字体只验证出 1/1769 个字形；因此继续扫描组件或加强 Harmony Hook 不能解决主要缺字。
- 仓库已有与 Unity 2019/TMP 2.x 匹配的 `sourcehan_sdf_medium_u2019` AssetBundle，哈希符合 manifest，包含 8361 个静态字形，覆盖当前需求集 1727/1769。
- 剩余 42 个字符主要来自异常的多语言拼接文本；其中仅 `裏`、`鲶` 是中文。它们不能阻止主修复上线，但健康报告必须如实披露。

## 方案

### 部署

`install_font_override` 在检测到 Unity 2019/2020 Mono 游戏时，把匹配字重的 TMP bundle 复制为插件目录下固定文件 `font-tmp.bundle`。没有兼容 bundle 时保持现有 OTF 动态路径，不令其他游戏回归。

### 插件加载

插件优先调用 `AssetBundle.LoadFromFile` 加载 `font-tmp.bundle`，从 bundle 中选择 `TMP_FontAsset`。成功后将其设为当前 TMP 主字体，并保持 AssetBundle 在插件生命周期内存活；失败时记录明确原因并回退现有动态字体工厂。

### 字体应用与 fallback

当插件把文本的主字体切换到静态 SDF 时，把该文本原来的 TMP 字体追加到静态字体的 fallback 表，而不是丢弃。这样中文由 Source Han SDF 渲染，拉丁、日文和其他原游戏已支持字符仍可由原字体渲染。重复扫描必须幂等，不能不断追加相同 fallback。

Harmony `TMP_Text.set_text` 和定时扫描共用同一字体应用函数，避免两条链路行为分叉。场景加载后重新扫描，确保启动提示、主菜单及延迟实例化文本都被覆盖。

### 健康检查

`font-health.json` 增加 TMP 字体来源和 bundle 加载状态。适配器只有在需求集逐码点验证后才能报告 ready；代表字“项”仅用于快速探针，不能再把 1/1769 误判为可用。

验收分两层：

1. 静态/自动测试证明 bundle 被部署、插件优先加载 bundle、原字体进入 fallback、失败可回退。
2. Rendezvous 冷启动后确认日志出现 bundle ready，TMP 覆盖从 1 提升到至少 1727，并以截图确认启动提示及主菜单不再大量显示方块。

### 剩余字符策略

本阶段不把异常的多语言拼接翻译扩展为字体需求。静态 SDF 主字体覆盖全部常用简体中文；原字体 fallback 处理非中文字符。`裏` 和 `鲶` 若仍在用户可见文本中出现，则在运行时翻译生成/装载边界分别规范化为 `里` 与 `鲇`，并由回归测试锁定。原始游戏文本不做全局破坏性替换。

## 错误处理

- bundle 缺失、版本不兼容、加载异常或找不到 TMP_FontAsset：写入带阶段名的日志，卸载半成品并回退动态 OTF。
- bundle 成功加载后不得在运行中卸载其资源；插件销毁时使用 `Unload(false)` 释放容器。
- 健康文件必须区分 `bundle`、`dynamic` 和 `failed`，不能静默降级。

## 范围外

- 不重新翻译已丢失的 level 文本。
- 不重编译 `Assembly-CSharp.dll`。
- 不重构整个 3500 行插件；只提取本修复需要复用的最小字体应用边界。
- 不修改用户现有备份或删除原游戏文件。
