"""Mind-map extraction from course content (Iter 27b).

Uses the Emergent LLM key to convert a course + its slides into a nodes+edges
graph the frontend renders with react-flow. Deliberately keeps the schema
simple (one root, N topic nodes, optional sub-topics) so react-flow's
default hierarchical layout works out of the box.

Nothing is persisted server-side — mind maps are ephemeral view state.
The caller can save the JSON blob to `Course.metadata_json` or an
external tool if they want; not the concern of this service.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import List

from fastapi import HTTPException

from core.config import settings

logger = logging.getLogger("ifpi.ai.mindmap")

_SYSTEM_PROMPT = (
    "You are IFPI's course structure analyst. Turn course content into a "
    "hierarchical mind-map. Return STRICT JSON only — no markdown, no prose."
)


def _prompt(course_title: str, slide_dicts: List[dict], max_topics: int) -> str:
    excerpt = "\n\n".join(
        f"[Slide {i + 1}] {s.get('title','')}\n{(s.get('content') or '')[:600]}"
        for i, s in enumerate(slide_dicts)
    )
    return (
        f'Analyse the course "{course_title}" and produce a mind map with '
        f'a single ROOT node, up to {max_topics} TOPIC nodes (major themes), '
        f'and up to 3 SUB-TOPIC children per topic (key concepts).\n\n'
        f'Each node id MUST be unique. Position layout is not needed — the '
        f'client computes coordinates. Do NOT invent facts.\n\n'
        f'Course material:\n\n{excerpt}\n\n'
        f'Output ONLY:\n'
        '{\n'
        '  "root": { "id": "root", "label": "Short course title" },\n'
        '  "topics": [\n'
        '    { "id": "t1", "label": "Topic 1",\n'
        '      "children": [ { "id": "c1a", "label": "Concept 1a" } ] }\n'
        '  ]\n'
        '}'
    )


async def generate_mindmap(course_title: str, slides: List[dict],
                            max_topics: int = 6) -> dict:
    """Return `{root, topics}`. Raises HTTPException on any failure."""
    if not settings.emergent_llm_key:
        raise HTTPException(status_code=503, detail="Mind map requires EMERGENT_LLM_KEY")
    if not slides:
        raise HTTPException(status_code=400, detail="Course has no slides to map")
    if not (1 <= max_topics <= 12):
        raise HTTPException(status_code=400, detail="max_topics must be 1-12")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError as e:
        logger.exception("emergentintegrations missing: %s", e)
        raise HTTPException(status_code=503, detail="Mind-map generator unavailable")

    chat = LlmChat(
        api_key=settings.emergent_llm_key,
        session_id=f"mindmap-{uuid.uuid4().hex}",
        system_message=_SYSTEM_PROMPT,
    ).with_model(settings.ai_builder_provider, settings.ai_builder_model)

    try:
        raw = await chat.send_message(UserMessage(text=_prompt(course_title, slides, max_topics)))
    except Exception as e:   # noqa: BLE001
        logger.exception("Mind-map LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Mind-map generation failed ({type(e).__name__})")

    text = (raw if isinstance(raw, str) else getattr(raw, "content", str(raw))).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.I).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.error("Mind-map returned non-JSON: %s", text[:400])
        raise HTTPException(status_code=502, detail="AI returned invalid JSON — please retry")

    # Normalise + sanity check
    root = parsed.get("root") or {}
    if not root.get("id") or not root.get("label"):
        raise HTTPException(status_code=502, detail="Mind-map missing root node — please retry")
    topics = parsed.get("topics") or []
    for t in topics[:max_topics]:
        t["label"] = str(t.get("label") or "")[:120]
        t["id"] = str(t.get("id") or f"t-{uuid.uuid4().hex[:6]}")
        kids = t.get("children") or []
        t["children"] = [
            {"id": str(k.get("id") or f"c-{uuid.uuid4().hex[:6]}"),
             "label": str(k.get("label") or "")[:120]}
            for k in kids[:3] if k.get("label")
        ]
    return {"root": {"id": str(root["id"]), "label": str(root["label"])[:120]},
            "topics": topics[:max_topics]}
