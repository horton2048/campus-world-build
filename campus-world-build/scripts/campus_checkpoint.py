#!/usr/bin/env python3
"""Durable, local bookkeeping for a campus build. Never calls the editor or a network.

The database is authoritative. RESUME.md is a disposable, bounded index. Records
contain evidence pointers supplied by the Agent; validation cannot authenticate
those pointers or prove that the actual campus is correct.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone


VERSION = 1
MAX_RECORD_BYTES = 65536
MAX_LIMIT = 20
DEFAULT_RESUME_BYTES = 16384
MIN_RESUME_BYTES = 4096
MAX_RESUME_BYTES = 65536
KINDS = ("project", "item", "job")
LIVE = {"prepared", "submitted", "running", "unknown"}
TERMINAL = {"succeeded", "failed", "cancelled"}
CORE_CHECKS = (
    "mapPlacement", "photoSimilarity", "wholeGeometry", "grounding",
    "entranceAndRoute", "nativeSave", "runtime",
)
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")


class Rejected(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def require(condition, message):
    if not condition:
        raise Rejected(message)


def short(value, length=240):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= length else text[:length] + "… [truncated; use get]"


def evidence(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(x, (str, dict)) and bool(x) for x in value
    )


def connect(root, create=False):
    root = Path(root).expanduser().resolve()
    if create:
        root.mkdir(parents=True, exist_ok=True)
    dbpath = root / "campus-checkpoint.sqlite3"
    require(create or dbpath.is_file(), "No checkpoint database. Run init first.")
    db = sqlite3.connect(str(dbpath), timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=FULL")
    if create:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS records (
                kind TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL,
                updated_at TEXT NOT NULL, document TEXT NOT NULL,
                PRIMARY KEY (kind,id)
            );
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                id TEXT NOT NULL, revision INTEGER NOT NULL, at TEXT NOT NULL,
                document TEXT NOT NULL, sha256 TEXT NOT NULL
            );
        """)
        db.execute("INSERT OR IGNORE INTO metadata VALUES ('schemaVersion',?)", (str(VERSION),))
    version = db.execute("SELECT value FROM metadata WHERE key='schemaVersion'").fetchone()
    require(version and version[0] == str(VERSION), "Unsupported checkpoint schema version.")
    return root, db


def row_doc(row):
    return {"kind": row["kind"], "id": row["id"], "revision": row["revision"],
            "updatedAt": row["updated_at"], "document": json.loads(row["document"])}


def fetch(db, kind, rid):
    row = db.execute("SELECT * FROM records WHERE kind=? AND id=?", (kind, rid)).fetchone()
    return row_doc(row) if row else None


def documents(db, kind):
    return [row_doc(x) for x in db.execute("SELECT * FROM records WHERE kind=? ORDER BY id", (kind,))]


def check_value(item, name):
    check = item.get("checks", {}).get(name, "not-checked")
    if isinstance(check, str):
        return check, item.get("checkEvidence", {}).get(name, []), item.get("checkReasons", {}).get(name)
    require(isinstance(check, dict), "Check must be a status string or object: " + name)
    return check.get("status"), check.get("evidence", []), check.get("reason")


