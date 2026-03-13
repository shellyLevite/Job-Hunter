"""Job Matching Engine.

Pipeline for each (user_cv, job) pair:
  1. Extract skills from the CV and job description via Groq / Llama-3
  2. Compute a match score = |cv_skills ∩ job_skills| / |job_skills|
  3. Identify missing skills = job_skills - cv_skills
  4. Persist to job_matches table if score >= MATCH_THRESHOLD
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

from groq import AsyncGroq

from app.core.config import settings

logger = logging.getLogger(__name__)

_SKILL_EXTRACTION_PROMPT = """\
Extract a JSON array of technical skills, tools, and technologies from the
text below. Return ONLY the JSON array — no explanation, no markdown.
Example: ["Python", "FastAPI", "PostgreSQL", "Docker"]

Text:
{text}
"""


class MatchingEngine:
    def __init__(self):
        self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    async def _extract_skills(self, text: str) -> List[str]:
        """Call Llama-3.3-70b via Groq to extract a skill list from *text*."""
        if not text or not text.strip():
            return []
        try:
            resp = await self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": _SKILL_EXTRACTION_PROMPT.format(text=text[:4000])}
                ],
                temperature=0,
                max_tokens=512,
            )
            raw = resp.choices[0].message.content.strip()
            skills = json.loads(raw)
            return [s.strip().lower() for s in skills if isinstance(s, str)]
        except Exception as exc:
            logger.warning("Skill extraction failed: %s", exc)
            return []

    def _compute_score(
        self,
        cv_skills: List[str],
        job_skills: List[str],
    ) -> tuple[float, List[str]]:
        """
        Score = intersection / job_skills (coverage).
        Returns (score 0-1, missing_skills list).
        """
        if not job_skills:
            return 0.0, []

        cv_set  = set(cv_skills)
        job_set = set(job_skills)

        matched  = cv_set & job_set
        missing  = sorted(job_set - cv_set)
        score    = len(matched) / len(job_set)

        return round(score, 4), missing

    async def match(
        self,
        cv_text: str,
        job: Dict[str, Any],
    ) -> tuple[float, List[str]]:
        """Return (score, missing_skills) for a CV vs a job."""
        job_text = f"{job.get('title', '')} {job.get('description', '') or ''}"

        cv_skills, job_skills = await asyncio.gather(
            self._extract_skills(cv_text),
            self._extract_skills(job_text),
        )

        logger.debug(
            "CV skills (%d): %s", len(cv_skills), cv_skills[:10]
        )
        logger.debug(
            "Job skills (%d): %s", len(job_skills), job_skills[:10]
        )

        return self._compute_score(cv_skills, job_skills)


_engine: MatchingEngine | None = None


def get_matching_engine() -> MatchingEngine:
    global _engine
    if _engine is None:
        _engine = MatchingEngine()
    return _engine
