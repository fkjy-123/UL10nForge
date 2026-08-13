"""把游戏指纹映射为可解释的自动后端计划。"""
from __future__ import annotations

from dataclasses import dataclass

from hanhua.core.font_support import FontProviderCapability
from hanhua.core.tooling.fingerprint import GameFingerprint
from hanhua.core.unity.il2cpp import SUPPORTED_LITERAL_RECORD_SIZES


@dataclass(frozen=True)
class BackendStep:
    step_id: str
    backend: str
    status: str
    required: bool
    confidence: str
    reason: str


def _tool_step(step_id: str, backend: str, state: str, *, required: bool,
               reason: str) -> BackendStep:
    if state == "verified":
        return BackendStep(step_id, backend, "pending", required, "high", reason)
    return BackendStep(step_id, backend, "blocked", required, "low",
                       f"{reason}；工具状态：{state or 'missing'}")


def plan_backends(fingerprint: GameFingerprint,
                  tool_states: dict[str, str], *,
                  font_capability: FontProviderCapability | None = None,
                  bitmap_provider_count: int = 0,
                  ) -> tuple[BackendStep, ...]:
    # 字体栈语义（Phase 4/5：planner 依据 Inventory 同源证据 font_stacks
    # 精化 provider 选择——动态/位图/未知栈决定 reason 与发布门语义；
    # bitmap_provider_count = 发现的可注入 .fnt 资产数，0 = 无 provider）
    stacks = fingerprint.font_stacks
    unverified_stack = "unverified_font_stack" in stacks
    runtime_fallback = "runtime_font_fallback" in stacks
    bitmap_stacks = any(s in stacks for s in ("ngui", "bitmap_font"))
    if runtime_fallback:
        stack_hint = "动态渲染消费者需运行时 attestation 证明（发布门消费）"
    elif bitmap_stacks:
        stack_hint = (
            f"位图渲染栈（NGUI/BMFont）已发现 {bitmap_provider_count} 个 "
            ".fnt 资产，写回阶段自动审计缺字并注入中文字库"
            if bitmap_provider_count
            else "存在位图渲染栈（NGUI/BMFont），但未发现可注入 .fnt 资产——"
                 "发布门保持阻断")
    elif unverified_stack:
        stack_hint = "存在未知渲染栈消费者——发布门 BLOCKED，候选确认不可绕过"
    else:
        stack_hint = ""
    steps = [
        BackendStep("detection", "native_fingerprint", "succeeded", True, "high",
                    f"{fingerprint.runtime} · Unity {fingerprint.unity_version}"),
        BackendStep("text_scan", "native_extractors", "pending", True, "high",
                    "结构化 UnityPy/dnfile/metadata 提取优先"),
    ]
    if "ambiguous_player_layout" in fingerprint.evidence:
        steps[1] = BackendStep(
            "text_scan", "unavailable", "blocked", True, "low",
            "存在多个未选择的 Unity player，禁止混合扫描",
        )
    if fingerprint.runtime == "il2cpp":
        steps.append(_tool_step(
            "tool_analysis", "il2cpp_dumper", tool_states.get("il2cpp_dumper", "missing"),
            required=True, reason="IL2CPP 字符串集合交叉验证"))
    else:
        steps.append(BackendStep(
            "tool_analysis", "native_only", "skipped", False, "high",
            "Mono 游戏无需 Il2CppDumper"))
    steps.append(BackendStep(
        "translation_quality", "quality_gate", "pending", True, "high",
        "占位符、标签、术语、语言与控制字符验证"))

    if "bitmap_font" in fingerprint.evidence:
        steps.append(_tool_step(
            "font_artifact", "bmfont", tool_states.get("bmfont", "missing"), required=False,
            reason="检测到外部位图字体契约，生成并验证中文字库"))
        if bitmap_provider_count:
            # Phase 5：发现可注入 .fnt 资产 → 自动注入（工具 verified 才
            # pending；工具缺失 → blocked 并给出状态原因）
            steps.append(_tool_step(
                "font_injection", "bmfont_inject",
                tool_states.get("bmfont", "missing"), required=False,
                reason=f"发现 {bitmap_provider_count} 个 BMFont 资产"
                       "（.fnt 描述器），写回阶段审计缺字并注入中文字库"))
        else:
            steps.append(BackendStep(
                "font_injection", "unsupported", "blocked", True, "low",
                "仅检测到 .fnt 证据；未发现可注入资产（无自动 injector）"))
    elif (font_capability is not None
          and not font_capability.provider_supported
          and font_capability.static_writeback_allowed):
        steps.append(BackendStep(
            "font", "static_replace", "pending", True,
            "high" if not bitmap_stacks else "medium",
            "IL2CPP 使用静态字体替换：legacy Font 内嵌 TTF / "
            "TMP_FontAsset 版本化 bundle 替换（写回阶段执行）"
            + (f"；{stack_hint}" if stack_hint else "")))
    elif font_capability is not None and not font_capability.provider_supported:
        steps.append(BackendStep(
            "font", font_capability.provider_id, "pending", True, "low",
            (font_capability.reason or "字体 provider 需要安装时验证")
            + (f"；{stack_hint}" if stack_hint else "")))
    elif font_capability is not None and font_capability.payload_available:
        steps.append(BackendStep(
            "font", font_capability.provider_id, "pending", True, "high",
            "使用已验证 TMP/UGUI 运行时中文回退"
            + (f"；{stack_hint}" if stack_hint else "")))
    elif font_capability is not None:
        steps.append(BackendStep(
            "font", font_capability.provider_id, "blocked", True, "low",
            (font_capability.reason or "字体 provider 固定载荷不可用")
            + (f"；{stack_hint}" if stack_hint else "")))
    elif fingerprint.runtime == "mono":
        steps.append(BackendStep(
            "font", "bepinex_runtime", "pending", True, "high",
            "使用已验证 TMP/UGUI 运行时中文回退"
            + (f"；{stack_hint}" if stack_hint else "")))
    else:
        steps.append(BackendStep(
            "font", "unavailable", "blocked", False, "low",
            "未检测到可验证的自动字体注入契约"
            + (f"；{stack_hint}" if stack_hint else "")))

    if fingerprint.runtime == "mono" or (
            fingerprint.runtime == "il2cpp"
            and fingerprint.metadata_version in SUPPORTED_LITERAL_RECORD_SIZES):
        steps.append(BackendStep(
            "writeback", "native_atomic_writer", "pending", True, "high",
            "使用原生 locator、staging、重开验证与原子提交"))
    else:
        steps.append(BackendStep(
            "writeback", "unsupported", "blocked", True, "low",
            "当前运行时/metadata 没有已验证自动 writer"))
    return tuple(steps)


def plan_is_unblocked(steps: tuple[BackendStep, ...]) -> bool:
    return not any(step.required and step.status in {"blocked", "failed"} for step in steps)


def plan_is_completable(steps: tuple[BackendStep, ...]) -> bool:
    return all(not step.required or step.status == "succeeded" for step in steps)
