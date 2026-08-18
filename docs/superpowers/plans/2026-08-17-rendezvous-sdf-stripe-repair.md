# Rendezvous SDF 条纹修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align generated TMP SDF material sampling parameters with the 4096² atlas and deploy the corrected Unity 2019 bundle.

**Architecture:** Bundle generation normalizes Material `_TextureWidth`, `_TextureHeight`, and `_GradientScale` alongside the font and atlas payload. A regression test reads the generated bundle and asserts the sampling contract.

**Tech Stack:** Python, UnityPy, pytest, PowerShell.

---

### Task 1: Normalize generated SDF material

- [x] Update `scripts/build_tmp_font_bundles.py` to write 4096/4096/10 material values.
- [ ] Rebuild the medium Unity 2019 bundle.
- [ ] Verify bundle metadata and deploy it to the game plugin directory.

### Task 2: Regression verification

- [ ] Run focused TMP/font tests and record output.
- [ ] Review changed files and update running issues.
