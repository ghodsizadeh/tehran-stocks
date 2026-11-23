"""Tests for bundled Agent Skills (SKILL.md compliance) and ``tse skill`` CLI."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from typer.testing import CliRunner

from tehran_stocks.cli import app
from tehran_stocks.cli import skills_cmd
from tehran_stocks.cli.skills_cmd import (
    SkillScope,
    SkillTarget,
    discover_skills,
    parse_skill_frontmatter,
    resolve_install_targets,
    resolve_skills_root,
    validate_skill_frontmatter,
)
from tehran_stocks.exceptions import TehranStocksError

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

runner = CliRunner()


def test_repo_skills_exist_and_conform_to_agentskills_spec() -> None:
    setup_md = SKILLS_DIR / "tehran-stocks-setup" / "SKILL.md"
    analysis_md = SKILLS_DIR / "tehran-stocks-analysis" / "SKILL.md"
    api_ref_md = (
        SKILLS_DIR / "tehran-stocks-analysis" / "references" / "api-reference.md"
    )
    glossary_md = (
        SKILLS_DIR / "tehran-stocks-analysis" / "references" / "tse-domain-glossary.md"
    )

    for path in (setup_md, analysis_md, api_ref_md, glossary_md):
        assert path.is_file(), f"Missing expected skill file: {path}"

    for folder_name, skill_file in (
        ("tehran-stocks-setup", setup_md),
        ("tehran-stocks-analysis", analysis_md),
    ):
        text = skill_file.read_text(encoding="utf-8")
        fm = parse_skill_frontmatter(text)
        errors = validate_skill_frontmatter(fm, expected_name=folder_name)
        assert errors == [], f"Frontmatter errors in {skill_file}: {errors}"
        assert fm["name"] == folder_name
        assert fm["license"] == "MIT"
        assert 10 <= len(fm["description"]) <= 1024
        assert 10 <= len(fm["compatibility"]) <= 500
        assert isinstance(fm["metadata"], dict)
        assert fm["metadata"]["author"] == "tehran-stocks"
        assert fm["metadata"]["version"] == "3.0.0"
        assert "github.com/ghodsizadeh/tehran-stocks" in fm["metadata"]["repository"]

    # Ensure documentation references exact v3.0 CLI, SDK, MCP, and Jalali APIs.
    setup_text = setup_md.read_text(encoding="utf-8")
    assert "uvx --from tehran-stocks tse" in setup_text
    assert "tse mcp" in setup_text
    assert "tehran-stocks-mcp" in setup_text
    assert "SQLiteStore" in setup_text
    assert "SQLAlchemyStore" in setup_text
    assert "npx skills add ghodsizadeh/tehran-stocks" in setup_text
    assert "tse skill install" in setup_text

    analysis_text = analysis_md.read_text(encoding="utf-8")
    assert "./references/api-reference.md" in analysis_text
    assert "./references/tse-domain-glossary.md" in analysis_text
    assert "jalali-pandas" in analysis_text
    assert "ts.to_dataframe" in analysis_text
    assert "daily_prices" in analysis_text
    assert "adjusted=True" in analysis_text

    api_ref_text = api_ref_md.read_text(encoding="utf-8")
    for mcp_tool in (
        "search_instruments",
        "get_stock_snapshot",
        "get_price_history",
        "get_client_type_flow",
        "get_order_book",
        "get_fundamentals_and_events",
        "get_market_overview",
        "get_indices",
        "screen_market",
        "get_disclosures",
        "sync_local_db",
        "query_local_db",
    ):
        assert mcp_tool in api_ref_text

    for resource_uri in (
        "tsetmc://market/overview",
        "tsetmc://market/sectors",
        "tsetmc://instrument/{symbol}",
    ):
        assert resource_uri in api_ref_text


def test_frontmatter_parser_and_validator_edge_cases() -> None:
    sample = """---
name: sample-skill
description: >-
  First line of description
  continued cleanly. # kept inside text? Wait: inline comment test
