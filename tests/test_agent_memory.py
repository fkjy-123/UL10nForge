"""AgentMemory 记忆模块测试（2026-08-12 用户指令：记忆模块）。

核心契约（「只记住好的内容 + 按具体情况翻译」）：
  1. 单次翻译只是提案（pending），≥2 次一致证据才晋升 active 参与运用；
  2. 直接应用需 phrase 型 + evidence≥3 + 零拒绝 + 跨游戏（或人工）；
  3. 语境敏感：同 key 不同 role 独立记忆，精确语境匹配优先，
     多语境分化的原文不用无语境记忆兜底（Resume 污染防护）；
  4. term 型（≤2 词）绝不直接应用；
  5. 反馈闭环：拒绝 → rejects+1 → 退休（≥2 次）；
  6. 同语境同 key 不同译文不覆盖（冲突信号）。
"""
import json

from hanhua.core.agent_memory import (
    AgentMemory, context_key_of, DIRECT_APPLY_MIN_EVIDENCE)


def _mem(tmp_path) -> AgentMemory:
    mem = AgentMemory(tmp_path / "agent_memory.db")
    mem.init_schema()
    return mem


def _grow(mem, key: str, value: str, games: list[str], role: str = "",
          morph: str = "") -> None:
    """跨游戏积累证据：每游戏 propose 一次（同游戏多次也计入证据）。"""
    for g in games:
        mem.propose(key, value, g, role=role, morph=morph)


def test_context_key_of_combines_role_and_morph():
    assert context_key_of("ui_button") == "r:ui_button"
    assert context_key_of("display", "small_config") == "r:display|m:small_config"
    assert context_key_of() == ""


def test_single_proposal_is_pending_and_not_usable(tmp_path):
    """单次翻译只是提案：不注入、不直接应用。"""
    mem = _mem(tmp_path)
    mem.propose("Press Start", "按开始", "game-a", role="display")
    assert mem.count() == 1
    assert mem.list_all()[0]["status"] == "pending"
    assert mem.direct_applications(["Press Start"]) == {}
    assert mem.reference_pairs() == []


def test_two_consistent_evidences_promote_to_active(tmp_path):
    """≥2 次一致证据（可跨游戏）→ active，参与参考注入。"""
    mem = _mem(tmp_path)
    _grow(mem, "Press Start", "按开始", ["game-a", "game-b"])
    row = mem.list_all()[0]
    assert row["status"] == "active"
    assert row["evidence_count"] == 2
    assert mem.reference_pairs() == [("Press Start", "按开始")]


def test_function_word_single_token_never_promotes(tmp_path):
    """F10c：单 token 英文功能词（on/off 类高频介词副词）证据充足也
    绝不晋升 active——做全局强制词对必然误杀自然文本（incremental-rts
    实证 'Analytics is ON.' / URL 内 on）。保持 pending（可人工复核），
    session 计数 blocked_function_words。"""
    mem = _mem(tmp_path)
    _grow(mem, "on", "在", ["game-a", "game-b", "game-c"])
    row = mem.list_all()[0]
    assert row["status"] == "pending"      # 功能词永不晋升
    assert mem.reference_pairs() == []
    report = mem.session_report(game="g")
    assert report["session"]["blocked_function_words"] >= 1
    # 对照：非功能词单 token 照常晋升（TIME 按钮词；高频普通词
    # miss/health 参考注入同样保留——强制过滤在 quality 检查端）
    _grow(mem, "TIME", "时间", ["game-a", "game-b"])
    assert mem.reference_pairs() == [("TIME", "时间")]


def test_same_context_diff_value_is_conflict_not_overwrite(tmp_path):
    """同语境同 key 不同译文 → 不覆盖、不积累证据，conflicts+1。"""
    mem = _mem(tmp_path)
    mem.propose("Resume", "继续", "game-a", role="ui_button")
    mem.propose("Resume", "恢复", "game-b", role="ui_button")
    row = mem.list_all()[0]
    assert row["value"] == "继续"          # 首译文保留
    assert row["evidence_count"] == 1      # 证据不积累（译文不一致）
    assert row["conflicts"] == 1
    conflicts = mem.detect_conflicts()
    assert len(conflicts) == 1
    assert conflicts[0]["key"] == "Resume"
    # 冲突记忆不参与运用（无 2 次一致证据，无法晋升 active）
    assert mem.reference_pairs() == []


def test_same_key_diff_context_is_independent_memory(tmp_path):
    """同 key 不同语境是独立记忆（Resume 按钮/名词不互相覆盖）。"""
    mem = _mem(tmp_path)
    mem.propose("Resume", "继续", "game-a", role="ui_button")
    mem.propose("Resume", "简历", "game-b", role="display")
    rows = {r["context_key"]: r for r in mem.list_all()}
    assert rows["r:ui_button"]["value"] == "继续"
    assert rows["r:display"]["value"] == "简历"
    assert mem.detect_conflicts() == []  # 语境分化不是冲突


def test_direct_apply_requires_three_evidence_and_multigame(tmp_path):
    """直接应用门槛：evidence≥3 + 跨游戏。"""
    mem = _mem(tmp_path)
    _grow(mem, "Ready to rumble!", "准备开打！",
          ["game-a", "game-b"], role="display")
    # 2 证据 → 注入但不直接应用
    assert mem.direct_applications(["Ready to rumble!"]) == {}
    # 3 证据 → 直接应用
    mem.propose("Ready to rumble!", "准备开打！", "game-c", role="display")
    got = mem.direct_applications(
        ["Ready to rumble!"], {"Ready to rumble!": "display"})
    assert got == {"Ready to rumble!": "准备开打！"}


