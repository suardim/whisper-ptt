#!/usr/bin/env python3
"""Tests for text cleaning / anti-repetition logic in push-to-talk.py.

The main module has a hyphen in its name and imports GUI libs at top level,
so we load it via importlib. Importing is safe: the app only starts in main().
"""
import importlib.util
import os
import sys
import unittest

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_module():
    path = os.path.join(SCRIPT_DIR, "push-to-talk.py")
    spec = importlib.util.spec_from_file_location("ptt", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ptt = load_module()


class TestCollapseRepetitions(unittest.TestCase):
    def test_drops_pure_repetition_run(self):
        # The user's exact symptom
        self.assertEqual(ptt.collapse_repetitions("da da da da da da da"), "")

    def test_drops_de_run(self):
        text = "de " * 50
        self.assertEqual(ptt.collapse_repetitions(text.strip()), "")

    def test_salvages_real_text_after_run(self):
        # Leading hallucinated run, then genuine speech must survive
        text = "de de de de de de de Eu estou vendo os dados"
        self.assertEqual(
            ptt.collapse_repetitions(text), "Eu estou vendo os dados"
        )

    def test_handles_punctuation_and_case(self):
        # "Ok? Ok? Ok? ..." style garbage, case/punct insensitive
        self.assertEqual(ptt.collapse_repetitions("Ok? Ok? Ok? Ok? Ok?"), "")

    def test_keeps_legitimate_short_repeats(self):
        # Real speech: a word repeated up to 3 times is kept
        self.assertEqual(ptt.collapse_repetitions("no no no"), "no no no")

    def test_keeps_normal_sentence(self):
        s = "vamos verificar o relatório diário de quilômetros"
        self.assertEqual(ptt.collapse_repetitions(s), s)


class TestCleanText(unittest.TestCase):
    def test_clean_text_strips_repetition(self):
        self.assertEqual(ptt.clean_text("da da da da da da"), "")

    def test_clean_text_keeps_real(self):
        self.assertEqual(ptt.clean_text("  preciso de um plano  "), "preciso de um plano")


class TestPromptSanitization(unittest.TestCase):
    def test_history_garbage_excluded_from_prompt(self):
        # Build a fake history file dominated by garbage and ensure the
        # prompt builder does not echo the repetition back.
        import tempfile
        garbage = "de " * 200
        lines = [
            "[2026-05-21 16:00:00] vamos analisar o relatório de vendas",
            f"[2026-05-21 16:01:00] {garbage.strip()}",
            f"[2026-05-21 16:02:00] {garbage.strip()}",
            "[2026-05-21 16:03:00] precisamos exportar a dashboard",
            f"[2026-05-21 16:04:00] {garbage.strip()}",
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("\n".join(lines) + "\n")
            tmp = f.name
        try:
            orig = ptt.HISTORY_FILE
            ptt.HISTORY_FILE = tmp
            hist = ptt.get_recent_history(5)
            self.assertNotIn("de de de de", hist)
            self.assertIn("relatório", hist)
            self.assertIn("dashboard", hist)
        finally:
            ptt.HISTORY_FILE = orig
            os.unlink(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