license: "MIT" # trailing comment
compatibility: 'Requires Python 3.11+'
metadata:
  author: "example"
  version: "1.2.3"
---

# Body
"""
    parsed = parse_skill_frontmatter(sample)
    assert parsed["name"] == "sample-skill"
    assert "First line of description" in parsed["description"]
    assert parsed["license"] == "MIT"
    assert parsed["compatibility"] == "Requires Python 3.11+"
    assert parsed["metadata"] == {"author": "example", "version": "1.2.3"}
    assert validate_skill_frontmatter(parsed, expected_name="sample-skill") == []

    # Invalid cases
    with pytest.raises(ValueError):
        parse_skill_frontmatter("# No frontmatter")

    bad_errors = validate_skill_frontmatter(
        {
            "name": "Bad_Name-",
            "description": "x" * 1025,
            "compatibility": "y" * 501,
            "metadata": {"version": 123},
        },
        expected_name="other-folder",
    )
    assert len(bad_errors) >= 5


def test_skill_discovery_zero_side_effects_and_package_bundle_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Importing skills_cmd creates no files in HOME or CWD
    src_dir = REPO_ROOT / "src"
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from tehran_stocks.cli import app, skills_cmd; assert skills_cmd.skill_app is not None",
        ],
        cwd=tmp_path,
        env={**os.environ, "HOME": str(tmp_path), "PYTHONPATH": str(src_dir)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout == ""
    assert proc.stderr == ""
    assert list(tmp_path.iterdir()) == []

    # Editable repository fallback
    root, source, skills = discover_skills()
    assert source == "repository"
    assert Path(str(root)).resolve() == SKILLS_DIR.resolve()
    assert [s.name for s in skills] == [
        "tehran-stocks-analysis",
        "tehran-stocks-setup",
    ]

    # Simulated wheel bundle (tehran_stocks/_skills via importlib.resources.files)
    pkg_dir = tmp_path / "site_pkg"
    bundled_root = pkg_dir / "_skills"
    (bundled_root / "tehran-stocks-setup").mkdir(parents=True)
    (bundled_root / "tehran-stocks-setup" / "SKILL.md").write_text(
        (SKILLS_DIR / "tehran-stocks-setup" / "SKILL.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    monkeypatch.setattr(skills_cmd.resources, "files", lambda pkg: pkg_dir)
    pkg_root, pkg_source = resolve_skills_root()
    assert pkg_source == "package"
    assert Path(str(pkg_root)) == bundled_root

    # If neither exists, raise TehranStocksError
    empty_pkg = tmp_path / "empty_pkg"
    empty_pkg.mkdir()
    monkeypatch.setattr(skills_cmd.resources, "files", lambda pkg: empty_pkg)
    monkeypatch.setattr(
        skills_cmd,
        "__file__",
        str(tmp_path / "a" / "b" / "c" / "d" / "skills_cmd.py"),
    )
    with pytest.raises(TehranStocksError):
        resolve_skills_root()


def test_cli_skill_list_and_path_outputs(tmp_path: Path) -> None:
    # tse skill list (table, --json, --format csv)
    list_tbl = runner.invoke(app, ["skill", "list"])
    assert list_tbl.exit_code == 0
    assert "tehran-stocks-setup" in list_tbl.stdout
    assert "tehran-stocks-analysis" in list_tbl.stdout

    list_json = runner.invoke(app, ["skill", "list", "--json"])
    assert list_json.exit_code == 0
    items = json.loads(list_json.stdout)
    assert [item["name"] for item in items] == [
        "tehran-stocks-analysis",
        "tehran-stocks-setup",
    ]
    assert items[0]["has_references"] is True
    assert "references/api-reference.md" in items[0]["files"]
    assert items[1]["has_references"] is False

    list_csv = runner.invoke(app, ["skill", "list", "--format", "csv"])
    assert list_csv.exit_code == 0
    csv_rows = list(csv.DictReader(io.StringIO(list_csv.stdout)))
    assert len(csv_rows) == 2
    assert csv_rows[0]["version"] == "3.0.0"

    # tse skill path (plain, --json, single skill, unknown skill error)
    path_plain = runner.invoke(app, ["skill", "path"])
    assert path_plain.exit_code == 0
    assert Path(path_plain.stdout.strip()).resolve() == SKILLS_DIR.resolve()

    path_json = runner.invoke(app, ["skill", "path", "--json"])
    assert path_json.exit_code == 0
    path_data = json.loads(path_json.stdout)
    assert Path(path_data["path"]).resolve() == SKILLS_DIR.resolve()
    assert path_data["source"] == "repository"
    assert path_data["skills"] == [
        "tehran-stocks-analysis",
        "tehran-stocks-setup",
    ]

    one_path = runner.invoke(app, ["skill", "path", "tehran-stocks-analysis"])
    assert one_path.exit_code == 0
    assert (
        Path(one_path.stdout.strip()).resolve()
        == (SKILLS_DIR / "tehran-stocks-analysis").resolve()
    )

    bad_path = runner.invoke(app, ["skill", "path", "nonexistent-skill"])
    assert bad_path.exit_code == 1
    assert bad_path.stdout == ""
    assert "TehranStocksError:" in bad_path.stderr

    # Verify list/path wrote nothing into temp CWD
    assert list(tmp_path.iterdir()) == []


def test_cli_skill_install_targets_and_scopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    monkeypatch.chdir(project_dir)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # 1. --target agents --scope project -> <project>/.agents/skills/
    res_agents = runner.invoke(
        app,
        ["skill", "install", "--target", "agents", "--scope", "project", "--json"],
    )
    assert res_agents.exit_code == 0
    installed_agents = json.loads(res_agents.stdout)
    assert len(installed_agents) == 2
    assert (
        project_dir / ".agents" / "skills" / "tehran-stocks-setup" / "SKILL.md"
    ).is_file()
    assert (
        project_dir
        / ".agents"
        / "skills"
        / "tehran-stocks-analysis"
        / "references"
        / "api-reference.md"
    ).is_file()
    assert (
        project_dir
        / ".agents"
        / "skills"
        / "tehran-stocks-analysis"
        / "references"
        / "tse-domain-glossary.md"
    ).is_file()

    # 2. --target claude --scope project -> <project>/.claude/skills/
    res_claude = runner.invoke(
        app,
        [
            "skill",
            "install",
            "--target",
            "claude",
            "--scope",
            "project",
            "--skill",
            "tehran-stocks-setup",
            "--json",
        ],
    )
    assert res_claude.exit_code == 0
    installed_claude = json.loads(res_claude.stdout)
    assert len(installed_claude) == 1
    assert installed_claude[0]["skill"] == "tehran-stocks-setup"
    assert (
        project_dir / ".claude" / "skills" / "tehran-stocks-setup" / "SKILL.md"
    ).is_file()
    assert not (
        project_dir / ".claude" / "skills" / "tehran-stocks-analysis"
    ).exists()

    # 3. --target auto --scope project in a clean repo falls back to .agents/skills
    clean_proj = tmp_path / "clean_proj"
    clean_proj.mkdir()
    monkeypatch.chdir(clean_proj)
    res_auto_fallback = runner.invoke(
        app,
        ["skill", "install", "--target", "auto", "--scope", "project"],
    )
    assert res_auto_fallback.exit_code == 0
    assert (
        clean_proj / ".agents" / "skills" / "tehran-stocks-setup" / "SKILL.md"
    ).is_file()

    # 4. --target auto --scope project with .cursor + .codex markers installs to both
    multi_proj = tmp_path / "multi_proj"
    (multi_proj / ".cursor").mkdir(parents=True)
    (multi_proj / ".codex").mkdir(parents=True)
    monkeypatch.chdir(multi_proj)
    res_auto_multi = runner.invoke(
        app,
        ["skill", "install", "--target", "auto", "--scope", "project", "--json"],
    )
    assert res_auto_multi.exit_code == 0
    multi_rows = json.loads(res_auto_multi.stdout)
    assert {r["target"] for r in multi_rows} == {"cursor", "codex"}
    assert (
        multi_proj / ".cursor" / "skills" / "tehran-stocks-analysis" / "SKILL.md"
    ).is_file()
    assert (
        multi_proj / ".codex" / "skills" / "tehran-stocks-setup" / "SKILL.md"
    ).is_file()

    # 5. Global scope (--target auto fallback, --target claude, --target antigravity, --target auto detection)
    assert resolve_install_targets(SkillTarget.AUTO, SkillScope.GLOBAL) == [
        ("agents", fake_home / ".agents" / "skills")
    ]

    res_global_claude = runner.invoke(
        app,
        ["skill", "install", "--target", "claude", "--scope", "global", "--json"],
    )
    assert res_global_claude.exit_code == 0
    assert (
        fake_home / ".claude" / "skills" / "tehran-stocks-setup" / "SKILL.md"
    ).is_file()

    res_global_agy = runner.invoke(
        app,
        ["skill", "install", "--target", "antigravity", "--scope", "global"],
    )
    assert res_global_agy.exit_code == 0
    assert (
        fake_home
        / ".gemini"
        / "config"
        / "skills"
        / "tehran-stocks-analysis"
        / "SKILL.md"
    ).is_file()

    # Auto global detection picks up existing ~/.claude and ~/.gemini/config
    auto_global = resolve_install_targets(SkillTarget.AUTO, SkillScope.GLOBAL)
    assert ("claude", fake_home / ".claude" / "skills") in auto_global
    assert ("antigravity", fake_home / ".gemini" / "config" / "skills") in auto_global

    # 6. Existing installs are preserved by default and with --no-overwrite; unknown skill rejects cleanly
    claude_setup_md = fake_home / ".claude" / "skills" / "tehran-stocks-setup" / "SKILL.md"
    claude_setup_md.write_text("LOCAL EDIT", encoding="utf-8")
    default_res = runner.invoke(
        app,
        ["skill", "install", "--target", "claude", "--scope", "global"],
    )
    assert default_res.exit_code == 1
    assert default_res.stdout == ""
    assert "--overwrite" in default_res.stderr
    assert claude_setup_md.read_text(encoding="utf-8") == "LOCAL EDIT"

    no_overwrite_res = runner.invoke(
        app,
        [
            "skill",
            "install",
            "--target",
            "claude",
            "--scope",
            "global",
            "--no-overwrite",
        ],
    )
    assert no_overwrite_res.exit_code == 1
    assert no_overwrite_res.stdout == ""
    assert "TehranStocksError:" in no_overwrite_res.stderr
    assert claude_setup_md.read_text(encoding="utf-8") == "LOCAL EDIT"

    bad_skill_res = runner.invoke(
        app,
        ["skill", "install", "--skill", "missing-skill"],
    )
    assert bad_skill_res.exit_code == 1
    assert bad_skill_res.stdout == ""
    assert "TehranStocksError:" in bad_skill_res.stderr

    # 7. Valid and broken symlinks (e.g. from npx skills) are detected and replaced safely
    symlink_proj = tmp_path / "symlink_proj"
    skills_target = symlink_proj / ".agents" / "skills"
    skills_target.mkdir(parents=True)

    real_target = tmp_path / "external_skill"
    real_target.mkdir()
    (real_target / "SKILL.md").write_text(
        "---\nname: old\ndescription: old\n---\n",
        encoding="utf-8",
    )

    valid_link = skills_target / "tehran-stocks-setup"
    broken_link = skills_target / "tehran-stocks-analysis"
    valid_link.symlink_to(real_target)
    broken_link.symlink_to(tmp_path / "missing_target")

    monkeypatch.chdir(symlink_proj)
    broken_no_overwrite = runner.invoke(
        app,
        [
            "skill",
            "install",
            "--target",
            "agents",
            "--scope",
            "project",
            "--skill",
            "tehran-stocks-analysis",
            "--no-overwrite",
        ],
    )
    assert broken_no_overwrite.exit_code == 1
    assert "TehranStocksError:" in broken_no_overwrite.stderr

    # Default (no flag) preserves both valid and broken symlinks untouched.
    res_default = runner.invoke(
        app,
        ["skill", "install", "--target", "agents", "--scope", "project", "--json"],
    )
    assert res_default.exit_code == 1
    assert res_default.stdout == ""
    assert "--overwrite" in res_default.stderr
    assert valid_link.is_symlink() and valid_link.resolve() == real_target.resolve()
    assert broken_link.is_symlink() and not broken_link.exists()
    assert sorted(p.name for p in skills_target.iterdir()) == [
        "tehran-stocks-analysis",
        "tehran-stocks-setup",
    ]

    res_symlink = runner.invoke(
        app,
        [
            "skill",
            "install",
            "--target",
            "agents",
            "--scope",
            "project",
            "--overwrite",
            "--json",
        ],
    )
    assert res_symlink.exit_code == 0
    assert not valid_link.is_symlink() and (valid_link / "SKILL.md").is_file()
    assert not broken_link.is_symlink() and (broken_link / "SKILL.md").is_file()
    assert (real_target / "SKILL.md").read_text(encoding="utf-8") == (
        "---\nname: old\ndescription: old\n---\n"
    )
    # No staging/backup leftovers inside the skills directory.
    assert sorted(p.name for p in skills_target.iterdir()) == [
        "tehran-stocks-analysis",
        "tehran-stocks-setup",
    ]


def _write_marker_skill(path: Path, marker: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(marker, encoding="utf-8")


def _install_args(base: Path, *extra: str) -> list[str]:
    return [
        "skill",
        "install",
        "--target",
        "agents",
        "--scope",
        "project",
        "--dir",
        str(base),
        *extra,
    ]


ALL_SKILL_NAMES = ["tehran-stocks-analysis", "tehran-stocks-setup"]


def test_cli_skill_install_default_preservation(tmp_path: Path) -> None:
    base = tmp_path / "base"
    skills_dir = base / ".agents" / "skills"

    first = runner.invoke(app, _install_args(base, "--json"))
    assert first.exit_code == 0
    assert len(json.loads(first.stdout)) == 2

    setup_md = skills_dir / "tehran-stocks-setup" / "SKILL.md"
    setup_md.write_text("LOCAL EDIT", encoding="utf-8")

    again = runner.invoke(app, _install_args(base))
    assert again.exit_code == 1
    assert again.stdout == ""
    assert "TehranStocksError:" in again.stderr
    assert "--overwrite" in again.stderr
    assert setup_md.read_text(encoding="utf-8") == "LOCAL EDIT"

    forced = runner.invoke(app, _install_args(base, "--overwrite", "--json"))
    assert forced.exit_code == 0
    assert {row["skill"] for row in json.loads(forced.stdout)} == set(ALL_SKILL_NAMES)
    assert setup_md.read_text(encoding="utf-8").startswith("---\nname: tehran-stocks-setup")
    assert sorted(p.name for p in skills_dir.iterdir()) == ALL_SKILL_NAMES


def test_cli_skill_install_multi_skill_preflight_is_atomic(tmp_path: Path) -> None:
    # Only skill 2 (setup) exists: skill 1 (analysis) must NOT be installed either.
    base = tmp_path / "base"
    skills_dir = base / ".agents" / "skills"
    _write_marker_skill(skills_dir / "tehran-stocks-setup", "EXISTING SETUP")

    res = runner.invoke(app, _install_args(base))
    assert res.exit_code == 1
    assert res.stdout == ""
    assert "TehranStocksError:" in res.stderr
    assert not (skills_dir / "tehran-stocks-analysis").exists()
    assert (skills_dir / "tehran-stocks-setup" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "EXISTING SETUP"
    assert sorted(p.name for p in skills_dir.iterdir()) == ["tehran-stocks-setup"]

    # Both exist: neither is touched.
    _write_marker_skill(skills_dir / "tehran-stocks-analysis", "EXISTING ANALYSIS")
    res_both = runner.invoke(app, _install_args(base, "--no-overwrite"))
    assert res_both.exit_code == 1
    assert (skills_dir / "tehran-stocks-analysis" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "EXISTING ANALYSIS"
    assert (skills_dir / "tehran-stocks-setup" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "EXISTING SETUP"

    # Explicit --skill list is preflighted as a whole too.
    other_base = tmp_path / "other"
    _write_marker_skill(other_base / ".agents" / "skills" / "tehran-stocks-setup", "X")
    fresh_target_res = runner.invoke(
        app,
        _install_args(other_base, "--skill", "tehran-stocks-analysis,tehran-stocks-setup"),
    )
    assert fresh_target_res.exit_code == 1
    assert not (other_base / ".agents" / "skills" / "tehran-stocks-analysis").exists()


def test_cli_skill_install_failed_copy_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "base"
    skills_dir = base / ".agents" / "skills"
    _write_marker_skill(skills_dir / "tehran-stocks-analysis", "OLD ANALYSIS")
    _write_marker_skill(skills_dir / "tehran-stocks-setup", "OLD SETUP")

    original_copy = skills_cmd._copy_traversable_dir

    def failing_copy(src_dir: Any, dst_dir: Path) -> int:
        if dst_dir.name == "tehran-stocks-setup":
            raise OSError("simulated disk full")
        return original_copy(src_dir, dst_dir)

    monkeypatch.setattr(skills_cmd, "_copy_traversable_dir", failing_copy)

    res = runner.invoke(app, _install_args(base, "--overwrite"))
    assert res.exit_code == 1
    assert res.stdout == ""
    assert "TehranStocksError:" in res.stderr
    assert "simulated" in res.stderr
    assert (skills_dir / "tehran-stocks-analysis" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "OLD ANALYSIS"
    assert (skills_dir / "tehran-stocks-setup" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "OLD SETUP"
    assert sorted(p.name for p in skills_dir.iterdir()) == ALL_SKILL_NAMES

    # Failed copy into a brand-new destination leaves no partial skill or empty dirs behind.
    fresh = tmp_path / "fresh"
    fresh_res = runner.invoke(app, _install_args(fresh))
    assert fresh_res.exit_code == 1
    assert not (fresh / ".agents").exists()


def test_cli_skill_install_failed_swap_restores_previous_installs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "base"
    skills_dir = base / ".agents" / "skills"
    skills_dir.mkdir(parents=True)

    external = tmp_path / "external_analysis"
    _write_marker_skill(external, "EXTERNAL ANALYSIS")
    analysis_link = skills_dir / "tehran-stocks-analysis"
    analysis_link.symlink_to(external, target_is_directory=True)
    _write_marker_skill(skills_dir / "tehran-stocks-setup", "OLD SETUP")

    original_swap = skills_cmd._swap_in_staged

    def failing_swap(staged: Path, skill_dest: Path, backup: Path) -> None:
        if skill_dest.name == "tehran-stocks-setup":
            raise OSError("simulated rename failure")
        original_swap(staged, skill_dest, backup)

    monkeypatch.setattr(skills_cmd, "_swap_in_staged", failing_swap)

    res = runner.invoke(app, _install_args(base, "--overwrite"))
    assert res.exit_code == 1
    assert res.stdout == ""
    assert "TehranStocksError:" in res.stderr

    # Skill 1 had already been swapped in; it must be rolled back to the original symlink.
    assert analysis_link.is_symlink()
    assert analysis_link.resolve() == external.resolve()
    assert (external / "SKILL.md").read_text(encoding="utf-8") == "EXTERNAL ANALYSIS"
    assert (skills_dir / "tehran-stocks-setup" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "OLD SETUP"
    assert sorted(p.name for p in skills_dir.iterdir()) == ALL_SKILL_NAMES
