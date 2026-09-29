import unittest

from src.session_types import SessionOptions


class SessionOptionsTests(unittest.TestCase):
    def test_every_session_requires_consent(self):
        self.assertEqual(
            SessionOptions(consent_confirmed=False).validation_error(),
            "Confirm participant consent",
        )

    def test_transcript_requires_audio(self):
        options = SessionOptions(transcript=True, consent_confirmed=True)
        self.assertEqual(
            options.validation_error(),
            "Transcript requires meeting audio or microphone",
        )

    def test_participant_id_is_trimmed_and_paths_are_rejected(self):
        self.assertEqual(
            SessionOptions(participant_id="  learner-07  ").participant_id,
            "learner-07",
        )
        with self.assertRaises(ValueError):
            SessionOptions(participant_id="../student")


if __name__ == "__main__":
    unittest.main()
