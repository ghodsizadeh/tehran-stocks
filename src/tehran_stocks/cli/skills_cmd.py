"""Bundled Agent Skills discovery and installation commands (``tse skill``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from importlib import resources
from importlib.resources.abc import Traversable
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Annotated, Any

import typer

from tehran_stocks.cli.formatters import (
    ColumnSpec,
    OutputFormat,
    cli_error_boundary,
    emit_csv,
    emit_json,
    fmt_int,
    fmt_text,
    output_records,
    resolve_output_format,
)
from tehran_stocks.exceptions import TehranStocksError

_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_IGNORED_NAMES = frozenset({"__pycache__", ".DS_Store"})

FormatOption = Annotated[
    OutputFormat,
    typer.Option(
        "--format",
        "-f",
        case_sensitive=False,
        help="Output format: table, json, or csv.",
    ),
]
JsonOption = Annotated[
    bool,
    typer.Option(
        "--json",
        help="Emit JSON output (shorthand for --format json).",
    ),
]


class SkillTarget(str, Enum):
    """Supported agent harness targets for ``tse skill install``."""

    AUTO = "auto"
    CLAUDE = "claude"
    CURSOR = "cursor"
    CODEX = "codex"
    ANTIGRAVITY = "antigravity"
    AGENTS = "agents"


class SkillScope(str, Enum):
    """Supported installation scopes for ``tse skill install``."""

    PROJECT = "project"
    GLOBAL = "global"


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """Parsed metadata and file inventory for a bundled Agent Skill."""

    name: str
    description: str
    license: str = ""
    compatibility: str = ""
    metadata: dict[str, str] | None = None
    dir_name: str = ""
    path: str = ""
    has_references: bool = False
    files: tuple[str, ...] = ()
    entry: Traversable | None = None

    @property
    def version(self) -> str:
        if not self.metadata:
            return ""
        return str(self.metadata.get("version", ""))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "license": self.license,
            "compatibility": self.compatibility,
            "version": self.version,
            "metadata": dict(self.metadata) if self.metadata else {},
            "dir_name": self.dir_name,
            "path": self.path,
            "has_references": self.has_references,
            "files": list(self.files),
        }


def _strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for idx, ch in enumerate(value):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_double:
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if idx == 0 or value[idx - 1].isspace():
                return value[:idx].rstrip()
    return value.strip()


def _unquote_yaml_scalar(raw: str) -> str:
    cleaned = _strip_inline_comment(raw.strip())
    if len(cleaned) >= 2 and cleaned[0] == '"' and cleaned[-1] == '"':
        inner = cleaned[1:-1]
        return (
            inner.replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\\\", "\\")
        )
    if len(cleaned) >= 2 and cleaned[0] == "'" and cleaned[-1] == "'":
        return cleaned[1:-1].replace("''", "'")
    return cleaned


def _collect_indented_block(
    lines: list[str],
    start: int,
    base_indent: int,
) -> tuple[list[str], int]:
    collected: list[str] = []
    idx = start
    while idx < len(lines):
        line = lines[idx]
        if not line.strip():
            collected.append("")
            idx += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= base_indent:
            break
        collected.append(line)
        idx += 1
    return collected, idx


def _parse_block_scalar(block_lines: list[str], indicator: str) -> str:
    non_empty = [line for line in block_lines if line.strip()]
    if not non_empty:
        return ""
    min_indent = min(len(line) - len(line.lstrip(" ")) for line in non_empty)
    stripped = [line[min_indent:] if len(line) >= min_indent else "" for line in block_lines]
    while stripped and not stripped[-1]:
        stripped.pop()

    if indicator.startswith(">"):
        paragraphs: list[str] = []
        current: list[str] = []
        for line in stripped:
            if not line:
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
                else:
                    paragraphs.append("")
            else:
                current.append(line.strip())
        if current:
            paragraphs.append(" ".join(current))
        text = "\n".join(paragraphs)
    else:
        text = "\n".join(stripped)

    if indicator.endswith("-"):
        return text.rstrip("\n")
    return text + "\n" if text else ""


def _parse_yaml_mapping(raw_yaml: str) -> dict[str, Any]:
    """Parse a clean YAML frontmatter mapping without external dependencies."""
    lines = raw_yaml.splitlines()
    data: dict[str, Any] = {}
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            idx += 1
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent != 0 or ":" not in stripped:
            raise ValueError(f"Unsupported YAML frontmatter line: {line!r}")

        key_part, _, rest_part = stripped.partition(":")
        key = key_part.strip()
        rest = rest_part.strip()
        idx += 1

        if rest in (">", ">-", "|", "|-"):
            block_lines, idx = _collect_indented_block(lines, idx, indent)
            data[key] = _parse_block_scalar(block_lines, rest)
            continue

        if rest == "":
            nested_lines, idx = _collect_indented_block(lines, idx, indent)
            non_empty = [
                nl for nl in nested_lines if nl.strip() and not nl.lstrip().startswith("#")
            ]
            if not non_empty:
                data[key] = {}
                continue

            if non_empty[0].lstrip().startswith("- "):
                items: list[str] = []
                for nl in non_empty:
                    content = nl.lstrip()
                    if not content.startswith("- "):
                        raise ValueError(f"Invalid YAML list item under {key!r}: {nl!r}")
                    items.append(_unquote_yaml_scalar(content[2:]))
                data[key] = items
            else:
                mapping: dict[str, str] = {}
                for nl in non_empty:
                    sub = nl.strip()
                    if ":" not in sub:
                        raise ValueError(f"Invalid YAML nested entry under {key!r}: {nl!r}")
                    sub_key, _, sub_val = sub.partition(":")
                    mapping[sub_key.strip()] = _unquote_yaml_scalar(sub_val)
                data[key] = mapping
            continue

        data[key] = _unquote_yaml_scalar(rest)

    return data


def parse_skill_frontmatter(text: str) -> dict[str, Any]:
    """Extract and parse the YAML frontmatter block from a ``SKILL.md`` file."""
    normalized = text.lstrip("\ufeff").replace("\r\n", "\n")
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", normalized, flags=re.DOTALL)
    if match is None:
        raise ValueError("Missing YAML frontmatter block delimited by '---'.")
    return _parse_yaml_mapping(match.group(1))


def validate_skill_frontmatter(
    frontmatter: Mapping[str, Any],
    *,
    expected_name: str | None = None,
) -> list[str]:
    """Validate parsed ``SKILL.md`` frontmatter against ``agentskills.io`` constraints."""
    errors: list[str] = []

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("Missing required 'name' field.")
    else:
        if len(name) > 64:
            errors.append(f"Skill name {name!r} exceeds 64 characters.")
        if _NAME_PATTERN.match(name) is None:
            errors.append(
                f"Skill name {name!r} must use lowercase letters, numbers, and hyphens only."
            )
        if expected_name is not None and name != expected_name:
            errors.append(
                f"Skill name {name!r} does not match parent folder {expected_name!r}."
            )

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("Missing required non-empty 'description' field.")
    elif len(description) > 1024:
        errors.append(
            f"Skill description exceeds 1024 characters ({len(description)} chars)."
        )

    compatibility = frontmatter.get("compatibility")
    if compatibility is not None:
        if not isinstance(compatibility, str):
            errors.append("'compatibility' must be a string.")
        elif len(compatibility) > 500:
            errors.append(
                f"'compatibility' exceeds 500 characters ({len(compatibility)} chars)."
            )

    license_val = frontmatter.get("license")
    if license_val is not None and not isinstance(license_val, str):
        errors.append("'license' must be a string.")

    metadata = frontmatter.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, Mapping):
            errors.append("'metadata' must be a key-value mapping.")
        else:
            for k, v in metadata.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    errors.append(
                        f"'metadata' entries must map strings to strings (got {k!r}: {v!r})."
                    )

    return errors


def _has_skills(root: Traversable) -> bool:
    try:
        if not root.is_dir():
            return False
        return any(
            entry.is_dir() and entry.joinpath("SKILL.md").is_file()
            for entry in root.iterdir()
        )
    except OSError:
        return False


def resolve_skills_root() -> tuple[Traversable, str]:
    """Locate bundled Agent Skills via ``importlib.resources`` with repo fallback."""
    try:
        pkg_root = resources.files("tehran_stocks")
        bundled = pkg_root.joinpath("_skills")
        if _has_skills(bundled):
            return bundled, "package"
    except (ModuleNotFoundError, FileNotFoundError, OSError):
        pass

    repo_skills = Path(__file__).resolve().parents[3] / "skills"
    if _has_skills(repo_skills):
        return repo_skills, "repository"

    raise TehranStocksError(
        "No bundled Agent Skills directory found (expected package '_skills' or repo 'skills/')."
    )


def _collect_relative_files(root: Traversable, prefix: str = "") -> list[str]:
    files: list[str] = []
    entries = sorted(root.iterdir(), key=lambda item: item.name)
    for child in entries:
        if child.name in _IGNORED_NAMES or child.name.endswith(".pyc"):
            continue
        rel = f"{prefix}/{child.name}" if prefix else child.name
        if child.is_dir():
            files.extend(_collect_relative_files(child, rel))
        elif child.is_file():
            files.append(rel)
    return files


def _copy_traversable_dir(src_dir: Traversable, dst_dir: Path) -> int:
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for child in sorted(src_dir.iterdir(), key=lambda item: item.name):
        if child.name in _IGNORED_NAMES or child.name.endswith(".pyc"):
            continue
        target = dst_dir / child.name
        if child.is_dir():
            copied += _copy_traversable_dir(child, target)
        elif child.is_file():
            target.write_bytes(child.read_bytes())
            copied += 1
    return copied


def discover_skills() -> tuple[Traversable, str, list[SkillMetadata]]:
    """Discover and validate all bundled Agent Skills."""
    root, source = resolve_skills_root()
    skills: list[SkillMetadata] = []

    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        skill_file = entry.joinpath("SKILL.md")
        if not skill_file.is_file():
            continue

        raw_text = skill_file.read_text(encoding="utf-8")
        try:
            fm = parse_skill_frontmatter(raw_text)
        except ValueError as exc:
            raise TehranStocksError(f"Invalid SKILL.md in {entry.name!r}: {exc}") from exc

        validation_errors = validate_skill_frontmatter(fm, expected_name=entry.name)
        if validation_errors:
            raise TehranStocksError(
                f"Invalid SKILL.md frontmatter for {entry.name!r}: "
                + "; ".join(validation_errors)
            )

        rel_files = _collect_relative_files(entry)
        raw_meta = fm.get("metadata")
        meta = dict(raw_meta) if isinstance(raw_meta, Mapping) else {}
        has_refs = any(path.startswith("references/") for path in rel_files)

        skills.append(
            SkillMetadata(
                name=str(fm["name"]),
                description=str(fm["description"]).strip(),
                license=str(fm.get("license") or ""),
                compatibility=str(fm.get("compatibility") or "").strip(),
                metadata=meta,
                dir_name=entry.name,
                path=str(entry),
                has_references=has_refs,
                files=tuple(rel_files),
                entry=entry,
            )
        )

    if not skills:
        raise TehranStocksError("No valid Agent Skills found in skills directory.")

    return root, source, skills


def resolve_install_targets(
    target: SkillTarget,
    scope: SkillScope,
    *,
    base_dir: Path | None = None,
) -> list[tuple[str, Path]]:
    """Resolve ``(target_label, skills_dest_dir)`` pairs for ``target`` and ``scope``."""
    base = (
        base_dir.expanduser().resolve()
        if base_dir is not None
        else (Path.cwd() if scope is SkillScope.PROJECT else Path.home())
    )

    explicit_map: dict[tuple[SkillTarget, SkillScope], Path] = {
        (SkillTarget.AGENTS, SkillScope.PROJECT): base / ".agents" / "skills",
        (SkillTarget.AGENTS, SkillScope.GLOBAL): base / ".agents" / "skills",
        (SkillTarget.CLAUDE, SkillScope.PROJECT): base / ".claude" / "skills",
        (SkillTarget.CLAUDE, SkillScope.GLOBAL): base / ".claude" / "skills",
        (SkillTarget.CURSOR, SkillScope.PROJECT): base / ".cursor" / "skills",
        (SkillTarget.CURSOR, SkillScope.GLOBAL): base / ".cursor" / "skills",
        (SkillTarget.CODEX, SkillScope.PROJECT): base / ".codex" / "skills",
        (SkillTarget.CODEX, SkillScope.GLOBAL): base / ".codex" / "skills",
        (SkillTarget.ANTIGRAVITY, SkillScope.PROJECT): base / ".agents" / "skills",
        (SkillTarget.ANTIGRAVITY, SkillScope.GLOBAL): base / ".gemini" / "config" / "skills",
    }

    if target is not SkillTarget.AUTO:
        return [(target.value, explicit_map[(target, scope)])]

    if scope is SkillScope.PROJECT:
        candidates = (
            (base / ".claude", "claude", base / ".claude" / "skills"),
            (base / ".cursor", "cursor", base / ".cursor" / "skills"),
            (base / ".codex", "codex", base / ".codex" / "skills"),
            (base / ".agents", "agents", base / ".agents" / "skills"),
            (base / ".agent", "antigravity", base / ".agent" / "skills"),
        )
    else:
        candidates = (
            (base / ".claude", "claude", base / ".claude" / "skills"),
            (base / ".cursor", "cursor", base / ".cursor" / "skills"),
            (base / ".codex", "codex", base / ".codex" / "skills"),
            (
                base / ".gemini" / "config",
                "antigravity",
                base / ".gemini" / "config" / "skills",
            ),
            (
                base / ".gemini" / "antigravity",
                "antigravity",
                base / ".gemini" / "config" / "skills",
            ),
            (
                base / ".gemini" / "antigravity-cli",
                "antigravity",
                base / ".gemini" / "config" / "skills",
            ),
            (base / ".agents", "agents", base / ".agents" / "skills"),
        )

    detected: list[tuple[str, Path]] = []
    seen_paths: set[Path] = set()
    for marker, label, dest_dir in candidates:
        if marker.exists() and dest_dir not in seen_paths:
            detected.append((label, dest_dir))
            seen_paths.add(dest_dir)

    if detected:
        return detected
    return [("agents", base / ".agents" / "skills")]


def _parse_skill_names(values: Sequence[str] | None) -> list[str] | None:
    if not values:
        return None
    names: list[str] = []
    for raw in values:
        for part in raw.split(","):
            cleaned = part.strip()
            if cleaned:
                names.append(cleaned)
    return names or None


@dataclass(frozen=True, slots=True)
class _InstallPlan:
    """A single ``(destination skills dir, skill)`` pair to install."""

    target_label: str
    skills_dest: Path
    skill: SkillMetadata

    @property
    def skill_dest(self) -> Path:
        return self.skills_dest / self.skill.name


def _path_present(path: Path) -> bool:
    """Return True for existing files/dirs and for valid *or broken* symlinks."""
    return path.is_symlink() or path.exists()


def _remove_path(path: Path) -> None:
    """Remove a file, symlink (never following it), or directory tree."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _ensure_directory(path: Path) -> list[Path]:
    """Create ``path`` (and parents); return the directories that did not exist before."""
    missing: list[Path] = []
    current = path
    while not _path_present(current) and current.parent != current:
        missing.append(current)
        current = current.parent
    path.mkdir(parents=True, exist_ok=True)
    return missing