def validate_item(doc, project):
    require(isinstance(doc.get("campusName"), str) and doc["campusName"].strip(), "item.campusName is required.")
    require(isinstance(doc.get("kind"), str) and doc["kind"] in {"building", "road", "gate", "sports-area", "water", "greenery", "facility", "other"}, "item.kind must identify the actual map element.")
    require(isinstance(doc.get("checks", {}), dict), "item.checks must be an object.")
    membership = doc.get("scopeMembership", "in-scope")
    require(isinstance(membership, str) and membership in {"in-scope", "excluded"}, "Invalid item.scopeMembership.")
    if membership == "excluded":
        change = doc.get("scopeChange", {})
        require(isinstance(change, dict) and change.get("requestedBy") == "user", "Excluding an item needs a user-requested scopeChange.")
        require(isinstance(change.get("reason"), str) and change["reason"].strip() and evidence(change.get("evidence")),
                "Excluding an item needs a nonempty reason and user-request evidence.")
        require(doc["id"] in project.get("scope", {}).get("exclude", []), "The project scope.exclude must explicitly contain the excluded stable item ID first.")
    require(isinstance(doc.get("result", "not-done"), str) and doc.get("result", "not-done") in {"not-done", "needs-correction", "meets-agreed-criteria"}, "Invalid item.result.")
    require(isinstance(doc.get("geometryCoverage", "not-started"), str) and doc.get("geometryCoverage", "not-started") in {
        "not-started", "placeholder", "partial", "whole-candidate", "whole-verified"
    }, "Invalid geometryCoverage.")
    for name in doc.get("checks", {}):
        state, proof, reason = check_value(doc, name)
        require(isinstance(state, str) and state in {"not-checked", "passed", "failed", "not-applicable"}, "Invalid check status: " + name)
        if state == "passed":
            require(evidence(proof), "Passed check needs its own evidence: " + name)
        if state == "not-applicable":
            require(isinstance(reason, str) and reason.strip(), "not-applicable needs a reason: " + name)
    if doc.get("result") == "meets-agreed-criteria":
        require(doc.get("geometryCoverage") == "whole-verified", "A placeholder/partial/candidate cannot meet agreed criteria.")
        checks = project.get("requiredChecks", list(CORE_CHECKS))
        require(checks, "Project requiredChecks must not be empty.")
        for name in checks:
            state, proof, reason = check_value(doc, name)
            require(state in {"passed", "not-applicable"}, "Item still lacks required check: " + name)
            require(evidence(proof) if state == "passed" else bool(reason), "Required check lacks evidence/reason: " + name)
        require(check_value(doc, "wholeGeometry")[0] == "passed", "Complete geometry must actually pass.")
        require(check_value(doc, "nativeSave")[0] == "passed", "Native save must actually pass.")
        require(evidence(doc.get("mapEvidence")), "Completed item needs map evidence.")
        if doc.get("kind") == "building":
            photos = doc.get("photoSearch", {})
            require(isinstance(photos, dict), "photoSearch must be an object.")
            require(photos.get("identityBasis") and evidence(photos.get("sourcesViewed")), "Building needs verified photo identity and viewed sources.")
            require(check_value(doc, "photoSimilarity")[0] == "passed", "Building photo similarity must pass.")


def validate_observation(doc):
    obs = doc.get("observation", {})
    require(isinstance(obs, dict), "job.observation must be an object.")
    require(obs.get("status") == doc["status"], "Terminal status needs a matching authoritative observation.status.")
    require(obs.get("source") and obs.get("observedAt") and evidence(obs.get("evidence")),
            "Terminal observation needs source, observedAt and evidence; a timeout is not terminal evidence.")
    require(obs.get("terminal") is True, "Terminal observation must explicitly confirm terminal=true.")


