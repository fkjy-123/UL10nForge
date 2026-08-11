# dollhouse 最终报告

## 概览

| 项 | 值 |
|---|---|
| 游戏 | dollhouse（2018.3.8f1 老 Unity 模板项目，文本极少） |
| 目录 | D:\游戏\dollhouse |
| 闭环轮次 | run1（2026-08-11） |
| 翻译条目 | 2 / 2（0 失败） |
| 写回 | 1 文本文件 · 2 条译文 · file/object PASS · runtime WARN（老引擎预期） |
| 汉化输出 | 已删除（只留原版） |

## 流程结果

1. **识别**：文本文件 1（app.info）· 识别条目 2。boot.config 引擎配置
   在 scanner `SKIP_DIRS` 目录级剪掉（第一层防护）；F14 提供解析层
   兜底（第二层防护，测试验证 5 条全跳过）
2. **翻译**（Hy-MT2-1.8B）：2 条全成功——`Olivia Haines`→`奥利维亚·海恩斯`
   （作者名）、`Dollhouse`→`玩偶屋`（游戏名）。app.info 是元数据记录
   （引擎不解析），标题本地化合理
3. **写回**：输入保护 ✓ 重开验证 ✓ 写入 2 条 · file/object PASS ·
   runtime WARN（2018.3 老 Unity 字体回退验证差异，风险无）·
   知识库 5 条规则启用
4. **清理**：`dollhouse_汉化` 已删除 ✓

## 质量结论

- **0 失败 / 0 跳过 / 0 哑信号**——条目极少且全部是合理处理：
  - app.info 2 条：作者名/游戏名，翻译正确
  - boot.config：识别层剪掉（SKIP_DIRS）+ 解析层跳过（F14）双保险，
    引擎配置值域（legacy/net_4_x/0/1）绝不翻译
- **无逻辑功能损坏**：boot.config 未被翻译（此前 legacy→「遗产」的
  破坏路径已封死）；app.info 引擎不解析，翻译无害

## 知识库沉淀

- boot.config 引擎配置值域（scripting-runtime-version=legacy 等）被当
  显示文本翻译 → **F14 文件级整体跳过**（含测试 2 个）

## 状态

**✅ 已闭环**。dollhouse 暴露的 F14 修复经测试 + 重跑验证（boot.config
5 条跳过、app.info 正常翻译写回），进入下一游戏对。
