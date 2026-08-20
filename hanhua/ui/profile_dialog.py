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

        hint = QLabel("档案只属于当前游戏项目，保存后注入翻译提示词——下次翻译开始时生效。")
        hint.setProperty("class", "subtitle")
        lay.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(12)
        self.name = QLineEdit(profile.game_name)
        self.name.setPlaceholderText("如：Rendezvous")
        self.genre = QLineEdit(profile.genre)
        self.genre.setPlaceholderText("如：动作 RPG / 视觉小说 / 恐怖解谜…")
        self.world = QPlainTextEdit(profile.world_setting)
        self.world.setPlaceholderText("例：近未来都市，地下排水管道中的恐怖求生，主角被困其中…\n注入提示词的【世界观设定】，帮助模型理解语境。")
        self.world.setFixedHeight(100)
        self.tone = QPlainTextEdit(profile.tone_notes)
        self.tone.setPlaceholderText("例：对话口语化、阴郁氛围；主角沉默寡言；NPC 各有口癖…\n注入提示词的【文风要求】。")
        self.tone.setFixedHeight(90)
        # #10：Style/Personalization——自定义翻译风格提示词（按游戏档案
        # 编辑；非空时以【个性化风格要求】块注入翻译提示词并优先生效）
        self.style = QPlainTextEdit(profile.prompt_style)
        self.style.setPlaceholderText(
            "例：本游戏术语统一音译；\"play/resume\" 等按键词必须译成"
            "「开始/继续」；禁止出现网络用语；技能名保持两字格式…\n"
            "注入提示词且优先级最高；留空 = 使用内置的游戏本地化专家提示词")
        self.style.setFixedHeight(100)
        self.source = QComboBox()
        for lang in SOURCE_LANGS:
            self.source.addItem("自动检测" if lang == "auto" else lang, lang)
        idx = self.source.findData(profile.source_lang)
        self.source.setCurrentIndex(max(0, idx))
        for control in (self.name, self.genre, self.source):
            control.setMinimumHeight(44)
        form.addRow("游戏名称", self.name)
        form.addRow("游戏类型", self.genre)
        form.addRow("世界观设定", self.world)
        form.addRow("文风要求", self.tone)
        form.addRow("翻译风格要求", self.style)
        form.addRow("源语言", self.source)
        form.addRow("目标语言", QLabel("简体中文（zh-CN）"))
        lay.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setMinimumHeight(44)
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setProperty("primary", True)
        save.setMinimumHeight(44)
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
            prompt_style=self.style.toPlainText().strip(),
            source_lang=self.source.currentData(),
            target_lang="zh-CN",
        )