def validate_job(doc, old, others):
    for key in ("intent", "fingerprint", "target", "operation"):
        require(isinstance(doc.get(key), str) and doc[key].strip(), "job." + key + " is required.")
    state = doc.get("status")
    require(isinstance(state, str) and state in LIVE | TERMINAL, "Invalid job.status.")
    require(isinstance(doc.get("sceneMutation", False), bool), "sceneMutation must be boolean.")
    require(doc.get("handle") is None or isinstance(doc.get("handle"), str) and bool(doc["handle"].strip()), "handle must be a nonempty string or null.")
    require(isinstance(doc.get("strategy", "default"), str) and bool(doc.get("strategy", "default").strip()), "strategy must be a nonempty string.")
    require(doc.get("retryOf") is None or isinstance(doc.get("retryOf"), str) and bool(ID.fullmatch(doc["retryOf"])), "retryOf must be a job ID or null.")
    require(isinstance(doc.get("observation", {}), dict), "observation must be an object.")
    if old is None:
        require(state == "prepared", "New jobs must be durably prepared before invoking the external tool.")
    else:
        for key in ("fingerprint", "target", "operation", "intent", "sceneMutation", "strategy", "retryOf", "inputSnapshot", "expectedChange", "baseline"):
            default = False if key == "sceneMutation" else "default" if key == "strategy" else None
            require(json.dumps(doc.get(key, default), sort_keys=True, allow_nan=False) == json.dumps(old.get(key, default), sort_keys=True, allow_nan=False),
                    "Job identity is immutable; create a separately identified retry: " + key)
        previous = old["status"]
        require(previous not in TERMINAL or state == previous, "Terminal jobs cannot be reopened; use a new prepared retry.")
        require(previous not in TERMINAL or doc == old, "Terminal job snapshots are immutable; attach additional evidence to the item/project rather than rewriting the attempt.")
        require(not (previous in {"submitted", "running", "unknown"} and state == "prepared"), "Do not reset a possibly submitted job to prepared.")
        oldhandle = old.get("handle")
        require(not oldhandle or doc.get("handle") == oldhandle, "A known handle cannot be removed or replaced.")
    if state in TERMINAL:
        validate_observation(doc)
    if state in LIVE:
        for other in others:
            if other.get("status") not in LIVE:
                continue
            require(other.get("fingerprint") != doc["fingerprint"], "Unresolved job with the same fingerprint; inspect it before retrying.")
            require(other.get("target") != doc["target"], "Unresolved job targets the same object; inspect it before another write.")
            require(not (other.get("sceneMutation") and doc.get("sceneMutation")), "Another scene mutation is unresolved; keep one scene writer.")
    if old is None:
        retry = doc.get("retryOf")
        previous = [x for x in others if x.get("fingerprint") == doc["fingerprint"]]
        if previous:
            require(retry and any(x.get("id") == retry and x.get("status") in TERMINAL for x in previous),
                    "Repeated fingerprint needs retryOf pointing to a verified terminal attempt.")
        if retry:
            require(any(x.get("id") == retry and x.get("status") in TERMINAL for x in others), "retryOf must reference a verified terminal job.")
        unchanged_failures = [x for x in previous if x.get("status") == "failed" and x.get("strategy", "default") == doc.get("strategy", "default")]
        require(len(unchanged_failures) < 2, "Two failures on this fingerprint/strategy: change method and record the new strategy before retrying.")


def validate_project(doc, db):
    require(all(isinstance(doc.get(k), str) and doc[k].strip() for k in ("school", "campus")), "Project requires school and campus strings.")
    require(isinstance(doc.get("status", "active"), str) and doc.get("status", "active") in {"active", "waiting", "blocked", "complete"}, "Invalid project.status.")
    checks = doc.get("requiredChecks", list(CORE_CHECKS))
    require(isinstance(checks, list) and all(isinstance(x, str) for x in checks), "requiredChecks must be a list of check names.")
    require(set(CORE_CHECKS).issubset(set(checks)), "Keep all seven core checks; use not-applicable with a reason when genuinely irrelevant.")
    for key in ("map", "scope", "environment", "lastSavedState", "budget"):
        require(isinstance(doc.get(key, {}), dict), "project." + key + " must be an object.")
    for key in ("nextQueue", "questionsRequiringUserDecision"):
        require(isinstance(doc.get(key, []), list), "project." + key + " must be a list.")
    excluded_ids = doc.get("scope", {}).get("exclude", [])
    require(isinstance(excluded_ids, list) and all(isinstance(x, str) and ID.fullmatch(x) for x in excluded_ids), "scope.exclude must be a list of stable item IDs.")
    items = documents(db, "item")
    for row in items:
        if row["document"].get("scopeMembership", "in-scope") == "excluded":
            require(row["id"] in excluded_ids, "Reactivate the excluded item before removing its ID from project scope.exclude: " + row["id"])
    inventory = doc.get("map", {})
    require(isinstance(inventory.get("inventoryComplete", False), bool), "map.inventoryComplete must be boolean.")
    ids = inventory.get("itemIds", [])
    require(isinstance(ids, list) and all(isinstance(x, str) and ID.fullmatch(x) for x in ids), "map.itemIds must be a list of valid string IDs.")
    if doc.get("status") != "complete":
        return
    require(inventory.get("inventoryComplete") is True and evidence(inventory.get("reviewEvidence")),
            "Complete project needs a reviewed full-map inventory, not just completed selected objects.")
    active_items = [r for r in items if r["document"].get("scopeMembership", "in-scope") == "in-scope"]
    ids = inventory.get("itemIds")
    require(isinstance(ids, list) and ids and len(ids) == len(set(ids)), "Completed map needs its full, nonempty unique itemIds.")
    require(set(ids) == {r["id"] for r in active_items}, "Map inventory itemIds and current in-scope items must match exactly; excluded history remains stored.")
    require(not set(excluded_ids).intersection(ids), "Items declared in scope.exclude must be marked excluded before completion.")
    for row in active_items:
        require(row["document"].get("result") == "meets-agreed-criteria", "Incomplete item: " + row["id"])
        validate_item(row["document"], doc)
    require(not any(r["document"].get("status") in LIVE for r in documents(db, "job")), "Unresolved external jobs remain.")
    saved = doc.get("lastSavedState", {})
    require(saved.get("version") and saved.get("verifiedAt") and evidence(saved.get("evidence")), "Complete project needs last native save plus readback evidence.")
    require(doc.get("environment", {}).get("projectIdentity"), "Complete project needs verified project identity.")
    require(evidence(doc.get("completionEvidence")), "Complete project needs whole-campus completion evidence.")
    require(not doc.get("questionsRequiringUserDecision"), "Unresolved user decisions remain.")


