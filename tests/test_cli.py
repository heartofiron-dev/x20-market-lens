from __future__ import annotations

import os
from unittest import TestCase
from unittest.mock import patch

from x20.__main__ import ensure_live_credentials


class LiveCredentialTests(TestCase):
    def tearDown(self) -> None:
        os.environ.pop("APCA_API_KEY_ID", None)
        os.environ.pop("APCA_API_SECRET_KEY", None)

    def test_existing_environment_is_preserved(self) -> None:
        with patch.dict(
            os.environ,
            {"APCA_API_KEY_ID": "existing-key", "APCA_API_SECRET_KEY": "existing-secret"},
            clear=False,
        ), patch("x20.__main__.getpass.getpass") as prompt:
            ensure_live_credentials(prompt=True)
            prompt.assert_not_called()

    def test_secure_prompt_sets_process_environment(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch(
            "x20.__main__.getpass.getpass", side_effect=["paper-key", "paper-secret"]
        ):
            ensure_live_credentials(prompt=True)
            self.assertEqual(os.environ["APCA_API_KEY_ID"], "paper-key")
            self.assertEqual(os.environ["APCA_API_SECRET_KEY"], "paper-secret")

    def test_missing_environment_fails_without_prompt(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SystemExit, "--prompt-credentials"):
                ensure_live_credentials(prompt=False)

