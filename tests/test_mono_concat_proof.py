"""证明链 Concat 传播测试（动态文本成分证明）。

合成 IL + 假 PE：验证 String.Concat 拼接片段里的字面量在流入 UI
setter 时被证明为显示文本（`"Level " + level` 的 `"Level "` 形态）；
被丢弃的拼接结果不被验证（回归保护，与 String.Format 同语义）。
"""
from __future__ import annotations

import struct
from types import SimpleNamespace

from hanhua.core.unity.mono_dll import extract_dll_user_strings


def _build_fake_pe(heap, bodies, member_refs, method_defs=None):
    class FakeUserStrings:
        def sizeof(self):
            return len(heap)

        def get_data_at_offset(self, offset, size):
            return bytes(heap)

        def get_file_offset(self, offset):
            return 100

    if method_defs is None:
        method_defs = [SimpleNamespace(Rva=rva) for rva in bodies]
    return SimpleNamespace(
        net=SimpleNamespace(
            user_strings=FakeUserStrings(),
            mdtables=SimpleNamespace(
                MemberRef=SimpleNamespace(rows=member_refs),
                MethodDef=SimpleNamespace(rows=method_defs),
            ),
        ),
        get_data=lambda rva, size: bodies.get(rva, b"")[:size],
        close=lambda: None,
    )


def _text_ref(name, ns="System", type_name="String",
              signature=b"\x00\x02\x0e\x0e\x0e"):
    declaring = SimpleNamespace(TypeName=type_name, TypeNamespace=ns)
    return SimpleNamespace(
        Name=name, Class=SimpleNamespace(row=declaring),
        Signature=SimpleNamespace(value=signature))


def _setter_ref():
    declaring = SimpleNamespace(TypeName="TMP_Text", TypeNamespace="TMPro")
    return SimpleNamespace(
        Name="set_text", Class=SimpleNamespace(row=declaring))


def _heap_of(texts):
    heap = bytearray(b"\x00")
    tokens = []
    for text in texts:
        raw = text.encode("utf-16-le") + b"\x01"
        tokens.append(len(heap))
        heap.extend((len(raw),))
        heap.extend(raw)
    return bytes(heap), tokens


def _extract(heap, bodies, member_refs, monkeypatch, tmp_path,
             method_defs=None):
    import dnfile
    fake_pe = _build_fake_pe(heap, bodies, member_refs, method_defs)
    monkeypatch.setattr(dnfile, "dnPE", lambda _path: fake_pe)
    parsed = extract_dll_user_strings(tmp_path / "Custom.Game.dll")
    return {e.original: e for e in parsed.entries
            if not e.key_path.startswith("skip/")}


_SETTER = 0x0A000001
_CONCAT2 = 0x0A000002
_CONCAT3 = 0x0A000003
_CONCAT_PARAMS = 0x0A000004


def _members():
    return [
        _setter_ref(),
        _text_ref("Concat", signature=b"\x00\x02\x0e\x0e\x0e"),   # (string, string)
        _text_ref("Concat", signature=b"\x00\x03\x0e\x0e\x0e\x0e"),  # (string×3)
        _text_ref("Concat", signature=b"\x00\x01\x0e\x1c"),  # (object[]) params 重载
    ]


def _ldstr(token):
    return b"\x72" + struct.pack("<I", 0x70000000 | token)


def _call(token):
    return b"\x28" + struct.pack("<I", token)


def _callvirt(token):
    return b"\x6f" + struct.pack("<I", token)


