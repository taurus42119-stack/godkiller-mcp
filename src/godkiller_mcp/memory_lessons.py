"""Lesson Memory store: 4-tier verified lessons SQLite engine."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

T = TypeVar("T")


class MemoryTier(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    WORKING = "working"


@dataclass
class Lesson:
    id: int
    project_id: str
    task_id: str
    content: str
    tags: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    task_passed: bool = True
    tier: str = "semantic"
    verified: bool = True


def _is_locked(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "locked" in msg or "busy" in msg


def _with_busy_retry(fn: Callable[[], T], *, attempts: int = 8, base_delay: float = 0.05) -> T:
    last: Optional[BaseException] = None
    for i in range(attempts):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            last = exc
            if not _is_locked(exc) or i == attempts - 1:
                raise
            time.sleep(base_delay * (2**i))
    assert last is not None
    raise last


class LessonMemory:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA busy_timeout=30000")
        except sqlite3.Error:
            pass
        self._init_db()

    def _init_db(self) -> None:
        def _create() -> None:
            with self.conn:
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS lessons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT,
                        task_id TEXT,
                        content TEXT,
                        tags TEXT,
                        evidence_ids TEXT,
                        task_passed INTEGER,
                        tier TEXT,
                        verified INTEGER
                    )
                """
                )

        _with_busy_retry(_create)

    def ingest_lesson(
        self,
        project_id: str,
        task_id: str,
        content: str,
        tags: Optional[List[str]] = None,
        evidence_ids: Optional[List[str]] = None,
        task_passed: bool = True,
        tier: str = "semantic",
        mark_verified: bool = True,
    ) -> Optional[Lesson]:
        # Failures are stored for fail-recipe injection (task_passed=0).
        # Praise-only fluff still filtered: empty / tiny content rejected.
        text = (content or "").strip()
        if len(text) < 8:
            return None

        tags_str = ",".join(tags) if tags else ""
        ev_str = ",".join(evidence_ids) if evidence_ids else ""

        # Unanchored semantic without evidence mark_verified check
        # Failures may be verified when mark_verified=True (operator attested).
        if task_passed:
            verified = 1 if mark_verified and (evidence_ids or tier != "semantic") else 0
        else:
            verified = 1 if mark_verified else 0

        def _insert() -> int:
            with self.conn:
                cursor = self.conn.execute(
                    """
                    INSERT INTO lessons (project_id, task_id, content, tags, evidence_ids, task_passed, tier, verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        project_id,
                        task_id,
                        text,
                        tags_str,
                        ev_str,
                        1 if task_passed else 0,
                        tier,
                        verified,
                    ),
                )
                return int(cursor.lastrowid or 0)

        lesson_id = _with_busy_retry(_insert)

        return Lesson(
            id=lesson_id,
            project_id=project_id,
            task_id=task_id,
            content=text,
            tags=tags or [],
            evidence_ids=evidence_ids or [],
            task_passed=task_passed,
            tier=tier,
            verified=bool(verified),
        )

    def retrieve(
        self, project_id: str, query: str, limit: int = 5
    ) -> List[Lesson]:
        def _query() -> List[Any]:
            cur = self.conn.cursor()
            return cur.execute(
                """
                SELECT id, project_id, task_id, content, tags, evidence_ids, task_passed, tier, verified
                FROM lessons
                WHERE project_id = ? AND task_passed = 1
                LIMIT ?
            """,
                (project_id, limit),
            ).fetchall()

        rows = _with_busy_retry(_query)

        results: List[Lesson] = []
        for r in rows:
            results.append(
                Lesson(
                    id=r[0],
                    project_id=r[1],
                    task_id=r[2],
                    content=r[3],
                    tags=r[4].split(",") if r[4] else [],
                    evidence_ids=r[5].split(",") if r[5] else [],
                    task_passed=bool(r[6]),
                    tier=r[7],
                    verified=bool(r[8]),
                )
            )

        # Basic query filtering
        q_words = query.lower().split()
        matched = [
            l
            for l in results
            if any(
                w in l.content.lower() or any(w in t.lower() for t in l.tags)
                for w in q_words
            )
        ]
        return matched if matched else results

    def retrieve_verified(
        self, project_id: str, query: str, limit: int = 5
    ) -> Dict[str, Any]:
        all_lessons = self.retrieve(project_id, query, limit=limit)
        verified_lessons = [l for l in all_lessons if l.verified]
        injected = [
            {"id": l.id, "content": l.content, "tags": l.tags}
            for l in verified_lessons
        ]

        return {
            "count_injected": len(injected),
            "injected": injected,
        }

    def retrieve_fail_recipes(
        self, project_id: str, query: str = "", limit: int = 5
    ) -> Dict[str, Any]:
        """Prior *failures* only (task_passed=0) — feed plan templates, never praise."""

        def _query() -> List[Any]:
            cur = self.conn.cursor()
            return cur.execute(
                """
                SELECT id, project_id, task_id, content, tags, evidence_ids, task_passed, tier, verified
                FROM lessons
                WHERE project_id = ? AND task_passed = 0 AND verified = 1
                ORDER BY id DESC
                LIMIT ?
            """,
                (project_id, limit * 3),
            ).fetchall()

        rows = _with_busy_retry(_query)
        lessons: List[Lesson] = []
        for r in rows:
            lessons.append(
                Lesson(
                    id=r[0],
                    project_id=r[1],
                    task_id=r[2],
                    content=r[3],
                    tags=r[4].split(",") if r[4] else [],
                    evidence_ids=r[5].split(",") if r[5] else [],
                    task_passed=bool(r[6]),
                    tier=r[7],
                    verified=bool(r[8]),
                )
            )
        q_words = [w for w in query.lower().split() if w]
        if q_words:
            matched = [
                l
                for l in lessons
                if any(
                    w in l.content.lower() or any(w in t.lower() for t in l.tags)
                    for w in q_words
                )
            ]
            lessons = matched if matched else lessons
        injected = [
            {"id": l.id, "content": l.content, "tags": l.tags, "task_passed": False}
            for l in lessons[:limit]
        ]
        return {"count_injected": len(injected), "injected": injected}

    def export_evidence_payload(self, lessons: List[Lesson]) -> Dict[str, Any]:
        """Serialize retrieved lessons for evidence attach / agent JSON."""
        return {
            "count": len(lessons),
            "lessons": [
                {
                    "id": l.id,
                    "project_id": l.project_id,
                    "task_id": l.task_id,
                    "content": l.content,
                    "tags": l.tags,
                    "evidence_ids": l.evidence_ids,
                    "task_passed": l.task_passed,
                    "tier": l.tier,
                    "verified": l.verified,
                }
                for l in lessons
            ],
        }

    def close(self) -> None:
        if self.conn:
            self.conn.close()
