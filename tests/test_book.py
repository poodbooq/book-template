from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.book import BookProject, BookProjectError


class BookProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for directory in (
            "chapters",
            "scenes",
            "characters",
            "world",
            "events",
            "journal",
            "inbox",
            "notes",
            "build",
            "styles",
        ):
            (self.root / directory).mkdir()
        (self.root / "styles" / "book.css").write_text(
            "body { font-family: serif; }\n", encoding="utf-8"
        )
        (self.root / "book.yaml").write_text(
            (
                'title: "Тестова книга"\n'
                'author: "Автор"\n'
                "lang: uk-UA\n"
                "toc: true\n"
                "pdf-engine: weasyprint\n"
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, relative: str, content: str) -> None:
        (self.root / relative).write_text(content.strip() + "\n", encoding="utf-8")

    def test_assemble_includes_published_scenes_and_resolves_wikilinks(self) -> None:
        self.write(
            "chapters/01.md",
            '''
---
title: "Глава перша"
status: revised
order: 1
---

- [[opening]]
- [[discarded]]
''',
        )
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: final
word-count: 0
---

[[marta|Марта]] прийшла до [[mill]].
''',
        )
        self.write(
            "scenes/discarded.md",
            '''
---
title: "Чернетка"
status: draft
word-count: 0
---

Цього тексту не має бути.
''',
        )
        self.write(
            "characters/marta.md",
            '''
---
title: "Марта"
---
''',
        )
        self.write(
            "world/mill.md",
            '''
---
title: "Старий млин"
---
''',
        )

        markdown = BookProject(self.root).assemble()

        self.assertIn("# Глава перша", markdown)
        self.assertIn("Марта прийшла до Старий млин.", markdown)
        self.assertNotIn("Цього тексту не має бути", markdown)
        self.assertNotIn("[[", markdown)
        self.assertNotIn('Глава перша"', markdown)

    def test_missing_scene_is_fatal(self) -> None:
        self.write(
            "chapters/01.md",
            '''
---
title: "Глава"
status: revised
order: 1
---

- [[missing-scene]]
''',
        )

        with self.assertRaisesRegex(BookProjectError, "missing-scene"):
            BookProject(self.root).assemble()

    def test_add_scene_uses_zk_compatible_link_and_rejects_duplicates(self) -> None:
        self.write(
            "chapters/01.md",
            '''
---
title: "Глава"
status: draft
order: 1
---
''',
        )
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: draft
word-count: 0
---
''',
        )
        project = BookProject(self.root)

        project.add_scene("01", "opening")

        chapter = (self.root / "chapters/01.md").read_text(encoding="utf-8")
        self.assertIn("- [[opening]]", chapter)
        self.assertNotIn("![[opening]]", chapter)
        with self.assertRaisesRegex(BookProjectError, "already"):
            BookProject(self.root).add_scene("01", "opening")

    def test_wordcount_updates_scene_frontmatter_without_rewriting_file(self) -> None:
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: draft
word-count: 0
pov: ""
---

Одне два, три-чотири.
''',
        )
        project = BookProject(self.root)

        counts = project.update_word_counts()

        text = (self.root / "scenes/opening.md").read_text(encoding="utf-8")
        self.assertEqual({"opening": 3}, counts)
        self.assertIn("word-count: 3", text)
        self.assertIn('pov: ""', text)

    def test_wordcount_counts_wikilink_as_rendered_label(self) -> None:
        self.write(
            "characters/marta.md",
            '''
---
title: "Марта Коваль"
---
''',
        )
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: draft
word-count: 0
---

[[marta]] прийшла.
''',
        )

        counts = BookProject(self.root).update_word_counts()

        self.assertEqual(3, counts["opening"])

    def test_generate_index_lists_notes_by_section(self) -> None:
        self.write(
            "characters/marta.md",
            '''
---
title: "Марта"
---
''',
        )
        self.write(
            "world/mill.md",
            '''
---
title: "Старий млин"
---
''',
        )

        path = BookProject(self.root).generate_index()

        index = path.read_text(encoding="utf-8")
        self.assertIn("## Characters", index)
        self.assertIn("- [[marta|Марта]]", index)
        self.assertIn("## World", index)
        self.assertIn("- [[mill|Старий млин]]", index)

    def test_check_cli_returns_nonzero_and_prints_validation_errors(self) -> None:
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: revised
word-count: 0
---