def put(db, kind, rid, doc, expected):
    require(expected >= 0, "expected-revision must be nonnegative.")
    require(ID.fullmatch(rid), "ID must use 1–96 ASCII letters, digits, dots, hyphens or underscores.")
    require(kind != "project" or rid == "main", "Use the single project record ID main.")
    require(isinstance(doc, dict), "Record must be a JSON object.")
    require(doc.get("id", rid) == rid, "Record id disagrees with command ID.")
    doc = dict(doc, id=rid)
    encoded = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    require(len(encoded.encode("utf-8")) <= MAX_RECORD_BYTES, "Record exceeds 64 KiB; store large logs/images externally and keep pointers.")
    db.execute("BEGIN IMMEDIATE")
    try:
        old = fetch(db, kind, rid)
        rev = old["revision"] if old else 0
        require(rev == expected, "Revision conflict: expected %s, current %s. Re-read before merging." % (expected, rev))
        project = fetch(db, "project", "main")
        require(kind == "project" or project, "Initialize a project first.")
        if kind == "project":
            validate_project(doc, db)
        elif kind == "item":
            validate_item(doc, project["document"])
        else:
            others = [dict(r["document"], id=r["id"]) for r in documents(db, "job") if r["id"] != rid]
            validate_job(doc, old["document"] if old else None, others)
        if kind != "project" and project["document"].get("status") == "complete":
            raise Rejected("Project is complete. Set project.status=active before changing its work records.")
        stamp = now()
        db.execute("INSERT OR REPLACE INTO records VALUES (?,?,?,?,?)", (kind, rid, rev + 1, stamp, encoded))
        db.execute("INSERT INTO events(kind,id,revision,at,document,sha256) VALUES (?,?,?,?,?,?)",
                   (kind, rid, rev + 1, stamp, encoded, hashlib.sha256(encoded.encode()).hexdigest()))
        db.execute("COMMIT")
        return {"kind": kind, "id": rid, "revision": rev + 1, "updatedAt": stamp}
    except BaseException:
        db.execute("ROLLBACK")
        raise


def atomic_text(path, text):
    fd, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def summary_record(row):
    doc = row["document"]
    result = {"id": row["id"], "revision": row["revision"]}
    for key in ("campusName", "kind", "status", "target", "operation", "handle", "fingerprint", "result", "geometryCoverage", "nextAction"):
        if key in doc:
            result[key] = short(doc[key], 180)
    if row["kind"] == "item":
        result["scopeMembership"] = doc.get("scopeMembership", "in-scope")
    return result


def view_records(rows, kind, view="all"):
    if view == "all":
        return rows
    if view == "unresolved":
        require(kind == "job", "The unresolved view applies only to jobs.")
        selected = [r for r in rows if r["document"].get("status") in LIVE]
        return sorted(selected, key=lambda r: (0 if r["document"].get("status") in {"unknown", "prepared"} else 1, r["updatedAt"], r["id"]))
    require(kind == "item", "The unfinished/excluded views apply only to items.")
    if view == "excluded":
        return [r for r in rows if r["document"].get("scopeMembership", "in-scope") == "excluded"]
    require(view == "unfinished", "Unknown record view.")
    return [r for r in rows if r["document"].get("scopeMembership", "in-scope") == "in-scope"
            and r["document"].get("result") != "meets-agreed-criteria"]


