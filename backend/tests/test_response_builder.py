from __future__ import annotations

import unittest

from app.services.response_builder import (
    _build_persona_relationship_detail_answer,
    expand_prompt_with_history,
    build_response,
)


class WebAnswerBuilderTests(unittest.TestCase):
    def test_simple_fact_prefers_direct_web_sentence(self) -> None:
        web_results = [
            {
                "title": "Capital city",
                "excerpt": "A capital city is the municipality exercising primary status in a country, state, or province.",
                "url": "https://example.com/capital-city",
            },
            {
                "title": "France",
                "excerpt": "Paris is the capital of France. It is the country's largest city.",
                "url": "https://example.com/france",
            },
        ]

        answer = build_response("What is the capital of France?", [], web_results)

        self.assertEqual(answer, "Paris is the capital of France.")


class PersonaRelationshipDetailTests(unittest.TestCase):
    def test_follow_up_expands_from_relation_first_answer(self) -> None:
        history = [
            {"role": "user", "content": "who is haji father"},
            {"role": "assistant", "content": "Haji's father is Syed Mohamed Hussain Sahib."},
        ]

        expanded = expand_prompt_with_history("give details of him", history)

        self.assertEqual(expanded, "Give more details about Syed Mohamed Hussain Sahib.")

    def test_relationship_detail_answer_stays_with_matched_person(self) -> None:
        contexts = [
            {
                "title": "Haji Family Structure",
                "content": (
                    "Father Name: Syed Mohamed Hussain Sahib "
                    "Nickname: Kannadi Sabu "
                    "Role: Head of the family "
                    "Contribution: Provides guidance and foundational support "
                    "Relationship with Haji: Father --- "
                    "Mother Name: Shehnaaz Nisha "
                    "Role: Primary financial supporter "
                    "Contribution: Provides emotional and family support "
                    "Relationship with Haji: Mother"
                ),
                "score": 0.91,
                "tags": ["family", "haji"],
                "core_persona": True,
                "excerpt": "",
            }
        ]

        answer = _build_persona_relationship_detail_answer(
            "father",
            "Syed Mohamed Hussain Sahib",
            contexts,
            answer_mode="balanced",
        )

        self.assertIsNotNone(answer)
        self.assertIn("Syed Mohamed Hussain Sahib is Haji's father.", answer)
        self.assertIn("He is head of the family.", answer)
        self.assertIn("He provides guidance and foundational support.", answer)
        self.assertNotIn("Shehnaaz", answer)
        self.assertNotIn("emotional and family support", answer.lower())

    def test_relationship_detail_splits_role_bullets_into_sentences(self) -> None:
        contexts = [
            {
                "title": "Haji Family Structure",
                "content": (
                    "Father Name: Syed Mohamed Hussain Sahib "
                    "Nickname: Kannadi Sabu "
                    "Role: - Head of the family - Provides guidance and foundational support "
                    "Relationship with Haji: - Father - Acts as a senior figure"
                ),
                "score": 0.91,
                "tags": ["family", "haji"],
                "core_persona": True,
                "excerpt": "",
            }
        ]

        answer = _build_persona_relationship_detail_answer(
            "father",
            "Syed Mohamed Hussain Sahib",
            contexts,
            answer_mode="balanced",
        )

        self.assertIsNotNone(answer)
        self.assertIn("He is head of the family.", answer)
        self.assertIn("He provides guidance and foundational support.", answer)
        self.assertNotIn("family Provides", answer)


if __name__ == "__main__":
    unittest.main()