def _swap_in_staged(staged: Path, skill_dest: Path, backup: Path) -> None:
    """Move an existing ``skill_dest`` aside to ``backup`` and move ``staged`` into place.

    Both moves are same-filesystem renames (staging lives inside the destination skills dir),
    and symlinks are moved as links so their targets are never touched.
    """
    if _path_present(skill_dest):
        os.replace(skill_dest, backup)
    os.replace(staged, skill_dest)


def _restore_original(skill_dest: Path, staged: Path, backup: Path, had_existing: bool) -> None:
    """Undo ``_swap_in_staged`` for one skill, restoring the previous install if it was moved."""
    if had_existing:
        if _path_present(backup):
            if _path_present(skill_dest):
                _remove_path(skill_dest)
            os.replace(backup, skill_dest)
    elif _path_present(skill_dest) and not _path_present(staged):
        _remove_path(skill_dest)


def _install_skills_transactionally(plans: Sequence[_InstallPlan]) -> list[int]:
    """Stage every skill copy first, then swap all into place; roll back everything on failure.

    1. Copy each skill into a private staging dir created inside its destination skills dir.
       A failed copy aborts before any existing install is touched.
    2. Swap each staged copy into place, moving any previous install into the staging dir as
       a backup. If any swap fails, every completed swap is reverted from its backup.
    3. Remove staging dirs (and backups) only after success or a complete rollback.
    """
    created_dirs: list[Path] = []
    tmp_roots: list[Path] = []
    keep_roots: list[Path] = []
    counts: list[int] = []
    try:
        staged_entries: list[tuple[_InstallPlan, Path, Path, Path]] = []
        for plan in plans:
            assert plan.skill.entry is not None
            created_dirs.extend(_ensure_directory(plan.skills_dest))
            tmp_root = Path(
                tempfile.mkdtemp(prefix=f".{plan.skill.name}.staging-", dir=plan.skills_dest)
            )
            tmp_roots.append(tmp_root)
            staged = tmp_root / plan.skill.name
            counts.append(_copy_traversable_dir(plan.skill.entry, staged))
            staged_entries.append((plan, staged, tmp_root / f"{plan.skill.name}.backup", tmp_root))

        attempted: list[tuple[Path, Path, Path, Path, bool]] = []
        try:
            for plan, staged, backup, tmp_root in staged_entries:
                attempted.append(
                    (plan.skill_dest, staged, backup, tmp_root, _path_present(plan.skill_dest))
                )
                _swap_in_staged(staged, plan.skill_dest, backup)
        except BaseException:
            for skill_dest, staged, backup, tmp_root, had_existing in reversed(attempted):
                try:
                    _restore_original(skill_dest, staged, backup, had_existing)
                except OSError:
                    keep_roots.append(tmp_root)
            raise
    except BaseException as exc:
        for tmp_root in tmp_roots:
            if tmp_root not in keep_roots:
                shutil.rmtree(tmp_root, ignore_errors=True)
        for created in sorted(set(created_dirs), key=lambda p: len(p.parts), reverse=True):
            try:
                created.rmdir()
            except OSError:
                pass
        if keep_roots:
            preserved = ", ".join(str(p) for p in keep_roots)
            raise TehranStocksError(
                f"Skill installation failed ({exc}) and automatic rollback was incomplete; "
                f"previous installations were preserved in: {preserved}"
            ) from exc
        raise

    for tmp_root in tmp_roots:
        shutil.rmtree(tmp_root, ignore_errors=True)
    return counts


