import asyncio
import json
import uuid
from datetime import datetime, timezone

import sentry_sdk
import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger()

GENERATION_SYSTEM_PROMPT = """You are an expert engineering question author for a technical assessment platform.
Generate realistic, practical engineering problems that test real skills.

For each question, provide:
- A clear, concise title
- A detailed scenario (3-5 paragraphs) describing a realistic problem with context
- Optional: supporting_code (code snippet relevant to the problem)
- Optional: supporting_logs (log output showing an issue)
- A list of relevant technologies (1-3 tags)

Format: Return a JSON array of question objects, each with:
{
  "title": "...",
  "scenario": "...",
  "supporting_code": "..." or null,
  "supporting_logs": "..." or null,
  "technologies": ["tech1", "tech2"]
}

Make questions that require deep thinking, tradeoff analysis, and real engineering judgment.
Do NOT make trivial quiz questions. Scenarios should be realistic workplace situations."""

QUALITY_CHECK_SYSTEM_PROMPT = """You are a quality reviewer for engineering assessment questions.
Review the following question and score it on:
1. Realism: Does it reflect a real workplace scenario? (0-10)
2. Clarity: Is the problem statement clear and unambiguous? (0-10)
3. Difficulty accuracy: Does it match the target difficulty? (0-10)
4. Testability: Can this question differentiate strong from weak candidates? (0-10)

Return JSON: {"realism": N, "clarity": N, "difficulty_accuracy": N, "testability": N, "overall": N, "pass": true/false}
A question passes if overall >= 7 and no single dimension < 5."""


@celery_app.task(
    bind=True,
    max_retries=2,
    name="app.workers.pipeline.generate_questions_task",
)
def generate_questions_task(
    self,
    run_id: str,
    category: str,
    difficulty: str,
    count: int = 5,
) -> dict:
    """Generate questions for the given category/difficulty using Claude."""

    async def _run():
        from app.core.ai import get_ai_simple_response
        from app.core.database import async_session_factory
        from app.models.pipeline import PipelineRun, PipelineStatus
        from app.repository.questions import QuestionRepository
        from sqlalchemy import select, update

        run_uuid = uuid.UUID(run_id)

        async with async_session_factory() as db:
            try:
                # Generate questions
                user_message = f"""Generate {count} {difficulty} difficulty {category.replace('_', ' ')} questions.
Each question should test a different aspect of {category.replace('_', ' ')}."""

                raw_response = await get_ai_simple_response(
                    system_prompt=GENERATION_SYSTEM_PROMPT,
                    user_message=user_message,
                    model="claude-sonnet-4-5",
                    max_tokens=4096,
                )

                # Parse the generated questions
                try:
                    # Find JSON array in response
                    start = raw_response.find("[")
                    end = raw_response.rfind("]") + 1
                    if start == -1 or end == 0:
                        raise ValueError("No JSON array found in response")
                    generated = json.loads(raw_response[start:end])
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error("pipeline_parse_error", error=str(e))
                    generated = []

                generated_count = len(generated)
                passed_count = 0
                held_count = 0
                failed_count = 0

                q_repo = QuestionRepository(db)

                for q_data in generated:
                    # Quality check
                    quality_check_msg = f"""Category: {category}
Difficulty: {difficulty}
Title: {q_data.get('title', '')}
Scenario: {q_data.get('scenario', '')}"""

                    try:
                        quality_response = await get_ai_simple_response(
                            system_prompt=QUALITY_CHECK_SYSTEM_PROMPT,
                            user_message=quality_check_msg,
                            model="claude-haiku-4-5",
                            max_tokens=256,
                        )
                        quality_data = json.loads(quality_response)
                        if not quality_data.get("pass", False):
                            failed_count += 1
                            continue
                    except Exception as e:
                        logger.warning("quality_check_failed", error=str(e))
                        failed_count += 1
                        continue

                    # Balance check: count existing questions in this bucket
                    existing_count_result = await db.execute(
                        select(__import__("sqlalchemy", fromlist=["func"]).func.count())
                        .select_from(__import__("app.models.question", fromlist=["Question"]).Question)
                        .where(
                            __import__("app.models.question", fromlist=["Question"]).Question.category == category,
                            __import__("app.models.question", fromlist=["Question"]).Question.difficulty == difficulty,
                            __import__("app.models.question", fromlist=["Question"]).Question.is_active == True,
                        )
                    )
                    existing_count = existing_count_result.scalar_one()

                    # Hold if bucket already has more than 50 questions
                    if existing_count >= 50:
                        held_count += 1
                        continue

                    # Simple dedup: check if title already exists (rough hash check)
                    from app.models.question import Question
                    title = q_data.get("title", "")
                    existing_title = await db.execute(
                        select(Question).where(Question.title == title)
                    )
                    if existing_title.scalar_one_or_none():
                        failed_count += 1
                        continue

                    # Create question (unvetted)
                    await q_repo.create(
                        title=title,
                        scenario=q_data.get("scenario", ""),
                        supporting_code=q_data.get("supporting_code"),
                        supporting_logs=q_data.get("supporting_logs"),
                        category=category,
                        technologies=q_data.get("technologies", []),
                        difficulty=difficulty,
                        is_vetted=False,
                        is_active=True,
                        generation_source="ai_pipeline",
                    )
                    passed_count += 1

                # Update pipeline run
                now = datetime.now(timezone.utc)
                await db.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id == run_uuid)
                    .values(
                        status=PipelineStatus.completed,
                        ended_at=now,
                        generated_count=generated_count,
                        passed_count=passed_count,
                        held_count=held_count,
                        failed_count=failed_count,
                    )
                )
                await db.commit()

                logger.info(
                    "pipeline_completed",
                    run_id=run_id,
                    generated=generated_count,
                    passed=passed_count,
                    held=held_count,
                    failed=failed_count,
                )
                return {
                    "status": "completed",
                    "generated": generated_count,
                    "passed": passed_count,
                    "held": held_count,
                    "failed": failed_count,
                }

            except Exception as e:
                from app.models.pipeline import PipelineStatus
                await db.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id == run_uuid)
                    .values(
                        status=PipelineStatus.failed,
                        ended_at=datetime.now(timezone.utc),
                        error_message=str(e),
                    )
                )
                await db.commit()
                raise

    try:
        return asyncio.run(_run())
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120)
        return {"status": "failed", "error": str(exc)}
