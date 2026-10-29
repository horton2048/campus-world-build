"""Offline CLI regressions; synthetic records never contact an editor or network.

Run from the repository root:
    python3 -B -m unittest discover -s tests -v

These tests verify durable bookkeeping, not the truth of evidence or campus quality.
"""

from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "campus-world-build" / "scripts" / "campus_checkpoint.py"


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="campus-checkpoint-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "task"
        self.call("init", self.root, "--school", "Example University", "--campus", "Main Campus")

    def invoke(self, *arguments, document=None):
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *map(str, arguments)],
            input=json.dumps(document, ensure_ascii=False) if document is not None else None,
            text=True, capture_output=True, env=environment, timeout=30,
        )

    def call(self, *arguments, document=None, accepted=True):
        process = self.invoke(*arguments, document=document)
        self.assertEqual(process.returncode, 0 if accepted else 2, (process.stdout, process.stderr))
        self.assertNotIn("Traceback", process.stderr)
        return json.loads(process.stdout if accepted else process.stderr)

    def put(self, kind, record_id, document, revision=0, accepted=True):
        return self.call(
            "put", self.root, kind, record_id, "--file", "-", "--expected-revision", revision,
            document=document, accepted=accepted,
        )

    def get(self, kind, record_id):
        return self.call("get", self.root, kind, record_id)

    @staticmethod
    def item(name="Library"):
        return {"campusName": name, "kind": "building", "result": "not-done",
                "geometryCoverage": "not-started", "checks": {}}

    @staticmethod
    def job():
        return {"intent": "Import one immutable model snapshot", "fingerprint": "import:model-A:hash-A",
                "target": "asset:model-A", "operation": "import", "status": "prepared",
                "sceneMutation": False, "strategy": "native-import"}

    @staticmethod
    def terminal_observation(status="failed"):
        return {"status": status, "terminal": True, "source": "synthetic tool fixture",
                "observedAt": "2026-01-01T00:00:00Z", "evidence": ["fixture terminal result"]}

    def completed_item(self, name="Library"):
        required = self.get("project", "main")["document"]["requiredChecks"]
        return dict(self.item(name), geometryCoverage="whole-verified", result="meets-agreed-criteria",
                    mapEvidence=["fixture official map"],
                    photoSearch={"identityBasis": "fixture building identity", "sourcesViewed": ["fixture photo"]},
                    checks={key: {"status": "passed", "evidence": ["synthetic evidence " + key]} for key in required})

    def completion_proposal(self):
        project = self.get("project", "main")
        doc = copy.deepcopy(project["document"])
        doc.update(status="complete", completionEvidence=["fixture whole-map check"],
                   lastSavedState={"version": "fixture-v1", "verifiedAt": "fixture", "evidence": ["fixture native save readback"]})
        doc["environment"]["projectIdentity"] = "fixture-project-only"
        return doc, project["revision"]

    def test_restart_reads_committed_contract_and_init_cannot_reset_it(self):
        self.put("item", "B1", self.item())
        before = self.get("project", "main")
        self.call("init", self.root, "--school", "Different", "--campus", "Other", accepted=False)
        self.assertEqual(self.get("project", "main"), before)
        self.assertEqual(self.get("item", "B1")["document"]["campusName"], "Library")
        self.assertTrue((self.root / "RESUME.md").is_file())

    def test_same_revision_concurrent_updates_have_exactly_one_winner(self):
        self.put("item", "B1", self.item())

        def update(action):
            return self.invoke(
                "put", self.root, "item", "B1", "--file", "-", "--expected-revision", 1,
                document=dict(self.item(), nextAction=action),
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            processes = list(pool.map(update, ("find photos", "verify identity")))
        self.assertEqual(sorted(p.returncode for p in processes), [0, 2])
        self.assertEqual(self.get("item", "B1")["revision"], 2)
        before = self.get("item", "B1")
        self.put("item", "B1", self.item(), 1, accepted=False)
        self.assertEqual(self.get("item", "B1"), before)

    def test_prepared_and_unknown_operations_fence_duplicate_without_handle(self):
        original = self.job()
        self.put("job", "J1", original)
        self.put("job", "J2", original, accepted=False)
        unknown = dict(original, status="unknown")
        self.put("job", "J1", unknown, 1)
        # A different target does not bypass the same-intent guard.
        self.put("job", "J2", dict(original, target="asset:another-name"), accepted=False)
        # A renamed intent does not bypass an unresolved write to the same target.
        self.put("job", "J3", dict(original, fingerprint="new-fingerprint"), accepted=False)
        self.assertEqual(self.get("job", "J1")["document"]["status"], "unknown")
        self.put("job", "J4", dict(original, fingerprint="unrelated", target="asset:B"))

    def test_scene_has_one_unresolved_writer_but_research_generation_can_continue(self):
        scene_write = dict(self.job(), operation="place", fingerprint="place:A", target="scene:A", sceneMutation=True)
        self.put("job", "S1", scene_write)
        self.put("job", "S2", dict(scene_write, fingerprint="place:B", target="scene:B"), accepted=False)
        self.put("job", "G1", dict(self.job(), operation="generate", fingerprint="generate:C", target="generation:C"))

    def test_observation_timeout_does_not_turn_live_job_into_failure(self):
        original = self.job()
        self.put("job", "J1", original)
        running = dict(original, status="running", handle="fixture-original-handle")
        self.put("job", "J1", running, 1)
        unknown = dict(running, status="unknown", observation={
            "status": "unknown", "terminal": False, "source": "synthetic observation timeout",
            "observedAt": "2026-01-01T00:00:00Z", "evidence": ["observer timed out"],
        })
        self.put("job", "J1", unknown, 2)
        before = self.get("job", "J1")
        self.put("job", "J1", dict(unknown, status="failed"), 3, accepted=False)
        without_handle = dict(unknown)
        without_handle.pop("handle")
        self.put("job", "J1", without_handle, 3, accepted=False)
        self.assertEqual(self.get("job", "J1"), before)

    def test_source_snapshot_expected_change_and_baseline_are_frozen(self):
        original = dict(self.job(), inputSnapshot={"sourceSHA": "fixture-source-A", "path": "models/A.glb"},
                        expectedChange={"asset": "A", "instancesAdded": 1}, baseline={"sceneVersion": "v1"})
        self.put("job", "J1", original)
        self.put("job", "J1", dict(original, status="running", handle="original-task-handle"), 1)
        before = self.get("job", "J1")
        for field, changed in (("inputSnapshot", {"sourceSHA": "fixture-source-B", "path": "models/A.glb"}),
                               ("expectedChange", {"asset": "B", "instancesAdded": 2}),
                               ("baseline", {"sceneVersion": "v2"})):
            with self.subTest(field=field):
                altered = dict(before["document"], **{field: changed})
                self.put("job", "J1", altered, 2, accepted=False)
                del altered[field]
                self.put("job", "J1", altered, 2, accepted=False)
                self.assertEqual(self.get("job", "J1"), before)

    def test_terminal_history_is_immutable_and_repeated_failure_changes_method(self):
        original = self.job()
        self.put("job", "J1", original)
        failed = dict(original, status="failed", observation=self.terminal_observation())
        self.put("job", "J1", failed, 1)
        before = self.get("job", "J1")
        for altered in (
            dict(failed, status="prepared"), dict(failed, strategy="erase-old-method"),
            dict(failed, observation=self.terminal_observation("succeeded")),
        ):
            self.put("job", "J1", altered, 2, accepted=False)
        self.assertEqual(self.get("job", "J1"), before)
        retry = dict(original, retryOf="J1")
        self.put("job", "J2", retry)
        self.put("job", "J2", dict(retry, status="failed", observation=self.terminal_observation()), 1)
        self.put("job", "J3", dict(original, retryOf="J2"), accepted=False)
        self.put("job", "J3", dict(original, retryOf="J2", strategy="split-package-before-import"))

    def test_killed_sqlite_transaction_preserves_previous_checkpoint(self):
        self.put("item", "B1", self.item())
        before = self.get("item", "B1")
        # Simulate a process disappearing after a write, before its transaction commits.
        source = "\n".join((
            "import os, sqlite3, sys",
            "db = sqlite3.connect(sys.argv[1])",
            "db.execute('BEGIN IMMEDIATE')",
            "db.execute(\"UPDATE records SET revision=999 WHERE kind='item' AND id='B1'\")",
            "os._exit(9)",
        ))
        killed = subprocess.run([sys.executable, "-B", "-c", source, str(self.root / "campus-checkpoint.sqlite3")], timeout=30)
        self.assertEqual(killed.returncode, 9)
        self.assertEqual(self.get("item", "B1"), before)

    def test_151_items_resume_with_bounded_index_and_lossless_pagination(self):
        expected = {"B%03d" % index for index in range(151)}
        for record_id in sorted(expected):
            self.put("item", record_id, self.item(record_id))
        index = self.call("resume", self.root)
        self.assertEqual(index["unfinishedItems"]["total"], 151)
        self.assertEqual(len(index["unfinishedItems"]["records"]), 8)
        self.assertTrue(index["unfinishedItems"]["hasMore"])
        self.assertLess(len(json.dumps(index, ensure_ascii=False).encode("utf-8")), 18000)
        received = set()
        for offset in range(0, 151, 20):
            page = self.call("list", self.root, "item", "--limit", 20, "--offset", offset)
            received.update(row["id"] for row in page["records"])
            self.assertEqual(page["hasMore"], offset + 20 < 151)
        self.assertEqual(received, expected)
        self.assertEqual(self.get("item", "B150")["document"]["campusName"], "B150")

    def test_long_chinese_records_obey_whole_index_byte_budget_without_losing_state(self):
        long_text = "校园复刻对照资料" * 120
        active_ids = ["A%02d" % number + "x" * 93 for number in range(24)]
        excluded_ids = ["E%02d" % number + "x" * 93 for number in range(24)]
        job_ids = ["J%02d" % number + "x" * 93 for number in range(24)]
        project = self.get("project", "main")
        contract = copy.deepcopy(project["document"])
        contract.update(school=long_text, campus=long_text,
                        coordinateFrame={"explanation": long_text},
                        resourceBoundaries={"details": long_text}, budget={"details": long_text},
                        lastSavedState={"evidence": [long_text]}, nextQueue=active_ids,
                        questionsRequiringUserDecision=[long_text] * 4)
        contract["scope"].update(extent=long_text, exclude=excluded_ids, details=long_text)
        contract["map"].update(sources=[long_text], reviewEvidence=[long_text], itemIds=active_ids)
        contract["environment"].update(projectIdentity=long_text, restoreSteps=[long_text], authorization={"details": long_text})
        self.assertLess(len(json.dumps(contract, ensure_ascii=False).encode()), 65536)
        self.put("project", "main", contract, project["revision"])
        expected = {("project", "main"): contract}
        for record_id in active_ids + excluded_ids:
            doc = dict(self.item(long_text), nextAction=long_text, notes=long_text * 10)
            if record_id in excluded_ids:
                doc.update(scopeMembership="excluded", scopeChange={"requestedBy": "user", "reason": long_text, "evidence": [long_text]})
            self.put("item", record_id, doc)
            expected[("item", record_id)] = dict(doc, id=record_id)
        for record_id in job_ids:
            doc = dict(self.job(), intent=long_text, operation=long_text, fingerprint=long_text + record_id,
                       target=long_text + record_id, campusName=long_text, nextAction=long_text,
                       inputSnapshot={"notes": long_text * 10})
            self.put("job", record_id, doc)
            doc.update(status="unknown", handle=long_text + record_id)
            self.put("job", record_id, doc, 1)
            expected[("job", record_id)] = dict(doc, id=record_id)
        # The automatic short card from a put is bounded too, before any resume call.
        self.assertLessEqual((self.root / "RESUME.md").stat().st_size, 16384)
        for maximum, limit in ((16384, 8), (4096, 20), (4096, 1), (65536, 20)):
            with self.subTest(maximum=maximum, limit=limit):
                process = self.invoke("resume", self.root, "--limit", limit, "--max-bytes", maximum)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertLessEqual(len(process.stdout.encode("utf-8")), maximum)
                self.assertLessEqual((self.root / "RESUME.md").stat().st_size, maximum)
                index = json.loads(process.stdout)
                self.assertEqual(index["byteBudget"]["maxBytes"], maximum)
                self.assertTrue(index["byteBudget"]["indexOnly"])
                self.assertTrue(index["byteBudget"]["fieldsShortened"])
                if maximum == 4096 and limit == 20:
                    self.assertGreater(index["byteBudget"]["pageRecordsRemoved"], 0)
                self.assertFalse(index["mapReview"]["inventoryComplete"])
                self.assertEqual(index["mapReview"]["declaredItemCount"], 24)
                self.assertIn("get DIR", index["recordAccess"])
                for page_name in ("unresolvedJobs", "unfinishedItems", "excludedItems"):
                    page = index[page_name]
                    self.assertEqual(page["total"], 24)
                    self.assertEqual(page["returned"], len(page["records"]))
                    self.assertGreater(page["returned"], 0)
                    self.assertTrue(page["hasMore"])
                    self.assertEqual(page["nextOffset"], page["offset"] + page["returned"])
                    for row in page["records"]:
                        self.assertEqual(len(row["id"]), 96)
                        self.assertIsInstance(row["revision"], int)
        # A warning must fit inside the same budget, not get appended past it.
        (self.root / "RESUME.md").unlink()
        (self.root / "RESUME.md").mkdir()
        warning = self.invoke("resume", self.root, "--limit", 20, "--max-bytes", 4096)
        self.assertEqual(warning.returncode, 0, warning.stderr)
        self.assertLessEqual(len(warning.stdout.encode("utf-8")), 4096)
        warned_index = json.loads(warning.stdout)
        self.assertIn("resumeWarning", warned_index)
        self.assertGreater(warned_index["byteBudget"]["pageRecordsRemoved"], 0)
        (self.root / "RESUME.md").rmdir()
        # Every omitted identifier remains retrievable through explicit, lossless pagination.
        for kind, expected_ids in (("job", set(job_ids)), ("item", set(active_ids + excluded_ids))):
            found, offset = set(), 0
            while True:
                page = self.call("list", self.root, kind, "--limit", 7, "--offset", offset)
                found.update(row["id"] for row in page["records"])
                self.assertEqual(page["returned"], len(page["records"]))
                if not page["hasMore"]:
                    self.assertIsNone(page["nextOffset"])
                    break
                self.assertGreater(page["nextOffset"], offset)
                offset = page["nextOffset"]
            self.assertEqual(found, expected_ids)
        for key in (("project", "main"), ("item", active_ids[-1]), ("job", job_ids[-1])):
            self.assertEqual(self.get(*key)["document"], expected[key])
        exported = self.call("export", self.root)
        actual = {(row["kind"], row["id"]): row["document"]
                  for rows in exported["records"].values() for row in rows}
        self.assertEqual(actual, expected)

    def test_recovery_budget_bounds_are_rejected_without_mutation(self):
        before = self.get("project", "main")
        for maximum in (0, 4095, 65537):
            self.call("resume", self.root, "--max-bytes", maximum, accepted=False)
        self.assertEqual(self.get("project", "main"), before)

    def test_next_page_preserves_mixed_job_view_and_reports_collection_revision(self):
        specifications = (("A-terminal", "succeeded"), ("A-running", "running"),
                          ("Z-unknown", "unknown"), ("M-prepared", "prepared"))
        for record_id, status in specifications:
            doc = dict(self.job(), fingerprint="fixture:" + record_id, target="asset:" + record_id)
            self.put("job", record_id, doc)
            if status != "prepared":
                doc["status"] = status
                if status == "succeeded":
                    doc["observation"] = self.terminal_observation("succeeded")
                self.put("job", record_id, doc, 1)
        index = self.call("resume", self.root, "--limit", 1, "--max-bytes", 4096)
        page = index["unresolvedJobs"]
        self.assertEqual(page["view"], "unresolved")
        found = {row["id"] for row in page["records"]}
        while page["hasMore"]:
            command = page["nextPage"].split()
            command[1] = str(self.root)
            page = self.call(*command)
            self.assertEqual(page["eventSeq"], index["eventSeq"])
            self.assertEqual(page["view"], "unresolved")
            self.assertEqual(page["returned"], len(page["records"]))
            found.update(row["id"] for row in page["records"])
        self.assertEqual(found, {"A-running", "Z-unknown", "M-prepared"})
        self.assertEqual(self.call("list", self.root, "job")["total"], 4)
        # A write changes the collection revision; old offsets must be restarted by the Agent.
        new_job = dict(self.job(), fingerprint="fixture:new", target="asset:new")
        self.put("job", "B-new", new_job)
        changed = self.call("list", self.root, "job", "--view", "unresolved", "--limit", 1)
        self.assertGreater(changed["eventSeq"], index["eventSeq"])
        self.assertEqual(changed["offset"], 0)
        self.assertEqual(changed["total"], 4)
        self.call("list", self.root, "job", "--view", "unfinished", accepted=False)

    def test_budget_exhaustion_partial_geometry_and_unreviewed_map_cannot_complete(self):
        self.put("item", "B1", dict(self.item(), geometryCoverage="partial", result="meets-agreed-criteria"), accepted=False)
        self.put("item", "B1", dict(self.item(), checks={"grounding": "passed"}), accepted=False)
        project = self.get("project", "main")
        complete_item = dict(self.item(), geometryCoverage="whole-verified", result="meets-agreed-criteria",
                             mapEvidence=["fixture map B1"], photoSearch={"identityBasis": "fixture identity", "sourcesViewed": ["fixture photo"]},
                             checks={name: {"status": "passed", "evidence": ["synthetic evidence " + name]}
                                     for name in project["document"]["requiredChecks"]})
        self.put("item", "B1", complete_item)
        completed = copy.deepcopy(project["document"])
        completed.update(status="complete", budget={"status": "exhausted", "remaining": 0},
                         completionEvidence=["fixture map check"], lastSavedState={"version": "fixture-v1", "verifiedAt": "fixture", "evidence": ["fixture save readback"]})
        completed["environment"]["projectIdentity"] = "fixture-only"
        completed["map"] = {"inventoryComplete": False, "itemIds": ["B1"], "reviewEvidence": ["unreviewed fixture"]}
        self.put("project", "main", completed, project["revision"], accepted=False)
        self.assertEqual(self.get("project", "main"), project)

    def test_exclusion_requires_user_evidence_and_explicit_project_scope(self):
        self.put("item", "B2", self.item("Deferred Building"))
        excluded = dict(self.item("Deferred Building"), scopeMembership="excluded")
        self.put("item", "B2", excluded, 1, accepted=False)
        authorized = dict(excluded, scopeChange={"requestedBy": "user", "reason": "User removed this area", "evidence": ["fixture user request"]})
        self.put("item", "B2", authorized, 1, accepted=False)
        project = self.get("project", "main")
        doc = copy.deepcopy(project["document"])
        doc["scope"]["exclude"] = ["B2"]
        self.put("project", "main", doc, project["revision"])
        self.put("item", "B2", dict(authorized, scopeChange={"requestedBy": "user", "reason": "Removed", "evidence": []}), 1, accepted=False)
        self.put("item", "B2", dict(authorized, scopeChange={"requestedBy": "agent", "reason": "Easier to finish", "evidence": ["fixture note"]}), 1, accepted=False)
        self.assertEqual(self.get("item", "B2")["revision"], 1)
        self.put("item", "B2", authorized, 1)
        self.assertEqual(self.get("item", "B2")["document"]["scopeMembership"], "excluded")

    def test_excluded_history_does_not_prevent_completion_but_live_jobs_do_and_reactivation_works(self):
        self.put("item", "B1", self.completed_item())
        self.put("item", "B2", self.item("Deferred Building"))
        project = self.get("project", "main")
        doc = copy.deepcopy(project["document"])
        doc["scope"]["exclude"] = ["B2"]
        doc["map"] = {"inventoryComplete": True, "itemIds": ["B1"], "reviewEvidence": ["fixture updated scope review"]}
        self.put("project", "main", doc, project["revision"])
        excluded = dict(self.item("Deferred Building"), scopeMembership="excluded",
                        scopeChange={"requestedBy": "user", "reason": "User removed area B2", "evidence": ["fixture exclusion request"]})
        self.put("item", "B2", excluded, 1)
        pending = dict(self.job(), target="scene:B2", fingerprint="write:B2", operation="place", sceneMutation=True)
        self.put("job", "J2", pending)
        index = self.call("resume", self.root)
        self.assertEqual(index["inventory"]["totalStoredItems"], 2)
        self.assertEqual(index["inventory"]["inScopeCount"], 1)
        self.assertEqual(index["inventory"]["excludedCount"], 1)
        self.assertEqual(index["inventory"]["results"], {"meets-agreed-criteria": 1})
        self.assertEqual(index["unfinishedItems"]["total"], 0)
        self.assertEqual(index["excludedItems"]["records"][0]["id"], "B2")
        proposal, revision = self.completion_proposal()
        self.put("project", "main", proposal, revision, accepted=False)
        self.put("job", "J2", dict(pending, status="cancelled", observation=self.terminal_observation("cancelled")), 1)
        self.put("project", "main", proposal, revision)
        self.assertEqual(self.get("project", "main")["document"]["status"], "complete")
        # Reopen the project, then reactivate the retained item before removing its exclusion.
        completed = self.get("project", "main")
        self.put("project", "main", dict(completed["document"], status="active"), completed["revision"])
        active_project = self.get("project", "main")
        premature = copy.deepcopy(active_project["document"])
        premature["scope"]["exclude"] = []
        self.put("project", "main", premature, active_project["revision"], accepted=False)
        reactivated = dict(self.item("Deferred Building"), scopeMembership="in-scope",
                           scopeChange={"requestedBy": "user", "reason": "User restored area B2", "evidence": ["fixture restoration request"]})
        self.put("item", "B2", reactivated, 2)
        premature["map"].update(inventoryComplete=False, itemIds=["B1", "B2"])
        self.put("project", "main", premature, active_project["revision"])
        restored = self.call("resume", self.root)
        self.assertEqual(restored["inventory"]["excludedCount"], 0)
        self.assertEqual(restored["unfinishedItems"]["records"][0]["id"], "B2")
        history = [json.loads(event["document"]).get("scopeMembership", "in-scope")
                   for event in self.call("export", self.root)["events"] if event["kind"] == "item" and event["id"] == "B2"]
        self.assertEqual(history, ["in-scope", "excluded", "in-scope"])

    def test_invalid_json_types_and_large_records_roll_back_without_traceback(self):
        self.put("item", "B1", self.item())
        self.put("job", "J1", self.job())
        cases = (("project", "main", "status", []), ("project", "main", "map", {"itemIds": [None]}),
                 ("project", "main", "map", []), ("project", "main", "requiredChecks", [[[]]]),
                 ("item", "B1", "kind", {}), ("item", "B1", "checks", []),
                 ("item", "B1", "checks", {"grounding": {"status": []}}),
                 ("job", "J1", "status", []), ("job", "J1", "handle", {}),
                 ("job", "J1", "strategy", []), ("job", "J1", "observation", []))
        for kind, record_id, field, value in cases:
            with self.subTest(kind=kind, field=field, value=value):
                before = self.get(kind, record_id)
                malformed = dict(before["document"], **{field: value})
                self.put(kind, record_id, malformed, before["revision"], accepted=False)
                self.assertEqual(self.get(kind, record_id), before)
        self.put("item", "B2", dict(self.item(), huge="x" * 70000), accepted=False)
        self.call("get", self.root, "item", "B2", accepted=False)

    def test_exported_latest_events_match_all_authoritative_records(self):
        self.put("item", "B1", self.item())
        self.put("item", "B1", dict(self.item(), nextAction="inspect photos"), 1)
        self.put("job", "J1", self.job())
        exported = self.call("export", self.root)
        latest = {}
        for event in exported["events"]:
            self.assertEqual(hashlib.sha256(event["document"].encode()).hexdigest(), event["sha256"])
            latest[(event["kind"], event["id"])] = event
        records = [row for rows in exported["records"].values() for row in rows]
        self.assertEqual(len(records), len(latest))
        for row in records:
            event = latest[(row["kind"], row["id"])]
            self.assertEqual(row["revision"], event["revision"])
            self.assertEqual(row["document"], json.loads(event["document"]))
        destination = Path(self.temporary.name) / "export.json"
        self.call("export", self.root, "--file", destination)
        self.assertEqual(json.loads(destination.read_text())["records"], exported["records"])

    def test_unwritable_resume_index_does_not_discard_committed_database(self):
        # A directory at the output path reproduces a portable write failure,
        # including when the test process has permission to ignore chmod bits.
        (self.root / "RESUME.md").unlink()
        (self.root / "RESUME.md").mkdir()
        result = self.put("item", "B1", self.item())
        self.assertIn("resumeWarning", result)
        self.assertEqual(self.get("item", "B1")["revision"], 1)
        (self.root / "RESUME.md").rmdir()
        self.call("resume", self.root)
        self.assertTrue((self.root / "RESUME.md").is_file())


if __name__ == "__main__":
    unittest.main()
