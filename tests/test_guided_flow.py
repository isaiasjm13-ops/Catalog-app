from __future__ import annotations

import unittest

from perfect_catalog.guided_flow import next_step

EMPTY = {
    "intake_count": 0, "pending_review_count": 0, "pending_image_count": 0,
    "materialize_image_count": 0, "draft_release_count": 0, "published_release_count": 0,
}
PLAN = {"import_plan_id": "plan-1", "pending_count": 3}


def _states(step):
    return [item["state"] for item in step["progress"]]


class NextStepTests(unittest.TestCase):
    def test_nothing_loaded_starts_with_upload(self) -> None:
        step = next_step(EMPTY, [])
        self.assertEqual(step["stage"], "cargar")
        self.assertEqual(step["action_href"], "/operator/simple")
        self.assertEqual(_states(step), ["current", "todo", "todo"])

    def test_pending_identities_point_to_the_first_pending_plan(self) -> None:
        resolved = {"import_plan_id": "plan-0", "pending_count": 0}
        step = next_step({**EMPTY, "pending_review_count": 3}, [resolved, PLAN])
        self.assertEqual(step["stage"], "revisar")
        self.assertEqual(step["action_href"], "/operator/plans/plan-1?state=pending")
        self.assertIn("3 productos", step["title"])
        self.assertEqual(_states(step), ["done", "current", "todo"])

    def test_singular_wording_for_one_pending_product(self) -> None:
        step = next_step({**EMPTY, "pending_review_count": 1}, [{**PLAN, "pending_count": 1}])
        self.assertIn("1 producto por confirmar", step["title"])

    def test_pending_photos_send_to_images(self) -> None:
        step = next_step({**EMPTY, "pending_image_count": 2}, [{**PLAN, "pending_count": 0}])
        self.assertEqual(step["action_href"], "/operator/images")
        self.assertIn("2 fotos", step["title"])

    def test_drafts_send_to_deliver(self) -> None:
        step = next_step({**EMPTY, "draft_release_count": 1}, [{**PLAN, "pending_count": 0}])
        self.assertEqual(step["stage"], "entregar")
        self.assertIn("1 borrador ", step["title"] + " ")
        self.assertEqual(_states(step), ["done", "done", "current"])

    def test_published_catalog_marks_everything_done(self) -> None:
        step = next_step({**EMPTY, "published_release_count": 1}, [{**PLAN, "pending_count": 0}])
        self.assertEqual(step["stage"], "listo")
        self.assertEqual(_states(step), ["done", "done", "done"])
        self.assertEqual(step["secondary"]["href"], "/operator/simple")

    def test_resolved_plans_without_releases_suggest_creating_the_catalog(self) -> None:
        step = next_step(EMPTY, [{**PLAN, "pending_count": 0}])
        self.assertEqual(step["stage"], "entregar")
        self.assertEqual(step["action_href"], "/operator/catalogs")

    def test_pending_review_wins_over_drafts_and_published(self) -> None:
        step = next_step(
            {**EMPTY, "pending_review_count": 1, "draft_release_count": 1, "published_release_count": 1},
            [{**PLAN, "pending_count": 1}],
        )
        self.assertEqual(step["stage"], "revisar")


if __name__ == "__main__":
    unittest.main()
