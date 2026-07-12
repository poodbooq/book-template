from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "create-book.sh"


class CreateBookScriptTests(unittest.TestCase):
    def test_creates_private_repository_from_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            log_path = tmp / "gh.log"
            fake_gh = bin_dir / "gh"
            fake_gh.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf '%s\\n' \"$*\" >> \"$GH_LOG\"\n"
                "if [[ \"$1\" == auth && \"$2\" == status ]]; then\n"
                "  exit 0\n"
                "fi\n"
                "if [[ \"$1\" == repo && \"$2\" == create ]]; then\n"
                "  exit 0\n"
                "fi\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            env = {
                **os.environ,
                "GH_LOG": str(log_path),
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
            }

            result = subprocess.run(
                ["bash", str(SCRIPT), "my-book"],
                capture_output=True,
                check=False,
                env=env,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                log_path.read_text(encoding="utf-8").splitlines(),
                [
                    "auth status",
                    "repo create my-book --private --template poodbooq/book-template --clone",
                ],
            )

    def test_rejects_missing_repository_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            fake_gh = bin_dir / "gh"
            fake_gh.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_gh.chmod(0o755)
            env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}

            result = subprocess.run(
                ["bash", str(SCRIPT)],
                capture_output=True,
                check=False,
                env=env,
                text=True,
            )

            self.assertEqual(result.returncode, 64)
            self.assertIn("Usage: create-book.sh REPOSITORY", result.stderr)

    def test_explains_when_github_cli_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = {**os.environ, "PATH": str(Path(tmp_dir))}

            result = subprocess.run(
                ["/bin/bash", str(SCRIPT), "my-book"],
                capture_output=True,
                check=False,
                env=env,
                text=True,
            )

            self.assertEqual(result.returncode, 127)
            self.assertIn("GitHub CLI (gh) is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