def test_direct_apply_single_game_auto_not_applied(tmp_path):
    """单游戏积累（auto）不直接应用——缺跨游戏验证。"""
    mem = _mem(tmp_path)
    for _ in range(4):
        mem.propose("Save your game", "保存游戏", "game-a", role="display")
    assert mem.direct_applications(["Save your game"]) == {}


def test_direct_apply_single_game_manual_source_applies(tmp_path):
    """manual 来源（人工沉淀）单游戏也直接应用——人工即权威。"""
    mem = _mem(tmp_path)
    for _ in range(3):
        mem.propose("Boss Rush", "首领连战", "game-a", role="display",
                    source="manual")
    assert mem.direct_applications(
        ["Boss Rush"], {"Boss Rush": "display"}) == {"Boss Rush": "首领连战"}


def test_term_never_direct_applied(tmp_path):
    """term 型（≤2 词）绝不直接应用——单字词对是污染源。"""
    mem = _mem(tmp_path)
    _grow(mem, "miss", "未命中", ["g1", "g2", "g3"], role="display")
    assert mem.direct_applications(["miss"]) == {}
    assert mem.reference_pairs() == [("miss", "未命中")]  # 只注入参考


def test_exact_context_match_wins_over_plain(tmp_path):
    """精确语境匹配优先于无语境兜底。"""
    mem = _mem(tmp_path)
    _grow(mem, "Game Options", "游戏选项", ["g1", "g2", "g3"],
          role="ui_button")
    _grow(mem, "Game Options", "游戏选项设置", ["g1", "g2", "g3"],
          role="display")
    # 按钮语境条目 → 按钮语境记忆
    got = mem.direct_applications(
        ["Game Options"], {"Game Options": "ui_button"})
    assert got == {"Game Options": "游戏选项"}
    # 显示语境条目 → 显示语境记忆
    got = mem.direct_applications(
        ["Game Options"], {"Game Options": "display"})
    assert got == {"Game Options": "游戏选项设置"}


def test_multi_context_original_no_plain_fallback(tmp_path):
    """已语境分化的原文绝不用无语境记忆兜底（污染防护）。"""
    mem = _mem(tmp_path)
    _grow(mem, "Resume", "继续", ["g1", "g2", "g3"], role="ui_button")
    _grow(mem, "Resume", "简历", ["g1", "g2", "g3"], role="display")
    # 未知语境（role 不匹配任何记忆）→ 不用任一记忆兜底
    assert mem.direct_applications(["Resume"], {"Resume": "other"}) == {}


def test_unique_plain_memory_falls_back(tmp_path):
    """唯一无语境记忆可作兜底（原文从未分化出语境记忆）。"""
    mem = _mem(tmp_path)
    _grow(mem, "Welcome back!", "欢迎回来！", ["g1", "g2", "g3"])
    got = mem.direct_applications(["Welcome back!"], {"Welcome back!": "x"})
    assert got == {"Welcome back!": "欢迎回来！"}


def test_rejected_feedback_retires_after_two(tmp_path):
    """被质量门拒绝 → rejects+1 → 2 次后退休，不再参与任何运用。"""
    mem = _mem(tmp_path)
    _grow(mem, "Press Start", "按开始", ["g1", "g2", "g3"], role="display")
    ckey = context_key_of("display")
    assert mem.direct_applications(["Press Start"]) != {}
    mem.apply_feedback("Press Start", ckey, accepted=False)
    assert mem.list_all()[0]["rejects"] == 1
    assert mem.list_all()[0]["status"] == "active"  # 首次拒绝未退休
    # 1 次拒绝后仍给一次机会（质量门误杀容错）
    assert mem.direct_applications(["Press Start"]) == {"Press Start": "按开始"}
    mem.apply_feedback("Press Start", ckey, accepted=False)
    assert mem.list_all()[0]["status"] == "retired"  # 2 次确认不可信
    assert mem.reference_pairs() == []
    assert mem.direct_applications(["Press Start"]) == {}


def test_accepted_feedback_increments_hits(tmp_path):
    mem = _mem(tmp_path)
    _grow(mem, "Nice job", "干得好", ["g1", "g2", "g3"], role="display")
    mem.apply_feedback("Nice job", context_key_of("display"), accepted=True)
    assert mem.list_all()[0]["hits"] == 1


def test_session_report_shape(tmp_path):
    mem = _mem(tmp_path)
    mem.session_reset()
    _grow(mem, "Start Game", "开始游戏", ["g1", "g2"], role="ui_button")
    report = mem.session_report(game="demo-game")
    assert report["game"] == "demo-game"
    assert report["session"]["proposed"] == 1   # 新提案（首条插入）
    assert report["session"]["evidence_added"] == 1  # 第二条是证据积累
    assert report["session"]["confirmed"] == 1
    assert report["library"]["phrase"]["active"] == 1
    assert report["top_memories"][0]["key"] == "Start Game"
    assert report["conflicts"] == []


def test_propose_empty_value_ignored(tmp_path):
    mem = _mem(tmp_path)
    mem.propose("", "x", "g1")
    mem.propose("key", "", "g1")
    assert mem.count() == 0


def test_games_dedup_across_same_game(tmp_path):
    """同一游戏多次证据不重复计入跨游戏数。"""
    mem = _mem(tmp_path)
    for _ in range(4):
        mem.propose("Go go go", "冲鸭", "only-game", role="display")
    row = mem.list_all()[0]
    assert row["evidence_count"] == 4
    assert json.loads(row["games"]) == ["only-game"]
    assert mem.direct_applications(["Go go go"]) == {}  # 单游戏不直接应用
