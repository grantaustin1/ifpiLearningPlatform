from __future__ import annotations

from fastapi import Depends

from auth.dependencies import CurrentUser, requires_roles
from schemas import AIBuilderRequest, AIBuilderResponse
from services.ai_builder_service import generate_course

from . import ai_router


@ai_router.post("/course-builder", response_model=AIBuilderResponse)
async def ai_course_builder(
    body: AIBuilderRequest,
    current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN")),
):
    result = await generate_course(
        topic=body.topic, description=body.description or "",
        num_slides=body.num_slides, include_quiz=body.include_quiz,
        num_questions=body.num_questions,
    )
    return AIBuilderResponse(**result)
