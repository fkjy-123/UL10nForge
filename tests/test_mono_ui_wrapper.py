"""Mono DLL 传递式 UI setter 验证：包装方法传参的字符串字面量必须放行。

cell-machine 真实样本：教程/细胞说明文本经游戏自封装方法 SetTutorialText(text)
传入 TextMeshProUGUI.set_text——ldstr 与 setter 调用不相邻（中间隔着包装方法），
直接邻接验证会全部漏过。此 fixture 覆盖四种消费路径：
  1) 直接赋值（原有验证路径，回归保护）
  2) 包装方法传参（修复目标）
  3) 两层包装传递链（不动点迭代覆盖）
  4) 日志 / 字符串拼接（必须保持跳过）
"""
from pathlib import Path

from hanhua.core.unity.mono_dll import extract_dll_user_strings

FIXTURES = Path(__file__).parent / "fixtures"
WRAPPER = FIXTURES / "mono_ui_wrapper.dll"


def _status_map() -> dict[str, str]:
    pf = extract_dll_user_strings(WRAPPER)
    assert not pf.noise
    return {e.original: e.status for e in pf.entries}


def test_direct_assignment_remains_verified():
    status = _status_map()
    assert status["Direct text assignment"] == "pending"


def test_wrapper_method_string_argument_verified():
    status = _status_map()
    # 字符串是包装方法的第二个参数（非栈顶），仍须验证为 UI 文本
    assert status["Most cells can be pushed by others"] == "pending"


def test_two_level_wrapper_chain_verified():
    status = _status_map()
    # 传递闭包：Wrapper2 → SetTutorialText → set_text
    assert status["Chained text via two helpers"] == "pending"


def test_log_and_concat_strings_stay_skipped():
    status = _status_map()
    # Console.WriteLine / String.Concat 不流入 UI setter → 保守跳过
    assert status["log only string"] == "skipped"
    assert status["composed text"] == "skipped"


def test_unityscript_assembly_upgrades_unverified_text(tmp_path):
    # 同一 fixture 以 Assembly-UnityScript.dll 命名：UnityScript 编译器生成的
    # IL 形态使 ui setter 验证链大面积失效（lilys-day-off 实证 825 条对话/
    # 服装/结局/选项文本全落 unverified 被跳过）。UnityScript 程序集字面量
    # 几乎全是显示文本——未被剔除的字符串（含空格对话与无空格语气词
    # 'What?' 'Hahaha!'）全部按显示文本升级；纯标识符已被 is_code_identifier
    # 剔除（lilys-day-off 实证：29 条无空格语气词恢复翻译）。
    import shutil
    us = tmp_path / "Assembly-UnityScript.dll"
    shutil.copy2(FIXTURES / "mono_ui_wrapper.dll", us)
    pf = extract_dll_user_strings(us)
    assert not pf.noise
    by_text = {e.original: e for e in pf.entries}
    # 含空格 unverified 字符串升级为可翻译
    assert by_text["log only string"].status == "pending"
    assert by_text["log only string"].meta["confidence"] == "medium"
    assert by_text["log only string"].meta["reason"] == "unityscript_user_string"
    assert by_text["composed text"].status == "pending"
    # ui setter 验证链在 UnityScript 程序集中不受影响
    assert by_text["Direct text assignment"].status == "pending"
    assert by_text["Direct text assignment"].meta["confidence"] == "high"
    # 升级后全部条目 pending（fixture 无标识符样本；标识符剔除在
    # is_code_identifier 层保证，见下方判定性测试）
    assert all(e.status == "pending" for e in pf.entries)


def test_unityscript_particle_text_is_not_a_structural_identifier():
    # 'What?' 'Hahaha!' 'Lily-chan!' 等语气词无空格但含标点，不是
    # code_identifier/engine/structural——UnityScript 路径必升级。
    from hanhua.core.engine_strings import is_engine_string
    from hanhua.core.placeholders import is_hard_structural, is_code_identifier
    for particle in ("What?", "Hahaha!", "Lily-chan?", "Kyahaaaaa~!", "NOO!!!"):
        assert not is_code_identifier(particle)
        assert not is_engine_string(particle)
        assert not is_hard_structural(particle)
