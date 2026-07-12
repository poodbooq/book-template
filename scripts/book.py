#!/usr/bin/env python3
"""Book-template build, validation, and authoring commands."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

CONTENT_DIRS = (
    "scenes",
    "chapters",
    "characters",
    "world",
    "events",
    "journal",
    "inbox",
    "notes",
)
PUBLISH_STATUSES = {"revised", "final"}
VALID_STATUSES = {"draft", *PUBLISH_STATUSES}
REQUIRED_FIELDS = {
    "scenes": {
        "title", "created", "updated", "tags", "status", "word-count",
        "pov", "setting", "story-date", "timeline-order", "act",
    },
    "chapters": {"title", "created", "updated", "tags", "status", "order", "act", "part", "pov"},
    "characters": {
        "title", "created", "updated", "tags", "role", "arc",
        "motivation", "conflict", "aliases",
    },
    "world": {"title", "created", "updated", "tags", "type", "era", "first-appearance", "aliases"},
    "events": {
        "title", "created", "updated", "tags", "story-date", "era", "type",
        "location", "characters", "causes", "consequences", "order", "aliases",
    },
    "journal": {"title", "created", "updated", "tags"},
    "notes": {"title", "created", "updated", "tags", "type", "sources", "aliases"},
    "inbox": {"title", "created", "updated", "tags", "aliases"},
}
WIKILINK_RE = re.compile(r"!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


class BookProjectError(RuntimeError):
    """A user-actionable project validation or build error."""


@dataclass(frozen=True)
class Note:
    path: Path
    metadata: dict[str, Any]
    body: str

    @property
    def slug(self) -> str:
        return self.path.stem

    @property
    def title(self) -> str:
        value = self.metadata.get("title", self.slug)
        return str(value).strip()

    @property
    def status(self) -> str | None:
        value = self.metadata.get("status")
        return str(value).strip() if value is not None else None


@dataclass
class ValidationReport:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def read_note(path: Path) -> Note:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise BookProjectError(f"{path}: missing YAML frontmatter")
    try:
        _, raw_metadata, body = text.split("---", 2)
        metadata = yaml.safe_load(raw_metadata) or {}
    except (ValueError, yaml.YAMLError) as exc:
        raise BookProjectError(f"{path}: invalid YAML frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise BookProjectError(f"{path}: frontmatter must be a YAML mapping")
    return Note(path=path, metadata=metadata, body=body.lstrip("\n"))


def normalize_target(target: str) -> str:
    return Path(target.strip()).stem


def active_markdown(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def iter_text_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_text_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_text_values(item)


class BookProject:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.book_config = self._load_book_config()
        self.notes = self._load_notes()
        self.by_slug = self._index_slugs(self.notes)

    def _load_book_config(self) -> dict[str, Any]:
        path = self.root / "book.yaml"
        if not path.is_file():
            raise BookProjectError(f"{path}: missing book metadata")
        try:
            config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise BookProjectError(f"{path}: invalid YAML: {exc}") from exc
        if not isinstance(config, dict):
            raise BookProjectError(f"{path}: metadata must be a YAML mapping")
        return config

    def _load_notes(self) -> list[Note]:
        notes: list[Note] = []
        for directory in CONTENT_DIRS:
            base = self.root / directory
            if not base.is_dir():
                continue
            notes.extend(read_note(path) for path in sorted(base.glob("*.md")))
        return notes

    @staticmethod
    def _index_slugs(notes: Iterable[Note]) -> dict[str, Note]:
        result: dict[str, Note] = {}
        for note in notes:
            if note.slug in result:
                raise BookProjectError(
                    f"duplicate slug '{note.slug}': {result[note.slug].path} and {note.path}"
                )
            result[note.slug] = note
        return result

    def _validate_status(self, note: Note) -> str:
        status = note.status
        if status not in VALID_STATUSES:
            raise BookProjectError(
                f"{note.path}: invalid status {status!r}; expected draft, revised, or final"
            )
        return status

    def _resolve_links(self, text: str, source: Path) -> str:
        def replace(match: re.Match[str]) -> str:
            target = normalize_target(match.group(1))
            label = match.group(2)
            note = self.by_slug.get(target)
            if note is None:
                raise BookProjectError(f"{source}: broken wikilink '{target}'")
            return label or note.title

        return WIKILINK_RE.sub(replace, text)

    def _scene_references(self, chapter: Note) -> list[Note]:
        references: list[Note] = []
        for match in WIKILINK_RE.finditer(active_markdown(chapter.body)):
            target = normalize_target(match.group(1))
            note = self.by_slug.get(target)
            if note is None:
                raise BookProjectError(f"{chapter.path}: missing scene '{target}'")
            if note.path.parent.name != "scenes":
                raise BookProjectError(
                    f"{chapter.path}: chapter entry '{target}' is not a scene"
                )
            references.append(note)
        if not references:
            raise BookProjectError(f"{chapter.path}: published chapter has no scenes")
        return references

    def check(self) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        assigned_scenes: dict[str, Path] = {}
        chapter_orders: dict[int, Path] = {}
        raw_schema_version = self.book_config.get("schema-version", 0)
        try:
            schema_version = int(str(raw_schema_version))
        except ValueError:
            errors.append("book.yaml: 'schema-version' must be an integer")
            schema_version = 0
        enforce_schema = schema_version >= 1

        for required in ("title", "lang"):
            if not str(self.book_config.get(required, "")).strip():
                errors.append(f"book.yaml: '{required}' must not be empty")

        for note in self.notes:
            if not note.title:
                errors.append(f"{note.path}: title must not be empty")

            for value in iter_text_values(note.metadata):
                for match in WIKILINK_RE.finditer(value):
                    target = normalize_target(match.group(1))
                    if target not in self.by_slug:
                        errors.append(
                            f"{note.path}: broken wikilink '{target}' in frontmatter"
                        )

            kind = note.path.parent.name
            if enforce_schema:
                for field in sorted(REQUIRED_FIELDS.get(kind, set()) - note.metadata.keys()):
                    errors.append(f"{note.path}: missing required field '{field}'")

            if kind in {"chapters", "scenes"}:
                if note.status not in VALID_STATUSES:
                    errors.append(
                        f"{note.path}: invalid status {note.status!r}; "
                        "expected draft, revised, or final"
                    )
                if note.status in PUBLISH_STATUSES and not note.body.strip():
                    errors.append(f"{note.path}: published note is empty")

            if kind == "chapters":
                raw_order = note.metadata.get("order")
                try:
                    order = int(str(raw_order))
                except (TypeError, ValueError):
                    errors.append(f"{note.path}: order must be an integer")
                else:
                    if order in chapter_orders:
                        errors.append(
                            f"{note.path}: duplicate chapter order {order} "
                            f"(also used by {chapter_orders[order]})"
                        )
                    chapter_orders[order] = note.path

                chapter_links = list(
                    WIKILINK_RE.finditer(active_markdown(note.body))
                )
                if note.status in PUBLISH_STATUSES and not chapter_links:
                    errors.append(f"{note.path}: published chapter has no scenes")
                publishable_scene_count = 0
                for match in chapter_links:
                    target = normalize_target(match.group(1))
                    linked = self.by_slug.get(target)
                    if linked is None:
                        errors.append(f"{note.path}: broken wikilink '{target}'")
                    elif linked.path.parent.name != "scenes":
                        errors.append(f"{note.path}: chapter entry '{target}' is not a scene")
                    else:
                        previous = assigned_scenes.get(target)
                        if previous is not None:
                            errors.append(
                                f"{linked.path}: scene is assigned to multiple chapters: "
                                f"{previous} and {note.path}"
                            )
                        else:
                            assigned_scenes[target] = note.path
                        if linked.status in PUBLISH_STATUSES:
                            publishable_scene_count += 1
                if (
                    note.status in PUBLISH_STATUSES
                    and chapter_links
                    and publishable_scene_count == 0
                ):
                    errors.append(f"{note.path}: published chapter has no publishable scenes")
            else:
                for match in WIKILINK_RE.finditer(active_markdown(note.body)):
                    target = normalize_target(match.group(1))
                    if target not in self.by_slug:
                        errors.append(f"{note.path}: broken wikilink '{target}'")

        for note in self.notes:
            if (
                note.path.parent.name == "scenes"
                and note.status in PUBLISH_STATUSES
                and note.slug not in assigned_scenes
            ):
                warnings.append(f"{note.path}: published scene is not assigned to a chapter")

        return ValidationReport(errors=errors, warnings=warnings)

    def add_scene(self, chapter_slug: str, scene_slug: str) -> Path:
        chapter = self.by_slug.get(normalize_target(chapter_slug))
        if chapter is None or chapter.path.parent.name != "chapters":
            raise BookProjectError(f"chapter '{chapter_slug}' does not exist")
        scene = self.by_slug.get(normalize_target(scene_slug))
        if scene is None or scene.path.parent.name != "scenes":
            raise BookProjectError(f"scene '{scene_slug}' does not exist")

        existing = {
            normalize_target(match.group(1))
            for match in WIKILINK_RE.finditer(active_markdown(chapter.body))
        }
        if scene.slug in existing:
            raise BookProjectError(
                f"scene '{scene.slug}' is already present in chapter '{chapter.slug}'"
            )
        with chapter.path.open("a", encoding="utf-8") as handle:
            if chapter.body and not chapter.body.endswith("\n"):
                handle.write("\n")
            handle.write(f"\n- [[{scene.slug}]]\n")
        return chapter.path

    def update_word_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        word_pattern = re.compile(r"[^\W_]+(?:[-’'][^\W_]+)*", re.UNICODE)
        for note in self.notes:
            if note.path.parent.name != "scenes":
                continue

            def link_text(match: re.Match[str]) -> str:
                target = normalize_target(match.group(1))
                linked = self.by_slug.get(target)
                return match.group(2) or (linked.title if linked else target)

            rendered = WIKILINK_RE.sub(link_text, active_markdown(note.body))
            count = len(word_pattern.findall(rendered))
            original = note.path.read_text(encoding="utf-8")
            updated, replacements = re.subn(
                r"(?m)^word-count:\s*\d+\s*$",
                f"word-count: {count}",
                original,
                count=1,
            )
            if replacements != 1:
                raise BookProjectError(f"{note.path}: missing numeric word-count field")
            note.path.write_text(updated, encoding="utf-8")
            counts[note.slug] = count
        return counts

    def generate_index(self) -> Path:
        sections = (
            ("Chapters", "chapters"),
            ("Characters", "characters"),
            ("World", "world"),
            ("Events", "events"),
            ("Notes", "notes"),
            ("Journal", "journal"),
        )
        lines = ["# Index", "", "> Generated by `just index`. Do not edit manually.", ""]
        for heading, directory in sections:
            lines.extend((f"## {heading}", ""))
            notes = sorted(
                (note for note in self.notes if note.path.parent.name == directory),
                key=lambda note: note.title.casefold(),
            )
            if notes:
                lines.extend(f"- [[{note.slug}|{note.title}]]" for note in notes)
            else:
                lines.append("_Поки порожньо._")
            lines.append("")
        path = self.root / "index.md"
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return path

    def assemble(self) -> str:
        chapters = [note for note in self.notes if note.path.parent.name == "chapters"]
        chapters.sort(key=lambda note: (int(note.metadata.get("order", 10**9)), note.path.name))

        output: list[str] = []
        published_chapters = 0
        for chapter in chapters:
            if self._validate_status(chapter) == "draft":
                continue
            published_chapters += 1
            output.extend((f"# {chapter.title}", ""))
            for scene in self._scene_references(chapter):
                if self._validate_status(scene) == "draft":
                    continue
                body = self._resolve_links(scene.body.rstrip(), scene.path)
                if not body.strip():
                    raise BookProjectError(f"{scene.path}: published scene is empty")
                output.extend((body, ""))

        if published_chapters == 0:
            raise BookProjectError("no revised or final chapters to build")
        return "\n".join(output).rstrip() + "\n"

    def build(self, output_format: str) -> Path:
        if output_format not in {"markdown", "html", "epub", "pdf"}:
            raise BookProjectError(f"unsupported output format: {output_format}")

        report = self.check()
        if report.errors:
            raise BookProjectError("validation failed:\n- " + "\n- ".join(report.errors))

        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = build_dir / "book.md"
        markdown_path.write_text(self.assemble(), encoding="utf-8")
        if output_format == "markdown":
            return markdown_path

        if shutil.which("pandoc") is None:
            raise BookProjectError("pandoc is required to build books")

        output_path = build_dir / f"book.{output_format}"
        command = [
            "pandoc",
            str(markdown_path.relative_to(self.root)),
            "--metadata-file=book.yaml",
            "--from=markdown",
            f"--output={output_path.relative_to(self.root)}",
        ]
        css = self.root / "styles" / "book.css"
        if self.book_config.get("toc", False):
            command.append("--toc")

        if output_format == "html":
            command.extend(("--to=html5", "--standalone", "--embed-resources"))
            if css.is_file():
                command.append("--css=styles/book.css")
        elif output_format == "epub":
            command.append("--to=epub3")
            if css.is_file():
                command.append("--css=styles/book.css")
        else:
            engine = str(self.book_config.get("pdf-engine", "weasyprint"))
            if shutil.which(engine) is None:
                raise BookProjectError(
                    f"PDF engine '{engine}' is not installed; run 'just doctor'"
                )
            command.extend((f"--pdf-engine={engine}", "--to=html5"))
            if css.is_file():
                command.append("--css=styles/book.css")

        try:
            subprocess.run(
                command,
                cwd=self.root,
                check=True,
                text=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "unknown pandoc failure").strip()
            raise BookProjectError(f"pandoc failed: {details}") from exc
        return output_path


def doctor(root: Path, book_config: dict[str, Any]) -> bool:
    checks = {
        "python3": shutil.which("python3"),
        "just": shutil.which("just"),
        "zk": shutil.which("zk"),
        "pandoc": shutil.which("pandoc"),
        "PyYAML": yaml.__version__,
    }
    engine = str(book_config.get("pdf-engine", "weasyprint"))
    checks[f"pdf-engine ({engine})"] = shutil.which(engine)
    ok = True
    for name, value in checks.items():
        present = bool(value)
        ok = ok and present
        print(f"{'OK' if present else 'MISSING':7} {name}: {value or '-'}")
    if checks["zk"]:
        result = subprocess.run(
            ["zk", "index"], cwd=root, text=True, capture_output=True, check=False
        )
        if result.returncode == 0:
            print("OK      zk notebook configuration")
        else:
            ok = False
            print(f"ERROR   zk notebook configuration: {result.stderr.strip()}")
    return ok


def create_note(root: Path, project: BookProject, kind: str, title: str | None) -> Path:
    directories = {
        "scene": "scenes",
        "chapter": "chapters",
        "character": "characters",
        "location": "world",
        "event": "events",
        "journal": "journal",
        "note": "notes",
        "inbox": "inbox",
    }
    directory = directories[kind]
    command = ["zk", "new", directory, "--no-input", "--print-path"]
    if title:
        command.extend(("--title", title))
    result = subprocess.run(
        command, cwd=root, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise BookProjectError(result.stderr.strip() or "zk failed to create note")
    path = Path(result.stdout.strip())
    if not path.is_absolute():
        path = root / path

    if kind == "chapter":
        existing_orders = [
            int(str(note.metadata.get("order", 0)))
            for note in project.notes
            if note.path.parent.name == "chapters"
        ]
        next_order = max(existing_orders, default=0) + 1
        text = path.read_text(encoding="utf-8")
        text, count = re.subn(
            r"(?m)^order:\s*0\s*$", f"order: {next_order}", text, count=1
        )
        if count != 1:
            raise BookProjectError(f"{path}: chapter template has no 'order: 0'")
        path.write_text(text, encoding="utf-8")
    return path


def print_stats(project: BookProject) -> None:
    scenes = [note for note in project.notes if note.path.parent.name == "scenes"]
    print(f"Scenes: {len(scenes)}")
    for status in ("draft", "revised", "final"):
        print(f"  {status:8} {sum(note.status == status for note in scenes)}")
    for label, directory in (
        ("Chapters", "chapters"),
        ("Characters", "characters"),
        ("Events", "events"),
        ("Locations", "world"),
        ("Notes", "notes"),
    ):
        count = sum(note.path.parent.name == directory for note in project.notes)
        print(f"{label + ':':12} {count}")


def select_notes(project: BookProject, field: str, value: str) -> list[Note]:
    return sorted(
        (
            note
            for note in project.notes
            if value.casefold() in str(note.metadata.get(field, "")).casefold()
        ),
        key=lambda note: note.title.casefold(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("format", choices=("html", "epub", "pdf", "markdown"))
    subparsers.add_parser("check")
    subparsers.add_parser("doctor")
    subparsers.add_parser("wordcount")
    subparsers.add_parser("index")
    subparsers.add_parser("stats")
    subparsers.add_parser("list-drafts")
    subparsers.add_parser("chapters")
    subparsers.add_parser("characters")
    subparsers.add_parser("tags")
    subparsers.add_parser("timeline")

    recent = subparsers.add_parser("recent")
    recent.add_argument("days", type=int, nargs="?", default=7)
    search = subparsers.add_parser("search")
    search.add_argument("query")
    query = subparsers.add_parser("query")
    query.add_argument("field", choices=("act", "pov", "setting", "era"))
    query.add_argument("value")
    new = subparsers.add_parser("new")
    new.add_argument(
        "kind",
        choices=("scene", "chapter", "character", "location", "event", "journal", "note", "inbox"),
    )
    new.add_argument("title", nargs="?")
    add_scene_parser = subparsers.add_parser("add-scene")
    add_scene_parser.add_argument("chapter")
    add_scene_parser.add_argument("scene")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        project = BookProject(args.root)
        if args.command == "build":
            output = project.build(args.format)
            print(f"Built: {output}")
        elif args.command == "check":
            report = project.check()
            for warning in report.warnings:
                print(f"warning: {warning}", file=sys.stderr)
            for error in report.errors:
                print(f"error: {error}", file=sys.stderr)
            if not report.ok:
                return 1
            print("Check passed.")
        elif args.command == "doctor":
            return 0 if doctor(project.root, project.book_config) else 1
        elif args.command == "wordcount":
            counts = project.update_word_counts()
            for slug, count in sorted(counts.items()):
                print(f"{count:8}  {slug}")
            print(f"{'-' * 8}  {'-' * 20}")
            print(f"{sum(counts.values()):8}  total ({len(counts)} scenes)")
        elif args.command == "index":
            print(f"Generated: {project.generate_index()}")
        elif args.command == "add-scene":
            print(f"Updated: {project.add_scene(args.chapter, args.scene)}")
        elif args.command == "new":
            if args.kind != "journal" and not args.title:
                raise BookProjectError(f"title is required for {args.kind}")
            print(f"Created: {create_note(project.root, project, args.kind, args.title)}")
        elif args.command == "stats":
            print_stats(project)
        elif args.command == "list-drafts":
            for note in project.notes:
                if note.status == "draft":
                    print(note.path.relative_to(project.root))
        elif args.command == "chapters":
            chapters = sorted(
                (note for note in project.notes if note.path.parent.name == "chapters"),
                key=lambda note: (int(str(note.metadata.get("order", 10**9))), note.path.name),
            )
            for note in chapters:
                count = len(WIKILINK_RE.findall(active_markdown(note.body)))
                order = int(str(note.metadata.get("order", 0)))
                print(f"{order:3}  {note.title:30}  {count} scenes")
        elif args.command == "characters":
            notes = sorted(
                (note for note in project.notes if note.path.parent.name == "characters"),
                key=lambda note: note.title.casefold(),
            )
            for note in notes:
                print(
                    f"{note.title:24}  {str(note.metadata.get('role', '-')):12}  "
                    f"{note.metadata.get('arc', '-')}"
                )
        elif args.command == "tags":
            tag_counts: dict[str, int] = {}
            for note in project.notes:
                for tag in note.metadata.get("tags", []) or []:
                    tag_counts[str(tag)] = tag_counts.get(str(tag), 0) + 1
            for tag, count in sorted(
                tag_counts.items(), key=lambda item: (-item[1], item[0])
            ):
                print(f"{count:4}  {tag}")
        elif args.command == "timeline":
            entries: list[tuple[int, Note]] = []
            for note in project.notes:
                kind = note.path.parent.name
                field = "timeline-order" if kind == "scenes" else "order"
                if kind not in {"scenes", "events"}:
                    continue
                try:
                    order = int(str(note.metadata.get(field, 0)))
                except ValueError:
                    raise BookProjectError(f"{note.path}: {field} must be an integer")
                entries.append((order, note))
            for order, note in sorted(entries, key=lambda item: (item[0], item[1].title)):
                story_date = note.metadata.get("story-date", "-") or "-"
                print(
                    f"{order:6}  {str(story_date):18}  "
                    f"{note.path.parent.name:8}  {note.title}"
                )
        elif args.command == "query":
            for note in select_notes(project, args.field, args.value):
                print(f"{note.path.relative_to(project.root)}  {note.title}")
        elif args.command == "search":
            needle = args.query.casefold()
            for note in project.notes:
                for line_number, line in enumerate(
                    note.path.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    if needle in line.casefold():
                        print(f"{note.path.relative_to(project.root)}:{line_number}:{line}")
        elif args.command == "recent":
            import time

            cutoff = time.time() - args.days * 86400
            notes = sorted(
                project.notes,
                key=lambda item: item.path.stat().st_mtime,
                reverse=True,
            )
            for note in notes:
                if note.path.stat().st_mtime >= cutoff:
                    print(note.path.relative_to(project.root))
        return 0
    except BookProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
