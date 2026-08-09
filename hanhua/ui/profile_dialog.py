"""项目游戏档案编辑弹窗（档案属于项目，不是全局设置）。"""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                               QVBoxLayout)

from hanhua.core.models import GameProfile

SOURCE_LANGS = ["auto", "English", "日本語", "한국어", "Deutsch", "Français",
                "Русский", "Español", "Italiano", "Português", "其他"]


class ProfileDialog(QDialog):
    def __init__(self, profile: GameProfile, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑游戏档案")
        self.setMinimumWidth(560)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)

        hint = QLabel("档案只属于当前项目，会注入翻译提示词——填得越详细，翻译越贴合游戏。")
        hint.setProperty("class", "subtitle")
        lay.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(12)
        self.name = QLineEdit(profile.game_name)
        self.genre = QLineEdit(profile.genre)
        self.genre.setPlaceholderText("如：动作 RPG / 视觉小说 / 恐怖解谜…")
        self.world = QPlainTextEdit(profile.world_setting)
        self.world.setPlaceholderText("例：近未来都市，地下排水管道中的恐怖求生，主角被困其中…")
        self.world.setFixedHeight(100)
        self.tone = QPlainTextEdit(profile.tone_notes)
        self.tone.setPlaceholderText("例：对话口语化、阴郁氛围；主角沉默寡言；NPC 各有口癖…")
        self.tone.setFixedHeight(90)
        self.source = QComboBox()
        for lang in SOURCE_LANGS:
            self.source.addItem("自动检测" if lang == "auto" else lang, lang)
        idx = self.source.findData(profile.source_lang)
        self.source.setCurrentIndex(max(0, idx))
        form.addRow("游戏名称", self.name)
        form.addRow("游戏类型", self.genre)
        form.addRow("世界观设定", self.world)
        form.addRow("文风要求", self.tone)
        form.addRow("源语言", self.source)
        form.addRow("目标语言", QLabel("简体中文（zh-CN）"))
        lay.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setProperty("primary", True)
        save.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        lay.addLayout(btn_row)

    def result_profile(self) -> GameProfile:
        return GameProfile(
            game_name=self.name.text().strip(),
            genre=self.genre.text().strip(),
            world_setting=self.world.toPlainText().strip(),
            tone_notes=self.tone.toPlainText().strip(),
            source_lang=self.source.currentData(),
            target_lang="zh-CN",
        )
