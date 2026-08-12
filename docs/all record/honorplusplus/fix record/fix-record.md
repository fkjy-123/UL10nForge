# honorplusplus 修复记录（2026-08-13，全局 F 系列修复实证）

> 本轮跑出并落地的修复全部是**全局性**问题（非本游戏特判），
> 已在代码层修复 + 回归全绿，后续游戏直接受益。

## 修复 F4：审核探测携带 Authorization（review_server._http_probe）

- **现象**：hickory/honorplusplus 两游戏审核条数恒为 0（reviewed=0，
  review-report.md 空报告），翻译/写回一切正常——审核链路静默失效
- **根因链**（2026-08-13 三次复现实证）：
  1. `_http_probe` 探测不带 Bearer key → 带鉴权的 llama-server 返回
     401 → 误判「实例不可用」→ 每次运行重复启动新 4B
  2. Windows llama-server **SO_REUSEADDR**：多实例可绑同一端口 8081，
     新连接由内核随机分发给任一实例 → 复用者拿 runtime key 请求
     可能打到别的实例 → Invalid API Key → 审核静默 0 判定
     （review_one 的 `except: return None` 吞掉错误）
- **修复**（`hanhua/core/review_server.py`）：
  - probe 携带 `Authorization: Bearer {api_key}`
  - 启动新实例前 `_clear_stale_review_port(8081)`：netstat -ano 找
    LISTENING 占用者 → taskkill /F（只杀端口占用者，翻译实例
    不同端口不受影响）
- **验证**：honorplusplus 完整重跑 → 审核 68 条 · 不合格 13 ·
  术语沉淀 5（此前恒 0）

## 修复 F5：runner 输出 GBK 崩溃（UTF-8 reconfigure）

- **现象**：hickory/honorplusplus 均在翻译汇总/写回打印含 ⚠ 的行时
  UnicodeEncodeError 崩溃（exit 1，Windows 控制台 GBK）
- **修复**：`scripts/all_record_runner.py` 顶部
  `sys.stdout/stderr.reconfigure(encoding="utf-8", errors="replace")`

## 修复 F6：审核模型名展示（SemanticReviewer.model_name）

- **现象**：runner:576 `f"- 审核模型：{reviewer.config.model}"` 抛
  `'ReviewConfig' has no attribute 'model'`（ReviewConfig 只有
  timeout/max_tokens/batch_size/enabled）
- **修复**：SemanticReviewer 新增 `model_name` 属性（registry 实际
  定位的 GGUF 文件名），runner 消费

## 修复 F7：质量门漏拦中置「翻译为」解释句式

- **现象**：honorplusplus us#9445 首译 `f={0} DEBUG 翻译为 DEBUG {1}`
  （25 chars）过质量门 → 写回容量截断丢占位符 → 被拒（写回防护
  正确兜底）
- **根因**：`_EXPLANATORY_PATTERN` 只拦前缀/特定解释短语，中置
  「X 翻译为 Y」句式漏网
- **修复**（`hanhua/core/quality.py`）：追加
  `\w+\s*翻译为\s*\S+`（20 字符门槛防短文本误伤）
- **验证**：回归全绿；被拒条目的真实防护行为（占位符保护）保持

## 待办 A（登记，不在本游戏特判）

1. **技术字符串不该翻译**（审核实证 e424/e406）：HTTP 协议文本
   （`POST /?{0} HTTP/1.1` / `Host: {1}`）、Unity 内部日志格式串
   （`AABB Center:{0}, HalfExtents:{1}`）进入翻译池被翻译 →
   Host→主持人 等错译。应走「协议/格式串识别豁免」——待积累真实
   样本后定位识别层判定统一修复（与 222am 待办 A 同类）
2. **回显型失败（30 条，本游戏全部失败）**：single_visible_string 8 /
   user_string_uppercase_ui 9 / display_phrase 10 / mono_ui_setter 3——
   logout→Logout、honor++→honor++ 等英文保留被判 untranslated。
   与 222am 的 keep 术语回显同类但更普遍：**纯英文单串/大写 UI
   串的正确策略就是保留**，质量门应豁免而非判失败——待多游戏
   样本交叉验证后统一修质量门
3. **CC0 许可证长文本**：CC0 1.0 声明多行文本（39 行）记忆告警
   「不同译文」——模型对大段法律文本翻译不稳定，且这类文本在
   游戏内通常以英文原文展示（许可证性质），长期可考虑「长法律
   文本保留英文」策略（登记，不在本游戏特判）