def page_navigation(page):
    returned = len(page["records"])
    page.update(returned=returned, hasMore=page["offset"] + returned < page["total"],
                nextOffset=page["offset"] + returned if page["offset"] + returned < page["total"] else None)
    if "kind" in page:
        page["nextPage"] = ("list DIR %s --view %s --limit 1 --offset %s" % (page["kind"], page["view"], page["nextOffset"])) if page["hasMore"] else None


def paged(rows, limit, offset=0, kind=None, view="all"):
    records = [summary_record(x) for x in rows[offset:offset + limit]]
    result = {"total": len(rows), "offset": offset, "limit": limit, "records": records}
    if kind:
        result.update(kind=kind, view=view)
    page_navigation(result)
    return result


def json_text(document):
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def resume_markdown(snapshot):
    return ("# Campus build — recovery index\n\n"
            "Generated from campus-checkpoint.sqlite3. The database is authoritative; re-read actual tool/editor state before writing.\n\n"
            "```json\n" + json_text(snapshot) + "```\n")


def utf8_short(value, maximum):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    encoded = text.encode("utf-8")
    if len(encoded) <= maximum:
        return text
    suffix = "… [truncated; use get]"
    prefix = encoded[:max(0, maximum - len(suffix.encode("utf-8")))].decode("utf-8", errors="ignore")
    return prefix + suffix


def fit_resume(snapshot, maximum=DEFAULT_RESUME_BYTES):
    """Bound the complete JSON and Markdown index, never the authoritative records."""
    require(MIN_RESUME_BYTES <= maximum <= MAX_RESUME_BYTES, "max-bytes must be between 4096 and 65536.")
    result = json.loads(json.dumps(snapshot, ensure_ascii=False))
    pages = [result[name] for name in ("unresolvedJobs", "unfinishedItems", "excludedItems")]
    previous_budget = result.get("byteBudget", {})
    original_count = sum(len(page["records"]) for page in pages) + previous_budget.get("pageRecordsRemoved", 0)
    already_shortened = "[truncated; use get]" in json.dumps(result, ensure_ascii=False)
    budget = {"maxBytes": maximum, "indexOnly": True, "fieldsShortened": already_shortened,
              "detailFieldsOmitted": previous_budget.get("detailFieldsOmitted", False),
              "guidanceShortened": previous_budget.get("guidanceShortened", False), "pageRecordsRemoved": 0}
    result["byteBudget"] = budget

    def fits():
        for page in pages:
            page_navigation(page)
        budget["pageRecordsRemoved"] = original_count - sum(len(page["records"]) for page in pages)
        return max(len(json_text(result).encode("utf-8")), len(resume_markdown(result).encode("utf-8"))) <= maximum

    if fits():
        return result
    for field_maximum in (240, 120, 64, 32):
        for key, value in list(result["project"].items()):
            result["project"][key] = utf8_short(value, field_maximum)
        for key in ("sources", "reviewEvidence"):
            result["mapReview"][key] = utf8_short(result["mapReview"].get(key, ""), field_maximum)
        if "resumeWarning" in result:
            result["resumeWarning"] = utf8_short(result["resumeWarning"], field_maximum)
        for page in pages:
            for row in page["records"]:
                for key, value in list(row.items()):
                    if key not in {"id", "revision"} and isinstance(value, str):
                        row[key] = utf8_short(value, field_maximum)
        budget["fieldsShortened"] = True
        if fits():
            return result

    # A tight context budget receives identifiers/statuses; get retrieves the full record.
    for page in pages:
        page["records"] = [{key: row[key] for key in ("id", "revision", "status", "scopeMembership") if key in row}
                           for row in page["records"]]
    budget["detailFieldsOmitted"] = True
    if fits():
        return result
    # Keep at least one identifier from every nonempty page before simplifying the header.
    for page in reversed(pages):
        while len(page["records"]) > 1:
            page["records"].pop()
            if fits():
                return result
    result["project"] = {key: value for key, value in result["project"].items() if key in {"school", "campus", "status"}}
    result["projectDetailsOmitted"] = "get DIR project main returns the complete contract and current revision"
    result["recoveryOrder"] = [
        "Read SKILL.md, get DIR project main, then listed job/item IDs. Recheck actual editor identity/save and original task handles.",
        "prepared/unknown may already have written remotely. Query original intent/handle before conflicting writes; an observation timeout is not terminal.",
        "Use each page's nextPage command for omitted records; it preserves the same view and offset. This index starts no work or scheduler."
    ]
    budget["guidanceShortened"] = True
    require(fits(), "The minimum recovery index exceeds max-bytes; use a larger budget.")
    return result


