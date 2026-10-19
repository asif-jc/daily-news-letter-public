"""Bounded semantic comparisons preserve global candidate and history membership."""

import unittest


class PairModel:
    def __init__(self, decide=None):
        self.calls = []
        self.decide = decide or (
            lambda pair: {
                "same_event": True,
                "novelty": "repeat" if pair["historical"] else "new",
            }
        )

    def complete(self, task, data, instructions=None):
        self.calls.append((task, data, instructions))
        return {
            "pairs": [
                {
                    "id": pair["id"],
                    "change": "",
                    "reason": "Explicit shared incident.",
                    **self.decide(pair),
                }
                for pair in data["pairs"]
            ]
        }


class BoundedGroupingTests(unittest.TestCase):
    def article(
        self, id, description="Council approved the Wellington flood map.", **kw
    ):
        return {
            "id": id,
            "title": description,
            "description": description,
            "source": "Example",
            "category": "world",
            "url": "https://example.com/" + id,
            "published": "2026-10-19T00:00:00Z",
            **kw,
        }

    def group(self, articles, model=None, history=None):
        from src.news.grouping import group_events_bounded

        return group_events_bounded(
            articles, model or PairModel(), history or {"stories": []}
        )

    def test_history_id_and_canonical_url_anchors_bypass_lexical_threshold(self):
        stories = [
            {
                "event_id": "old",
                "title": "No shared words",
                "summary": "Completely separate wording.",
                "sources": [
                    {"id": "a"},
                    {"url": "https://example.com/b?utm_source=rss"},
                ],
            }
        ]
        model = PairModel()
        result = self.group(
            [self.article("a", "Fresh"), self.article("b", "Another")],
            model,
            {"stories": stories},
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["event_id"], "old")
        self.assertEqual(result[0]["source_ids"], ["a", "b"])
        self.assertEqual(result[0]["novelty"], "repeat")
        self.assertEqual(result[0]["previous_event_ids"], ["old"])
        refs = [
            pair["right"]["id"] for _, data, _ in model.calls for pair in data["pairs"]
        ]
        self.assertEqual(refs, ["h1", "h1"])

    def test_exact_history_anchor_still_requires_a_positive_semantic_verdict(self):
        history = {
            "stories": [
                {
                    "event_id": "old",
                    "title": "Old incident",
                    "summary": "Old incident",
                    "sources": [{"id": "a"}],
                }
            ]
        }
        model = PairModel(lambda pair: {"same_event": False, "novelty": "new"})
        event = self.group([self.article("a")], model, history)[0]
        self.assertEqual(event["novelty"], "new")
        self.assertNotEqual(event["event_id"], "old")
        self.assertEqual(event["previous_event_ids"], [])
        self.assertEqual(len(model.calls), 1)

    def test_rejected_history_cannot_inherit_its_deterministic_event_identity(self):
        import hashlib

        old_id = hashlib.sha256(b"a").hexdigest()[:16]
        history = {
            "stories": [
                {
                    "event_id": old_id,
                    "title": "Old incident",
                    "summary": "Old incident",
                    "sources": [{"id": "a"}],
                }
            ]
        }
        verdict = lambda pair: {"same_event": False, "novelty": "new"}
        first = self.group([self.article("a")], PairModel(verdict), history)[0]
        again = self.group([self.article("a")], PairModel(verdict), history)[0]
        self.assertNotEqual(first["event_id"], old_id)
        self.assertEqual(first["event_id"], again["event_id"])
        self.assertEqual(first["previous_event_ids"], [])
        self.assertEqual(first["source_ids"], ["a"])
        self.assertEqual(first["novelty"], "new")
        # A previously assigned fallback ID is also reserved when unrelated history rejects it.
        history["stories"].append(
            {
                "event_id": first["event_id"],
                "title": "Another incident",
                "summary": "Another incident",
                "sources": [{"id": "a"}],
            }
        )
        later = self.group([self.article("a")], PairModel(verdict), history)[0]
        self.assertNotIn(later["event_id"], {old_id, first["event_id"]})

    def test_global_candidates_link_articles_on_opposite_sides_of_batches(self):
        rows = [
            self.article(str(i), f"Council Wellington flood map district {i}")
            for i in range(20)
        ]
        model = PairModel()
        result = self.group(rows, model)
        self.assertGreater(len(model.calls), 1)
        self.assertTrue(all(len(data["pairs"]) <= 12 for _, data, _ in model.calls))
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result[0]["source_ids"]), {str(i) for i in range(20)})
        self.assertTrue(
            all(task == "compare_event_pairs" for task, _, _ in model.calls)
        )

    def test_lexical_similarity_never_merges_a_rejected_pair(self):
        model = PairModel(lambda pair: {"same_event": False, "novelty": "new"})
        result = self.group([self.article("a"), self.article("b")], model)
        self.assertEqual(len(result), 2)
        self.assertEqual({e["novelty"] for e in result}, {"new"})

    def test_no_distinctive_overlap_preserves_singletons_without_model_calls(self):
        model = PairModel()
        result = self.group(
            [
                self.article("a", "Orion telescope discovery"),
                self.article("b", "Parliament tax vote"),
            ],
            model,
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(model.calls, [])

    def test_earliest_history_baseline_controls_novelty_and_keeps_other_history_ids(
        self,
    ):
        history = {
            "stories": [
                {
                    "event_id": "first",
                    "title": "Council flood map",
                    "summary": "Council flood map",
                    "sources": [{"id": "a"}],
                },
                {
                    "event_id": "second",
                    "title": "Council flood map",
                    "summary": "Council flood map",
                    "sources": [{"id": "a"}],
                },
            ]
        }

        def decision(pair):
            return {
                "same_event": True,
                "novelty": "repeat" if pair["right"]["id"] == "h1" else "update",
                "change": "" if pair["right"]["id"] == "h1" else "A new approval.",
            }

        event = self.group([self.article("a")], PairModel(decision), history)[0]
        self.assertEqual(event["event_id"], "first")
        self.assertEqual(event["novelty"], "repeat")
        self.assertEqual(event["previous_event_ids"], ["first", "second"])
        self.assertEqual(event["change"], "")

    def test_update_requires_concrete_change_and_valid_pair_partition(self):
        history = {
            "stories": [
                {
                    "event_id": "old",
                    "title": "Old",
                    "summary": "Old",
                    "sources": [{"id": "a"}],
                }
            ]
        }
        with self.assertRaises(ValueError):
            self.group(
                [self.article("a")],
                PairModel(lambda pair: {"same_event": True, "novelty": "update"}),
                history,
            )
        model = PairModel(
            lambda pair: {
                "same_event": True,
                "novelty": "update",
                "change": "The council reversed the decision.",
            }
        )
        self.assertEqual(
            self.group([self.article("a")], model, history)[0]["novelty"], "update"
        )

    def test_invalid_pair_ids_duplicate_ids_and_nonboolean_verdict_are_rejected(self):
        from unittest.mock import Mock

        base = {
            "id": "p1",
            "same_event": True,
            "novelty": "new",
            "change": "",
            "reason": "Same incident.",
        }
        for response in [
            {"pairs": []},
            {"pairs": [{**base, "id": "unknown"}]},
            {"pairs": [base, base]},
            {"pairs": [{**base, "same_event": "yes"}]},
        ]:
            model = Mock()
            model.complete.return_value = response
            with self.subTest(response=response), self.assertRaises(ValueError):
                self.group([self.article("a"), self.article("b")], model)

    def test_current_current_update_metadata_is_projected_to_identity_only(self):
        model = PairModel(
            lambda pair: {
                "same_event": True,
                "novelty": "update",
                "change": "The patient made a later public appearance.",
            }
        )
        event = self.group([self.article("a"), self.article("b")], model)[0]
        self.assertEqual(set(event["source_ids"]), {"a", "b"})
        self.assertEqual(event["novelty"], "new")
        self.assertEqual(event["change"], "")

    def test_historical_repeat_cannot_supply_nonempty_change(self):
        history = {
            "stories": [
                {
                    "event_id": "old",
                    "title": "Old",
                    "summary": "Old",
                    "sources": [{"id": "a"}],
                }
            ]
        }
        model = PairModel(
            lambda pair: {
                "same_event": True,
                "novelty": "repeat",
                "change": "Unjustified change.",
            }
        )
        with self.assertRaises(ValueError):
            self.group([self.article("a")], model, history)

    def test_callback_can_validate_real_response_before_retaining_normalized_rows(self):
        from src.news.grouping import group_events_bounded
        from unittest.mock import Mock

        retained = []

        def compare(inputs, validate_response):
            rows = validate_response(
                {
                    "pairs": [
                        {
                            "id": inputs[0]["id"],
                            "same_event": True,
                            "reason": "Explicit same incident.",
                            "novelty": "update",
                            "change": "Later action.",
                        }
                    ]
                }
            )
            retained.extend(rows)
            return rows

        model = Mock()
        event = group_events_bounded(
            [self.article("a"), self.article("b")], model, {}, compare_batch=compare
        )[0]
        model.complete.assert_not_called()
        self.assertEqual(retained[0]["novelty"], "new")
        self.assertEqual(retained[0]["change"], "")
        self.assertEqual(set(event["source_ids"]), {"a", "b"})

    def test_callback_cannot_bypass_pair_validation(self):
        from src.news.grouping import group_events_bounded
        from unittest.mock import Mock

        def compare(inputs, validate_response):
            return [
                {
                    "id": inputs[0]["id"],
                    "same_event": "yes",
                    "reason": "Invalid boolean.",
                }
            ]

        with self.assertRaises(ValueError):
            group_events_bounded(
                [self.article("a"), self.article("b")],
                Mock(),
                {},
                compare_batch=compare,
            )

    def test_model_only_receives_short_node_references(self):
        model = PairModel()
        self.group([self.article("a" * 64), self.article("b" * 64)], model)
        import json

        payload = json.dumps(model.calls[0][1])
        self.assertNotIn("a" * 64, payload)
        self.assertNotIn("b" * 64, payload)
        self.assertIn("n1", payload)

    def test_representative_prefers_substantive_grounded_description(self):
        a = self.article("a", "Council flood map")
        b = self.article(
            "b", "Council flood map establishes new boundaries after the council vote."
        )
        event = self.group([a, b])[0]
        self.assertEqual(event["representative_id"], "b")

    def test_empty_inputs_do_not_call_model(self):
        model = PairModel()
        self.assertEqual(self.group([], model), [])
        self.assertEqual(model.calls, [])
