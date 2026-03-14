"""Job Matching Engine.

Search-time pipeline:
  1. CV skills are extracted once per CV (in-memory cache, 1 h TTL)
  2. Job skills are batch-extracted: up to 10 jobs per Groq call
  3. Score  = |cv_skills \u2229 job_skills| / |job_skills|
  4. Jobs are tagged strong_match if score >= threshold
  5. Results are sorted by score descending
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from groq import AsyncGroq

from backend.core.config import settings

logger = logging.getLogger(__name__)

_SKILL_EXTRACT_PROMPT = """\
Extract a JSON array of technical skills, tools, and technologies from the \
text below. Return ONLY the JSON array - no explanation, no markdown.
Example: ["Python", "FastAPI", "PostgreSQL", "Docker"]

Text:
{text}
"""

_BATCH_SKILL_PROMPT = """\
For each job below, extract a JSON array of technical skills, tools, and \
technologies. Return ONLY a JSON array of arrays - one inner array per job, \
in the same order. No explanation, no markdown.
Example for 2 jobs: [["Python", "FastAPI"], ["React", "TypeScript"]]

{jobs_text}
"""

# cv_id -> {"skills": list[str], "expires": float}
_CV_SKILL_CACHE: dict[str, dict] = {}
_CV_SKILL_TTL = 3600  # 1 hour


class MatchingEngine:
    def __init__(self) -> None:
        self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    # -- Single-text extraction ------------------------------------------------

    async def extract_skills(self, text: str) -> list[str]:
        """Extract skills from arbitrary text via a single Groq call."""
        if not text or not text.strip():
            return []
        try:
            resp = await self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": _SKILL_EXTRACT_PROMPT.format(text=text[:4000])}
                ],
                temperature=0,
                max_tokens=512,
            )
            raw = resp.choices[0].message.content.strip()
            skills = json.loads(raw)
            return [s.strip().lower() for s in skills if isinstance(s, str)]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skill extraction failed: %s", exc)
            return []

    # -- CV skill cache --------------------------------------------------------

    async def get_cv_skills(self, cv_id: str, cv_text: str) -> list[str]:
        """Return CV skills from the in-memory cache, extracting once if needed."""
        cached = _CV_SKILL_CACHE.get(cv_id)
        if cached and cached["expires"] > time.monotonic():
            return cached["skills"]
        skills = await self.extract_skills(cv_text)
        _CV_SKILL_CACHE[cv_id] = {
            "skills": skills,
            "expires": time.monotonic() + _CV_SKILL_TTL,
        }
        logger.debug("CV %s: extracted %d skills", cv_id, len(skills))
        return skills

    # -- Batch job extraction --------------------------------------------------

    async def _batch_extract_job_skills(self, job_texts: list[str]) -> list[list[str]]:
        """Extract skills for up to 10 job texts in a single Groq call."""
        if not job_texts:
            return []
        labeled = "\n\n".join(
            f"Job {i}:\n{t[:600]}" for i, t in enumerate(job_texts)
        )
        try:
            resp = await self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": _BATCH_SKILL_PROMPT.format(jobs_text=labeled)}
                ],
                temperature=0,
                max_tokens=1024,
            )
            raw = resp.choices[0].message.content.strip()
            parsed = json.loads(raw)
            result: list[list[str]] = []
            for item in parsed:
                if isinstance(item, list):
                    result.append([s.strip().lower() for s in item if isinstance(s, str)])
                else:
                    result.append([])
            while len(result) < len(job_texts):
                result.append([])
            return result[: len(job_texts)]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Batch skill extraction failed: %s", exc)
            return [[] for _ in job_texts]

    # -- Scoring ---------------------------------------------------------------

    def _score(
        self, cv_skills: list[str], job_skills: list[str]
    ) -> tuple[float, list[str]]:
        if not job_skills:
            return 0.0, []
        cv_set = set(cv_skills)
        job_set = set(job_skills)
        missing = sorted(job_set - cv_set)
        score = round(len(cv_set & job_set) / len(job_set), 4)
        return score, missing

    # -- Public ranking --------------------------------------------------------

    async def rank_jobs(
        self,
        cv_skills: list[str],
        jobs: list[dict[str, Any]],
        threshold: float = 0.40,
    ) -> list[dict[str, Any]]:
        """
        Score all jobs against cv_skills using batched Groq calls (10 per batch).
        Returns job dicts enriched with score, strong_match, missing_skills,
        sorted by score descending.
        """
        BATCH = 10
        job_texts = [
            f"{j.get('title', '')} {j.get('description', '') or ''}" for j in jobs
        ]
        all_job_skills: list[list[str]] = []
        for i in range(0, len(job_texts), BATCH):
            batch = await self._batch_extract_job_skills(job_texts[i : i + BATCH])
            all_job_skills.extend(batch)

        results = []
        for job, job_skills in zip(jobs, all_job_skills):
            score, missing = self._score(cv_skills, job_skills)
            results.append(
                {
                    **job,
                    "score": score,
                    "strong_match": score >= threshold,
                    "missing_skills": missing,
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results


_engine: MatchingEngine | None = None


def get_matching_engine() -> MatchingEngine:
    global _engine
    if _engine is None:
        _engine = MatchingEngine()
    return _engine