class TestConcatProof:
    def test_fragment_into_setter_verified(self, tmp_path, monkeypatch):
        # text.text = "Level " + level;
        heap, tokens = _heap_of(["Level ", "Unrelated"])
        code = (_ldstr(tokens[0]) + b"\x16"        # ldstr; ldc.i4.0
                + _call(_CONCAT2) + _callvirt(_SETTER) + b"\x2a")
        bodies = {0x2000: bytes(((len(code) << 2) | 2,)) + code}
        by_original = _extract(heap, bodies, _members(), monkeypatch, tmp_path)
        e = by_original["Level "]
        assert e.status == "pending"
        assert e.meta["reason"] == "mono_ui_setter"
        assert e.meta["confidence"] == "high"

    def test_multi_literal_fragment_all_verified(self, tmp_path, monkeypatch):
        # text.text = "HP: " + hp + " of ";   (C# 编译为 Concat(3))
        heap, tokens = _heap_of(["HP: ", " of ", "Noise"])
        code = (_ldstr(tokens[0]) + b"\x16"
                + _ldstr(tokens[1])
                + _call(_CONCAT3) + _callvirt(_SETTER) + b"\x2a")
        bodies = {0x2000: bytes(((len(code) << 2) | 2,)) + code}
        by_original = _extract(heap, bodies, _members(), monkeypatch, tmp_path)
        assert by_original["HP: "].meta["reason"] == "mono_ui_setter"
        assert by_original[" of "].meta["reason"] == "mono_ui_setter"

    def test_discarded_fragment_not_verified(self, tmp_path, monkeypatch):
        # string s = "Score: " + x;  (结果未流入 setter)
        heap, tokens = _heap_of(["Score: "])
        code = (_ldstr(tokens[0]) + b"\x16"
                + _call(_CONCAT2) + b"\x26\x2a")   # pop; ret
        bodies = {0x2000: bytes(((len(code) << 2) | 2,)) + code}
        by_original = _extract(heap, bodies, _members(), monkeypatch, tmp_path)
        assert by_original["Score: "].status == "skipped"
        assert by_original["Score: "].meta["reason"] == "unverified_user_string"

    def test_params_overload_conservative(self, tmp_path, monkeypatch):
        # string.Join 类 params 重载（arity=None）：调用点清栈，不误放行
        heap, tokens = _heap_of(["Alpha part", "Bravo part"])
        code = (_ldstr(tokens[0]) + _ldstr(tokens[1])
                + _call(_CONCAT_PARAMS) + _callvirt(_SETTER) + b"\x2a")
        bodies = {0x2000: bytes(((len(code) << 2) | 2,)) + code}
        by_original = _extract(heap, bodies, _members(), monkeypatch, tmp_path)
        assert by_original["Alpha part"].status == "skipped"
        assert by_original["Bravo part"].status == "skipped"

    def test_concat_through_wrapper_chain(self, tmp_path, monkeypatch):
        # wrapper(string s) { text.text = "Prefix " + s; }
        # 调用点：wrapper("Gold") → "Prefix " 与 "Gold" 都应被证明
        heap, tokens = _heap_of(["Prefix ", "Gold"])
        wrapper_code = (
            _ldstr(tokens[0]) + b"\x02"            # ldstr; ldarg.0
            + _call(_CONCAT2) + _callvirt(_SETTER) + b"\x2a")
        call_code = _ldstr(tokens[1]) + _call(0x06000001) + b"\x2a"
        bodies = {
            0x2000: bytes(((len(wrapper_code) << 2) | 2,)) + wrapper_code,
            0x3000: bytes(((len(call_code) << 2) | 2,)) + call_code,
        }
        method_defs = [
            SimpleNamespace(
                Name="Wrapper",
                Rva=0x2000,
                Signature=SimpleNamespace(value=b"\x00\x01\x01\x0e")),
            # Signature：default + 1 参 + ret(void=0x01) + string 参数
            SimpleNamespace(
                Name="Caller",
                Rva=0x3000,
                Signature=SimpleNamespace(value=b"\x00\x00\x01")),
        ]
        by_original = _extract(
            heap, bodies, _members(), monkeypatch, tmp_path,
            method_defs=method_defs,
        )
        # wrapper 体内 concat 消耗 ("arg",0) 片段 → setter 消费时该参数
        # gained → 调用点 "Gold" 经包装链验证；"Prefix " 直接验证
        assert by_original["Prefix "].meta["reason"] == "mono_ui_setter"
        assert by_original["Gold"].meta["reason"] == "mono_ui_setter"


