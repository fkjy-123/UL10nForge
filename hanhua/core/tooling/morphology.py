"""Unity 文本载体形态注册表（显式清单）。

识别模块的「形态覆盖」是可审计事实：每个扫描来源文件归类到注册表形态，
未注册形态 → 显式告警（不静默按最低策略处理）。形态**文本先验**决定该
形态字符串的语义（dense：字面量几乎全是显示文本——UnityScript/Boo 程序集；
mixed：显示文本与键名/结构值混合）。

历史教训（0.14.0/0.14.1 复盘）：
- UnityScript 程序集的 dense 先验此前藏在启发式里未显式化，825 条对话/
  服装/结局文本被 ui setter 验证链跳过，随后 29 条无空格语气词又被
  「无空格不升级」边界跳过；
- Boo 程序集此前不在 fallback 前缀列表，整个不提取；
- 'A game by Kyuppin'（typetree m_Text）被 credit 软猜测规则降级——
  证据分层后此类问题由代码结构保证，本注册表保证「形态级覆盖」可审计。

流程约定（docs/识别形态覆盖与遗漏处理.md）：用户实测发现遗漏 →
证据分层审查 → 真实样本锚点 fixture → 若为新形态先注册此处再接线。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Morphology:
    name: str            # 注册表键（classify 返回值）
    extractor: str       # 提取器名（可审计绑定）
    prior: str           # dense / mixed 文本先验
    description: str     # 中文说明（含实证锚点来源）


REGISTRY: tuple[Morphology, ...] = (
    Morphology(
        "mono_csharp", "extract_dll_user_strings", "mixed",
        "C# 编译程序集（Assembly-CSharp*）：显示文本与键名/绑定名混合，"
        "ui setter 传递验证链定向于此形态"),
    Morphology(
        "mono_unityscript", "extract_dll_user_strings", "dense",
        "UnityScript/旧 JS 编译程序集（Assembly-UnityScript*）：字面量几乎"
        "全是显示文本（lilys-day-off 实证 854 条对话/语气词/服装/结局文本；"
        "0.14.0 恢复含空格，0.14.1 恢复无空格语气词）"),
    Morphology(
        "mono_boo", "extract_dll_user_strings", "dense",
        "Boo 编译程序集（Assembly-Boo*）：同 UnityScript 语言先验，"
        "0.14.0 补 fallback 前缀（此前整个不提取）"),
    Morphology(
        "mono_other", "extract_dll_user_strings", "mixed",
        "manifest 自定义名游戏程序集（StgAssembly_* 等，绕过 assembly-* "
        "前缀命名）：C# 编译，无语言先验可依赖"),
    Morphology(
        "asset_unity", "extract_asset_file", "mixed",
        "Unity 序列化/资源包容器（level*/sharedassets*/.assets/bundle/"
        "TextAsset/typetree/MonoBehaviour 原始串）：提取器内部按字段证据"
        "分层（0.14.1 证据分层原则）"),
    Morphology(
        "il2cpp_metadata", "extract_metadata_strings", "mixed",
        "IL2CPP global-metadata.dat 字符串字面量（native 解析 + "
        "Il2CppDumper 交叉验证）"),
)

_BY_NAME = {m.name: m for m in REGISTRY}


def morphology(name: str) -> Morphology | None:
    return _BY_NAME.get(name)


def classify_morphology(rel: str) -> str | None:
    """来源文件（game_dir 相对路径）→ 注册表形态名；None = 未知形态。

    未知形态必须显式告警（扫描报告 + UI）：静默按最低策略处理正是
    0.14.0 之前整类遗漏的土壤。当前扫描管线三类来源全部可归类；
    None 分支是未来新提取器/新容器类型的强制登记点。
    """
    low = rel.casefold().replace("\\", "/")
    name = low.rsplit("/", 1)[-1]
    if low.endswith(".dll"):
        if name.startswith("assembly-csharp"):
            return "mono_csharp"
        if name.startswith("assembly-unityscript"):
            return "mono_unityscript"
        if name.startswith("assembly-boo"):
            return "mono_boo"
        return "mono_other"
    if "global-metadata" in name or name == "metadata.dat":
        return "il2cpp_metadata"
    return "asset_unity"
