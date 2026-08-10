# 修复 8：类型引用误分类（Fungus.Flowchart 被译成「真菌.流程图」写回）

## 问题

第七跑核查时发现：`Fungus.Flowchart, Fungus`（.NET 类型名，Fungus 对话插件的
Flowchart 类 + 程序集名）被识别为 natural_language/display 进翻译池，
模型译成「真菌.流程图, 真菌」并**写回游戏**（level0:174、level0:192、level1:3235 共 3 条）。
第六跑该 3 条是回显（模型未翻），第七跑模型自信意译——类型名改写破坏
序列化/反射引用，且玩家根本看不到（运行时类型名）。

## 根源

`extractor.py` 的 `_ASSEMBLY_REFERENCE` 正则对程序集部分设置了白名单
（`Assembly-*` / `Unity.*` / `UnityEngine*` / `System*` / `mscorlib`）：
`UnityEngine.Object, UnityEngine` 命中白名单正确拦截（type_reference），
但 `Fungus.Flowchart, Fungus` 的程序集名 `Fungus` 不在白名单 → 不命中 →
回落到 natural_language 进池。**白名单模式无法覆盖第三方插件类型。**

## 修复方案（形态识别替代白名单）

`Namespace.Type, Assembly`（`A.B, C` 点连标识符 + 逗号分隔程序集）本身
就是 .NET 类型引用信号——人类显示文本几乎不出现该形态（`Mr. Smith, John`
因点后带空格不匹配，`.` 后必须紧跟标识符）。改为：

```python
_ASSEMBLY_REFERENCE = _re.compile(
    r"^(?:"
    r"[A-Za-z_][A-Za-z0-9_+`]*(?:\.[A-Za-z_][A-Za-z0-9_+`]*)+,\s*"
    r"[A-Za-z_][A-Za-z0-9_.-]*"              # A.B, 任意程序集
    r"|[A-Za-z_][A-Za-z0-9_+`]*,\s*Assembly-[A-Za-z0-9_.-]+"  # A, Assembly-X
    r")"
    r"(?:,\s*Version=[^,\s]+(?:,\s*Culture=[^,\s]+,\s*"
    r"PublicKeyToken=[^,\s]+)?)?$",
    _re.I)
```

- 分支 1：`A.B, 任意程序集`（Fungus.Flowchart, Fungus / System.String, mscorlib）
- 分支 2：`A, Assembly-X`（MenuButton, Assembly-CSharp，保留原 Assembly- 前缀支持）
- 版本/公钥段可选

## 修复代码位置

| 文件 | 位置 |
|---|---|
| hanhua/core/unity/extractor.py | `_ASSEMBLY_REFERENCE` 正则 |
| tests/test_v2.py | `test_assembly_reference_generic_assembly`（新）+ 旧测试保持 |

## 验证

- 332 passed（新增 6 正例 + 5 反例：Mr. Smith/Dr. Who/I.R.S. 不误伤）
- 第八跑 a-catfiends 全流程重跑：3 条 Fungus 类型名应全部 skipped（type_reference），
  不再进翻译池

## 防复发

- 形态识别不依赖程序集白名单，任何第三方插件类型（Fungus/ProBuilder/Poly2Tri）
  自动覆盖
- 该模式仅用于二进制 rawstr 提取（_structural_reason），文本文件行扫描
  （txt/csv/本地化表）不经此规则，句子级文本不受影响
