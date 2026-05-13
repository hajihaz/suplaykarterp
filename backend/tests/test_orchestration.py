from __future__ import annotations

import unittest

from app.services.orchestration import build_route_plan, filter_relevant_memories


class OrchestrationTests(unittest.TestCase):
    def test_current_affairs_blocks_memory(self) -> None:
        route = build_route_plan("Who is the Prime Minister of India?", [])

        self.assertEqual(route.intent, "current_affairs")
        self.assertEqual(route.source_strategy, "web")
        self.assertFalse(route.memory_allowed)
        self.assertIn("memory_blocked_for_current_affairs", route.reasons)

    def test_user_relationship_uses_memory_query(self) -> None:
        route = build_route_plan("Who is my father?", [])

        self.assertEqual(route.intent, "personal_memory")
        self.assertEqual(route.source_strategy, "memory")
        self.assertTrue(route.memory_allowed)
        self.assertTrue(route.memory_required)
        self.assertEqual(route.effective_prompt, "Who is Haji's father?")
        self.assertIn("Haji family relationship", route.memory_query)

    def test_bare_named_entity_uses_web_not_memory(self) -> None:
        route = build_route_plan("who is shehnaaz", [])
        contexts = [
            {
                "title": "Haji Family Structure",
                "content": "Mother Name: Shehnaaz Nisha. Relationship with Haji: Mother.",
                "tags": ["haji", "family"],
                "score": 1.0,
                "core_persona": True,
            },
            {
                "title": "Business Strategy",
                "content": "A general note about planning, pricing, and business reviews.",
                "tags": ["operations"],
                "score": 0.8,
                "core_persona": False,
            },
        ]

        selected, confidence = filter_relevant_memories(route, contexts)

        self.assertEqual(route.source_strategy, "web")
        self.assertFalse(route.memory_allowed)
        self.assertEqual(confidence, 0.0)
        self.assertEqual(selected, [])

    def test_memory_disabled_blocks_retrieval_even_for_personal_prompt(self) -> None:
        route = build_route_plan("What business do I run?", [], memory_enabled=False)

        self.assertEqual(route.intent, "personal_memory")
        self.assertFalse(route.memory_allowed)
        self.assertFalse(route.memory_required)
        self.assertEqual(route.source_strategy, "general")


if __name__ == "__main__":
    unittest.main()
