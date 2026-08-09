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