skill_app = typer.Typer(
    name="skill",
    no_args_is_help=True,
    help="Inspect and install bundled tehran-stocks Agent Skills.",
)
app = skill_app


@skill_app.command("list")
def skill_list_cmd(
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """List bundled tehran-stocks Agent Skills and metadata."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    with cli_error_boundary():
        _, source, skills = discover_skills()
    rows = [skill.to_dict() for skill in skills]
    columns = [
        ColumnSpec("name", "Skill", no_wrap=True),
        ColumnSpec("version", "Version", no_wrap=True),
        ColumnSpec("license", "License", no_wrap=True),
        ColumnSpec("has_references", "Refs", justify="center", formatter=fmt_text),
        ColumnSpec("description", "Description"),
    ]
    output_records(
        rows,
        fmt=resolved_fmt,
        columns=columns,
        title=f"Bundled Agent Skills ({source})",
    )


@skill_app.command("path")
def skill_path_cmd(
    name: Annotated[
        str | None,
        typer.Argument(help="Optional skill name to inspect (defaults to skills root)."),
    ] = None,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Print the filesystem/package path to bundled Agent Skills."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    with cli_error_boundary():
        root, source, skills = discover_skills()
        if name is not None:
            cleaned = name.strip()
            match = next((s for s in skills if s.name == cleaned), None)
            if match is None or match.entry is None:
                available = ", ".join(s.name for s in skills)
                raise TehranStocksError(
                    f"Unknown skill {name!r}. Available skills: {available}"
                )
            target_path = str(match.entry)
            selected_names = [match.name]
        else:
            target_path = str(root)
            selected_names = [s.name for s in skills]

    if resolved_fmt is OutputFormat.JSON:
        emit_json({"path": target_path, "source": source, "skills": selected_names})
    elif resolved_fmt is OutputFormat.CSV:
        emit_csv(
            [
                {
                    "path": target_path,
                    "source": source,
                    "skills": ",".join(selected_names),
                }
            ],
            columns=["path", "source", "skills"],
        )
    else:
        sys.stdout.write(f"{target_path}\n")
        sys.stdout.flush()


@skill_app.command("install")
def skill_install_cmd(
    target: Annotated[
        SkillTarget,
        typer.Option(
            "--target",
            "-t",
            case_sensitive=False,
            help="Target agent harness: auto, claude, cursor, codex, antigravity, or agents.",
        ),
    ] = SkillTarget.AUTO,
    scope: Annotated[
        SkillScope,
        typer.Option(
            "--scope",
            "-s",
            case_sensitive=False,
            help="Installation scope: project or global.",
        ),
    ] = SkillScope.PROJECT,
    skill: Annotated[
        list[str] | None,
        typer.Option(
            "--skill",
            help="Specific skill name(s) to install (comma-separated or repeated).",
        ),
    ] = None,
    dest_dir: Annotated[
        Path | None,
        typer.Option(
            "--dir",
            help="Base directory override (defaults to CWD for project, HOME for global).",
        ),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite/--no-overwrite",
            help=(
                "Replace existing installed skills (directories or symlinks). "
                "Default: refuse and leave existing installs untouched."
            ),
        ),
    ] = False,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Install bundled Agent Skills into a project or global agent directory.

    Existing skill installs are preserved unless ``--overwrite`` is given. All destinations are
    checked before anything is written, and copies are staged then swapped into place so a
    failed install never leaves a skill missing or half-copied.
    """
    resolved_fmt = resolve_output_format(fmt, as_json)
    requested = _parse_skill_names(skill)

    with cli_error_boundary():
        _, source, all_skills = discover_skills()
        by_name = {item.name: item for item in all_skills}
        if requested is not None:
            missing = [req for req in requested if req not in by_name]
            if missing:
                available = ", ".join(by_name)
                raise TehranStocksError(
                    f"Unknown skill(s): {', '.join(missing)}. Available: {available}"
                )
            selected = [by_name[req] for req in dict.fromkeys(requested)]
        else:
            selected = all_skills

        destinations = resolve_install_targets(target, scope, base_dir=dest_dir)

        # Preflight every (skills_dest, skill) pair before creating or modifying anything.
        plans: list[_InstallPlan] = []
        seen_dests: set[Path] = set()
        for target_label, skills_dest in destinations:
            for item in selected:
                if item.entry is None:
                    continue
                plan = _InstallPlan(target_label=target_label, skills_dest=skills_dest, skill=item)
                if plan.skill_dest in seen_dests:
                    continue
                seen_dests.add(plan.skill_dest)
                plans.append(plan)

        for skills_dest in dict.fromkeys(plan.skills_dest for plan in plans):
            if _path_present(skills_dest) and not skills_dest.is_dir():
                raise TehranStocksError(
                    f"Skills destination is not a directory: {skills_dest}"
                )

        conflicts = [plan.skill_dest for plan in plans if _path_present(plan.skill_dest)]
        if conflicts and not overwrite:
            listed = ", ".join(str(path) for path in conflicts)
            raise TehranStocksError(
                f"Destination already exists: {listed}. Nothing was installed and existing "
                "skills were left unchanged; re-run with --overwrite to replace them."
            )

        try:
            copied_counts = _install_skills_transactionally(plans)
        except OSError as exc:
            raise TehranStocksError(
                f"Failed to install Agent Skills ({exc}). Existing installations were left "
                "unchanged."
            ) from exc

        installed_rows: list[dict[str, Any]] = [
            {
                "skill": plan.skill.name,
                "target": plan.target_label,
                "scope": scope.value,
                "path": str(plan.skill_dest),
                "files": copied_count,
                "source": source,
            }
            for plan, copied_count in zip(plans, copied_counts, strict=True)
        ]

    columns = [
        ColumnSpec("skill", "Skill", no_wrap=True),
        ColumnSpec("target", "Target", no_wrap=True),
        ColumnSpec("scope", "Scope", no_wrap=True),
        ColumnSpec("files", "Files", justify="right", formatter=fmt_int),
        ColumnSpec("path", "Installed Path"),
    ]
    output_records(
        installed_rows,
        fmt=resolved_fmt,
        columns=columns,
        title="Installed Agent Skills",
    )


__all__ = [
    "SkillMetadata",
    "SkillScope",
    "SkillTarget",
    "app",
    "discover_skills",
    "parse_skill_frontmatter",
    "resolve_install_targets",
    "resolve_skills_root",
    "skill_app",
    "validate_skill_frontmatter",
]