[[missing]]
''',
        )
        script = Path(__file__).parents[1] / "scripts" / "book.py"

        result = subprocess.run(
            [sys.executable, str(script), "--root", str(self.root), "check"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("missing", result.stderr)

    def test_build_html_and_epub_create_real_book_files(self) -> None:
        self.write(
            "chapters/01.md",
            '''
---
title: "Глава"
status: revised
order: 1
---

- [[opening]]
''',
        )
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: final
word-count: 0
---

Текст українською.
''',
        )
        project = BookProject(self.root)

        html = project.build("html")
        epub = project.build("epub")

        self.assertTrue(html.is_file())
        self.assertIn("Текст українською", html.read_text(encoding="utf-8"))
        self.assertTrue(epub.is_file())
        self.assertGreater(epub.stat().st_size, 1000)

    def test_html_comments_do_not_create_scene_references(self) -> None:
        self.write(
            "chapters/01.md",
            '''
---
title: "Глава"
status: revised
order: 1
---

<!-- - [[example-scene]] -->
- [[opening]]
''',
        )
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: revised
word-count: 0
---

Текст.
''',
        )

        project = BookProject(self.root)

        self.assertFalse(project.check().errors)
        self.assertIn("Текст.", project.assemble())

    def test_check_rejects_published_chapter_with_only_draft_scenes(self) -> None:
        self.write(
            "chapters/01.md",
            '''
---
title: "Глава"
status: revised
order: 1
---

- [[opening]]
''',
        )
        self.write(
            "scenes/opening.md",
            '''
---
title: "Чернетка"
status: draft
word-count: 0
---

Текст.
''',
        )

        report = BookProject(self.root).check()

        self.assertTrue(any("no publishable scenes" in error for error in report.errors))

    def test_check_rejects_scene_assigned_to_multiple_chapters(self) -> None:
        for slug, order in (("one", 1), ("two", 2)):
            self.write(
                f"chapters/{slug}.md",
                f'''\n---
title: "Глава {order}"
status: revised
order: {order}
---

- [[opening]]
''',
            )
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: revised
word-count: 0
---

Текст.
''',
        )

        report = BookProject(self.root).check()

        self.assertTrue(any("multiple chapters" in error for error in report.errors))

    def test_check_rejects_published_chapter_without_scenes(self) -> None:
        self.write(
            "chapters/01.md",
            '''
---
title: "Порожня глава"
status: revised
order: 1
---

<!-- - [[scene-slug]] -->
''',
        )

        report = BookProject(self.root).check()

        self.assertTrue(any("has no scenes" in error for error in report.errors))

    def test_check_reports_invalid_schema_version(self) -> None:
        (self.root / "book.yaml").write_text(
            'title: "Тестова книга"\nlang: uk-UA\nschema-version: one\n',
            encoding="utf-8",
        )

        report = BookProject(self.root).check()

        self.assertTrue(any("schema-version" in error for error in report.errors))

    def test_check_enforces_required_scene_schema(self) -> None:
        (self.root / "book.yaml").write_text(
            'title: "Тестова книга"\nlang: uk-UA\nschema-version: 1\n',
            encoding="utf-8",
        )
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: draft
word-count: 0
---
''',
        )

        report = BookProject(self.root).check()

        self.assertTrue(any("timeline-order" in error for error in report.errors))
        self.assertTrue(any("created" in error for error in report.errors))

    def test_check_validates_wikilinks_inside_frontmatter(self) -> None:
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: draft
word-count: 0
pov: "[[ghost]]"
---
''',
        )

        report = BookProject(self.root).check()

        self.assertTrue(any("ghost" in error for error in report.errors))

    def test_check_reports_broken_links_and_unassigned_published_scenes(self) -> None:
        self.write(
            "chapters/01.md",
            '''
---
title: "Глава"
status: revised
order: 1
---

- [[opening]]
''',
        )
        self.write(
            "scenes/opening.md",
            '''
---
title: "Відкриття"
status: final
word-count: 0
---

Згадка про [[unknown]].
''',
        )
        self.write(
            "scenes/orphan.md",
            '''
---
title: "Зайва сцена"
status: revised
word-count: 0
---

Неприв'язаний текст.
''',
        )

        report = BookProject(self.root).check()

        self.assertTrue(any("unknown" in error for error in report.errors))
        self.assertTrue(any("orphan" in warning for warning in report.warnings))

    def test_unknown_status_is_fatal(self) -> None:
        self.write(
            "chapters/01.md",
            '''
---
title: "Глава"
status: darft
order: 1
---
''',
        )

        with self.assertRaisesRegex(BookProjectError, "darft"):
            BookProject(self.root).assemble()


if __name__ == "__main__":
    unittest.main()