class TestStringBuilderAndIMGUI:
    """StringBuilder 拼接链与 IMGUI OnGUI 显示调用（语料挖掘实证）。"""

    def _sb_members(self):
        from tests.test_mono_concat_proof import _text_ref, _setter_ref
        sb_type = "StringBuilder"
        return [
            _setter_ref(),
            _text_ref(".ctor", ns="System.Text", type_name=sb_type,
                      signature=b"\x00\x01\x01\x0e"),
            _text_ref("Append", ns="System.Text", type_name=sb_type,
                      signature=b"\x00\x02\x01\x0e\x0e"),
            _text_ref("AppendLine", ns="System.Text", type_name=sb_type,
                      signature=b"\x00\x02\x01\x0e\x0e"),
            _text_ref("AppendFormat", ns="System.Text", type_name=sb_type,
                      signature=b"\x00\x03\x01\x0e\x0e\x1c"),
            _text_ref("ToString", ns="System.Text", type_name=sb_type,
                      signature=b"\x00\x00\x0e"),
            _text_ref("Label", ns="UnityEngine", type_name="GUI",
                      signature=b"\x00\x01\x01\x0e"),
        ]

    def test_stringbuilder_chain_verified(self, tmp_path, monkeypatch):
        # var sb = new StringBuilder("HP: "); sb.Append(hp);
        # sb.Append(" / "); sb.Append(max); text.text = sb.ToString();
        heap, tokens = _heap_of(["HP: ", " of ", "Noise"])
        code = (
            _ldstr(tokens[0])                    # 构造器初始内容
            + b"\x73" + struct.pack("<I", _CTOR)  # newobj StringBuilder
            + b"\x16"                             # ldc.i4.0 (hp)
            + _callvirt(_APPEND)                  # Append(int) 消耗非字面量
            + _ldstr(tokens[1])
            + _callvirt(_APPEND)                  # Append(" / ")
            + b"\x16"
            + _callvirt(_APPEND)
            + _callvirt(_TOSTRING)                # ToString → frag
            + _callvirt(_SETTER) + b"\x2a")
        bodies = {0x2000: bytes(((len(code) << 2) | 2,)) + code}
        by_original = _extract(heap, bodies, self._sb_members(),
                               monkeypatch, tmp_path)
        assert by_original["HP: "].meta["reason"] == "mono_ui_setter"
        assert by_original[" of "].meta["reason"] == "mono_ui_setter"

    def test_stringbuilder_discarded_not_verified(self, tmp_path,
                                                  monkeypatch):
        # sb.Append("Score: ") 后 sb 从未 ToString 流入 setter → 不验证
        heap, tokens = _heap_of(["Score: "])
        code = (
            _ldstr(tokens[0])
            + b"\x73" + struct.pack("<I", _CTOR)
            + _ldstr(tokens[0])
            + _callvirt(_APPEND) + b"\x26\x2a")   # pop; ret
        bodies = {0x2000: bytes(((len(code) << 2) | 2,)) + code}
        by_original = _extract(heap, bodies, self._sb_members(),
                               monkeypatch, tmp_path)
        assert by_original["Score: "].status == "skipped"

    def test_imgui_label_verified(self, tmp_path, monkeypatch):
        # OnGUI() { GUI.Label(new Rect(...), "Health"); }
        heap, tokens = _heap_of(["Health"])
        code = (_ldstr(tokens[0])
                + _call(_GUI_LABEL) + b"\x2a")
        bodies = {0x2000: bytes(((len(code) << 2) | 2,)) + code}
        by_original = _extract(heap, bodies, self._sb_members(),
                               monkeypatch, tmp_path)
        assert by_original["Health"].meta["reason"] == "mono_ui_setter"
        assert by_original["Health"].meta["confidence"] == "high"


_CTOR = 0x0A000002
_APPEND = 0x0A000003
_APPENDLINE = 0x0A000004
_APPENDFMT = 0x0A000005
_TOSTRING = 0x0A000006
_GUI_LABEL = 0x0A000007