def resume_snapshot(db, limit):
    projectrow = fetch(db, "project", "main")
    require(projectrow, "Missing project record.")
    project = projectrow["document"]
    jobs = documents(db, "job")
    live = view_records(jobs, "job", "unresolved")
    items = documents(db, "item")
    active_items = [r for r in items if r["document"].get("scopeMembership", "in-scope") == "in-scope"]
    excluded_items = [r for r in items if r["document"].get("scopeMembership", "in-scope") == "excluded"]
    unfinished = view_records(items, "item", "unfinished")
    counts = {}
    for r in active_items:
        status = r["document"].get("result", "not-done")
        counts[status] = counts.get(status, 0) + 1
    return {
        "schemaVersion": VERSION, "generatedAt": now(), "eventSeq": db.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0], "projectRevision": projectrow["revision"],
        "project": {key: short(project[key], 800) for key in (
            "school", "campus", "status", "scope", "coordinateFrame", "environment",
            "resourceBoundaries", "budget", "lastSavedState", "nextQueue", "questionsRequiringUserDecision"
        ) if key in project},
        "mapReview": {"inventoryComplete": project.get("map", {}).get("inventoryComplete", False),
                      "declaredItemCount": len(project.get("map", {}).get("itemIds", [])),
                      "sources": short(project.get("map", {}).get("sources", []), 600),
                      "reviewEvidence": short(project.get("map", {}).get("reviewEvidence", []), 600)},
        "inventory": {"totalStoredItems": len(items), "inScopeCount": len(active_items), "excludedCount": len(excluded_items), "inventoryComplete": project.get("map", {}).get("inventoryComplete", False),
                      "results": counts, "unfinishedCount": len(unfinished)},
        "unresolvedJobs": paged(live, limit, kind="job", view="unresolved"),
        "unfinishedItems": paged(unfinished, limit, kind="item", view="unfinished"),
        "excludedItems": paged(excluded_items, limit, kind="item", view="excluded"),
        "recoveryOrder": [
            "Read project/main and the listed job/item records before writing; this summary is only an index.",
            "Check actual editor project identity, last save and original job handles/intent. A stale note is not live-state evidence.",
            "prepared or unknown can already have caused a write. Missing handles and observation timeouts do not authorize a duplicate.",
            "Observe every unresolved/conflicting job before new scene writes. Follow the matching page's nextPage when hasMore=true.",
            "Then select the next full-map gap inside the agreed budget; checkpoint each external mutation before and after.",
            "No process is resumed, external action made, or scheduler created by this command."
        ],
        "recordAccess": "get DIR {project|item|job} ID; follow nextPage or list DIR KIND --view VIEW --limit 1 --offset N",
        "validationBoundary": "Checks validate record structure, not the truth of supplied evidence or the real world's quality."
    }


def resume(db, limit, max_bytes=DEFAULT_RESUME_BYTES):
    db.execute("BEGIN")
    try:
        return fit_resume(resume_snapshot(db, limit), max_bytes)
    finally:
        db.execute("COMMIT")


