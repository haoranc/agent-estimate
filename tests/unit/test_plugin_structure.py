"""Structural validation tests for plugin and skill layout."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


class TestPluginManifest:
    """Tests for .claude-plugin/plugin.json."""

    plugin_json = ROOT / ".claude-plugin" / "plugin.json"

    def test_plugin_json_exists(self):
        assert self.plugin_json.exists(), ".claude-plugin/plugin.json must exist"

    def test_plugin_json_is_valid_json(self):
        data = json.loads(self.plugin_json.read_text())
        assert isinstance(data, dict)

    def test_plugin_json_has_required_fields(self):
        data = json.loads(self.plugin_json.read_text())
        assert "name" in data, "plugin.json must have 'name'"
        assert "description" in data, "plugin.json must have 'description'"
        assert "version" in data, "plugin.json must have 'version'"

    def test_plugin_json_name_matches(self):
        data = json.loads(self.plugin_json.read_text())
        assert data["name"] == "agent-estimate"

    def test_plugin_version_matches_package(self):
        from agent_estimate.version import __version__

        data = json.loads(self.plugin_json.read_text())
        assert data["version"] == __version__, (
            f"plugin.json version ({data['version']}) must match "
            f"version.py ({__version__})"
        )


class TestSkillLocation:
    """Tests for skills/estimate/SKILL.md placement."""

    skill_md = ROOT / "skills" / "estimate" / "SKILL.md"
    old_skill_md = ROOT / "src" / "agent_estimate" / "skill" / "SKILL.md"

    def test_skill_md_exists(self):
        assert self.skill_md.exists(), "skills/estimate/SKILL.md must exist"

    def test_skill_md_has_yaml_frontmatter(self):
        content = self.skill_md.read_text()
        assert content.startswith("---"), "SKILL.md must start with YAML frontmatter"
        # Find the closing ---
        second_fence = content.index("---", 3)
        frontmatter = content[3:second_fence].strip()
        assert "name:" in frontmatter, "frontmatter must contain 'name:'"
        assert "description:" in frontmatter, "frontmatter must contain 'description:'"

    def test_skill_frontmatter_name_is_estimate(self):
        content = self.skill_md.read_text()
        second_fence = content.index("---", 3)
        frontmatter = content[3:second_fence].strip()
        for line in frontmatter.splitlines():
            if line.startswith("name:"):
                value = line.split(":", 1)[1].strip()
                assert value == "estimate", f"skill name must be 'estimate', got '{value}'"
                return
        pytest.fail("'name:' not found in frontmatter")

    def test_old_skill_md_removed(self):
        assert not self.old_skill_md.exists(), (
            "src/agent_estimate/skill/SKILL.md must be removed — "
            "canonical location is skills/estimate/SKILL.md"
        )


class TestCodexSkillMirror:
    """Tests for Codex-compatible .agent skill."""

    canonical_skill_md = ROOT / "skills" / "estimate" / "SKILL.md"
    codex_skill_md = ROOT / ".agent" / "skills" / "estimate" / "SKILL.md"

    def test_codex_skill_mirror_exists(self):
        assert self.codex_skill_md.exists(), ".agent/skills/estimate/SKILL.md must exist"

    def test_codex_skill_mirror_has_yaml_frontmatter(self):
        content = self.codex_skill_md.read_text()
        assert content.startswith("---"), "Codex SKILL.md must start with YAML frontmatter"
        second_fence = content.index("---", 3)
        frontmatter = content[3:second_fence].strip()
        assert "name:" in frontmatter, "frontmatter must contain 'name:'"
        assert "description:" in frontmatter, "frontmatter must contain 'description:'"

    def test_codex_skill_frontmatter_name_is_estimate(self):
        content = self.codex_skill_md.read_text()
        second_fence = content.index("---", 3)
        frontmatter = content[3:second_fence].strip()
        for line in frontmatter.splitlines():
            if line.startswith("name:"):
                value = line.split(":", 1)[1].strip()
                assert value == "estimate", f"codex skill name must be 'estimate', got '{value}'"
                return
        pytest.fail("'name:' not found in codex frontmatter")

    def test_codex_skill_includes_core_cli_commands(self):
        content = self.codex_skill_md.read_text()
        assert "agent-estimate estimate" in content
        assert "agent-estimate validate" in content
        assert "agent-estimate calibrate" in content

    def test_codex_skill_documents_json_as_supported(self):
        content = self.codex_skill_md.read_text()
        assert "--format json" in content
        assert "NOT YET IMPLEMENTED" not in content

    def test_codex_and_canonical_skills_share_skill_name(self):
        canonical = self.canonical_skill_md.read_text()
        codex = self.codex_skill_md.read_text()
        assert "name: estimate" in canonical
        assert "name: estimate" in codex
