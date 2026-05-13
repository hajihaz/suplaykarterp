from __future__ import annotations

import unittest

from app.services.web_lookup import WebLookupService


class WebLookupQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = WebLookupService()

    def test_president_of_america_normalizes_to_united_states(self) -> None:
        phrase = self.service._current_office_search_phrase("who is president of america")

        self.assertEqual(phrase, "President of United States")

    def test_president_of_america_uses_direct_office_qid(self) -> None:
        phrase = self.service._current_office_search_phrase("who is president of america")
        direct_office = self.service._direct_current_office_qid(phrase or "")

        self.assertEqual(direct_office, ("President of United States", "Q11696"))

    def test_president_of_america_uses_authoritative_direct_holder(self) -> None:
        phrase = self.service._current_office_search_phrase("who is president of america")
        holder = self.service._direct_current_office_holder(phrase or "")

        self.assertIsNotNone(holder)
        assert holder is not None
        self.assertEqual(holder["office"], "President of United States")
        self.assertEqual(holder["name"], "Donald Trump")
        self.assertIn("whitehouse.gov", holder["url"])

    def test_current_office_candidate_requires_matching_office(self) -> None:
        self.assertTrue(
            self.service._office_candidate_matches(
                "President of United States",
                "President of the United States",
                "head of state and head of government of the United States",
            )
        )
        self.assertFalse(
            self.service._office_candidate_matches(
                "President of United States",
                "Phil Baker",
                "American radio personality and comedian",
            )
        )

    def test_who_is_person_prompt_extracts_entity_phrase(self) -> None:
        phrase = self.service._entity_search_phrase("who is narendra modi")

        self.assertEqual(phrase, "narendra modi")

    def test_entity_ranking_demotes_movie_result_for_public_person(self) -> None:
        ranked = self.service._rank_results(
            "who is narendra modi",
            [
                {
                    "title": "Narendra Modi Movie Review",
                    "excerpt": "Narendra Modi is a film and movie trailer topic.",
                    "url": "https://example.com/movie",
                    "source": "DuckDuckGo",
                },
                {
                    "title": "Narendra Modi",
                    "excerpt": "Narendra Modi is an Indian politician who has served as prime minister of India since 2014.",
                    "url": "https://en.wikipedia.org/wiki/Narendra_Modi",
                    "source": "Wikipedia",
                    "quality_score": 5.0,
                },
            ],
        )

        self.assertEqual(ranked[0]["title"], "Narendra Modi")

    def test_news_ranking_demotes_entertainment_noise(self) -> None:
        ranked = self.service._rank_results(
            "top news in tamilnadu",
            [
                {
                    "title": "Jyothika movie trailer trends",
                    "excerpt": "Tamil cinema actress Jyothika stars in a new movie trailer.",
                    "url": "https://example.com/cinema",
                    "kind": "news",
                    "source": "Google News / Entertainment",
                },
                {
                    "title": "Tamil Nadu government announces new measures",
                    "excerpt": "Tamil Nadu government officials announced new public measures today.",
                    "url": "https://www.thehindu.com/news/national/tamil-nadu/example",
                    "kind": "news",
                    "source": "Google News / The Hindu",
                },
            ],
        )

        self.assertEqual(ranked[0]["title"], "Tamil Nadu government announces new measures")


if __name__ == "__main__":
    unittest.main()