def write_resume(root, snapshot):
    atomic_text(root / "RESUME.md", resume_markdown(snapshot))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a new local checkpoint; never overwrites an existing project")
    init.add_argument("directory")
    init.add_argument("--school", required=True)
    init.add_argument("--campus", required=True)
    update = commands.add_parser("put", help="Replace one record transactionally, requiring its current revision")
    update.add_argument("directory")
    update.add_argument("kind", choices=KINDS)
    update.add_argument("id")
    update.add_argument("--file", required=True, help="UTF-8 JSON record, or - for stdin")
    update.add_argument("--expected-revision", type=int, required=True)
    get = commands.add_parser("get")
    get.add_argument("directory")
    get.add_argument("kind", choices=KINDS)
    get.add_argument("id")
    listing = commands.add_parser("list")
    listing.add_argument("directory")
    listing.add_argument("kind", choices=KINDS)
    listing.add_argument("--limit", type=int, default=8)
    listing.add_argument("--offset", type=int, default=0)
    listing.add_argument("--view", choices=("all", "unresolved", "unfinished", "excluded"), default="all",
                         help="Match a recovery-index view and its pagination order; default all preserves full history")
    recovery = commands.add_parser("resume", help="Write a bounded RESUME.md index and print it as JSON")
    recovery.add_argument("directory")
    recovery.add_argument("--limit", type=int, default=8)
    recovery.add_argument("--max-bytes", type=int, default=DEFAULT_RESUME_BYTES,
                          help="Whole UTF-8 recovery index budget, including Markdown wrapper (4096–65536; default 16384)")
    export = commands.add_parser("export", help="Export full records and append-only event history as JSON")
    export.add_argument("directory")
    export.add_argument("--file", help="Optional exact output path; otherwise print JSON")
    args = parser.parse_args(argv)
    if hasattr(args, "limit"):
        require(1 <= args.limit <= MAX_LIMIT, "limit must be between 1 and 20.")
    if hasattr(args, "offset"):
        require(args.offset >= 0, "offset must be nonnegative.")
    if hasattr(args, "max_bytes"):
        require(MIN_RESUME_BYTES <= args.max_bytes <= MAX_RESUME_BYTES, "max-bytes must be between 4096 and 65536.")
    root, db = connect(args.directory, args.command == "init")
    try:
        if args.command == "init":
            require(not fetch(db, "project", "main"), "Project already exists; init does not reset it.")
            result = put(db, "project", "main", {
                "school": args.school, "campus": args.campus, "status": "active",
                "scope": {"extent": "whole-campus", "phase": "baseline-replication", "preserve": [], "exclude": []},
                "map": {"sources": [], "inventoryComplete": False, "itemIds": [], "reviewEvidence": []},
                "coordinateFrame": {}, "environment": {"projectIdentity": None, "restoreSteps": [], "authorization": {}},
                "resourceBoundaries": {}, "budget": {"status": "unknown", "rule": "Research first; confirm actual cost boundary before paid actions."},
                "lastSavedState": {}, "requiredChecks": list(CORE_CHECKS), "nextQueue": [],
                "questionsRequiringUserDecision": []
            }, 0)
        elif args.command == "put":
            if args.file == "-":
                raw = sys.stdin.buffer.read(MAX_RECORD_BYTES + 1)
            else:
                with open(args.file, "rb") as stream:
                    raw = stream.read(MAX_RECORD_BYTES + 1)
            require(len(raw) <= MAX_RECORD_BYTES, "Input exceeds 64 KiB.")
            doc = json.loads(raw.decode("utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(Rejected("Nonfinite JSON number: " + x)))
            result = put(db, args.kind, args.id, doc, args.expected_revision)
        elif args.command == "get":
            result = fetch(db, args.kind, args.id)
            require(result is not None, "No such record.")
        elif args.command == "list":
            db.execute("BEGIN")
            try:
                result = paged(view_records(documents(db, args.kind), args.kind, args.view), args.limit, args.offset, args.kind, args.view)
                result["eventSeq"] = db.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]
            finally:
                db.execute("COMMIT")
        elif args.command == "resume":
            result = resume(db, args.limit, args.max_bytes)
        else:
            db.execute("BEGIN")
            try:
                result = {"schemaVersion": VERSION, "exportedAt": now(),
                          "records": {kind: documents(db, kind) for kind in KINDS},
                          "events": [dict(row) for row in db.execute("SELECT * FROM events ORDER BY seq")]}
            finally:
                db.execute("COMMIT")
            if args.file:
                target = Path(args.file).expanduser().resolve()
                require(target != root / "campus-checkpoint.sqlite3", "Export cannot overwrite the database.")
                atomic_text(target, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
                result = {"exportedFile": str(target), "events": len(result["events"])}
        if args.command in {"init", "put", "resume"}:
            try:
                write_resume(root, result if args.command == "resume" else resume(db, 8))
            except OSError as exc:
                result["resumeWarning"] = "Database saved; disposable RESUME.md could not be refreshed: " + str(exc)
                if args.command == "resume":
                    result = fit_resume(result, args.max_bytes)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Rejected, ValueError, TypeError, AttributeError, KeyError, RecursionError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
