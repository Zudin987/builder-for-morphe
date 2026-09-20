"""Guard against release-workflow regressions that can remove published APKs."""

import unittest
from pathlib import Path

WORKFLOW = (Path(__file__).resolve().parents[1] / ".github/workflows/build.yml").read_text(encoding="utf-8")


class ReleaseSafetyTests(unittest.TestCase):
    def test_preparation_never_deletes_a_published_release(self):
        prepare = WORKFLOW.split("      - name: Prepare clean draft release\n", 1)[1].split(
            "      - name: Set matrix based on patch source\n", 1
        )[0]
        self.assertIn("select(.tag_name == $ver and .draft == false)", prepare)
        self.assertIn('if [[ -n "$PUBLISHED_ID" ]]', prepare)
        self.assertIn("select(.tag_name == $ver and .draft == true)", prepare)
        self.assertLess(prepare.index('if [[ -n "$PUBLISHED_ID" ]]'), prepare.index("gh_retry api --method DELETE"))

    def test_publication_and_notification_require_all_builds_to_succeed(self):
        release = WORKFLOW.split("  release:\n", 1)[1]
        for name in (
            "Download and remove build logs",
            "Combine logs and finalize release",
            "Send Telegram notification",
        ):
            with self.subTest(step=name):
                step = release.split(f"      - name: {name}\n", 1)[1]
                condition = step.split("        if: ", 1)[1].split("\n", 1)[0]
                self.assertIn("needs.run.result == 'success'", condition)
                self.assertIn("steps.check.outputs.has_apks == 'true'", condition)


if __name__ == "__main__":
    unittest.main()
