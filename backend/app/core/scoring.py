import json
import uuid
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.ai import get_ai_simple_response

logger = structlog.get_logger()

SCORING_SYSTEM_PROMPT = """You are a strict, objective engineering assessment scorer.
You will receive a question scenario, a candidate's response, and their AI assistant interaction history.
Score the candidate on four dimensions, each 0-100.

Scoring dimensions:
1. engineering_skill: Correctness, completeness, and depth of the technical answer
2. ai_collaboration: Whether the candidate used the AI assistant effectively (right questions, iterative refinement)
3. ai_trust_calibration: Whether the candidate appropriately trusted or pushed back on AI suggestions
4. engineering_judgement: Quality of tradeoff reasoning, edge-case awareness, and architectural decisions

Return ONLY a JSON object in this exact format:
{
  "engineering_skill": {"score": <0-100 integer>, "rationale": "<explanation>"},
  "ai_collaboration": {"score": <0-100 integer>, "rationale": "<explanation>"},
  "ai_trust_calibration": {"score": <0-100 integer>, "rationale": "<explanation>"},
  "engineering_judgement": {"score": <0-100 integer>, "rationale": "<explanation>"}
}

Be rigorous. A score of 50 means average. Only give high scores for genuinely strong work."""

DIFFICULTY_MODIFIERS = {
    "low": "This was a low-difficulty question. Apply a more lenient rubric — partial credit for reasonable approaches.",
    "medium": "This was a medium-difficulty question. Apply a standard rubric.",
    "high": "This was a high-difficulty question. Apply a strict rubric — only award high scores for excellent depth.",
}


async def score_session(session_id: uuid.UUID, db: AsyncSession) -> dict:
    """Score all questions in a session and return aggregated scores."""
    from app.models.session import SessionQuestion, AssessmentSession
    from app.models.question import Question

    # Load session and questions
    session_result = await db.execute(
        select(AssessmentSession).where(AssessmentSession.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise ValueError(f"Session {session_id} not found")

    sq_result = await db.execute(
        select(SessionQuestion, Question)
        .join(Question, SessionQuestion.question_id == Question.id)
        .where(SessionQuestion.session_id == session_id)
        .order_by(SessionQuestion.order_index)
    )
    question_rows = sq_result.all()

    if not question_rows:
        return {
            "engineering_skill": 0.0,
            "ai_collaboration": 0.0,
            "ai_trust_calibration": 0.0,
            "engineering_judgement": 0.0,
            "total_score": 0.0,
        }

    dimension_totals = {
        "engineering_skill": 0.0,
        "ai_collaboration": 0.0,
        "ai_trust_calibration": 0.0,
        "engineering_judgement": 0.0,
    }

    difficulty_modifier = DIFFICULTY_MODIFIERS.get(session.difficulty.value, DIFFICULTY_MODIFIERS["medium"])

    scored_count = 0
    for sq, question in question_rows:
        response = sq.response_text or ""
        ai_log = json.dumps(sq.ai_interactions, indent=2) if sq.ai_interactions else "No AI interactions"

        user_message = f"""Question: {question.title}

Scenario: {question.scenario}

Candidate Response: {response}

AI Interaction Log:
{ai_log}

Difficulty modifier: {difficulty_modifier}"""

        try:
            raw_response = await get_ai_simple_response(
                system_prompt=SCORING_SYSTEM_PROMPT,
                user_message=user_message,
                model="claude-sonnet-4-5",
                max_tokens=1024,
            )
            scores = json.loads(raw_response)

            # Update the SessionQuestion record
            sq.score_engineering_skill = float(scores["engineering_skill"]["score"])
            sq.score_ai_collaboration = float(scores["ai_collaboration"]["score"])
            sq.score_ai_trust_calibration = float(scores["ai_trust_calibration"]["score"])
            sq.score_engineering_judgement = float(scores["engineering_judgement"]["score"])
            sq.scoring_notes = {
                "engineering_skill": scores["engineering_skill"]["rationale"],
                "ai_collaboration": scores["ai_collaboration"]["rationale"],
                "ai_trust_calibration": scores["ai_trust_calibration"]["rationale"],
                "engineering_judgement": scores["engineering_judgement"]["rationale"],
            }

            for dim in dimension_totals:
                dimension_totals[dim] += float(scores[dim]["score"])
            scored_count += 1

        except Exception as e:
            logger.error("question_scoring_failed", sq_id=str(sq.id), error=str(e))
            # Assign zero scores for failed question
            sq.score_engineering_skill = 0.0
            sq.score_ai_collaboration = 0.0
            sq.score_ai_trust_calibration = 0.0
            sq.score_engineering_judgement = 0.0
            sq.scoring_notes = {"error": str(e)}
            scored_count += 1
            for dim in dimension_totals:
                dimension_totals[dim] += 0.0

    if scored_count == 0:
        raise ValueError("No questions could be scored")

    # Average across questions
    averages = {dim: round(total / scored_count, 2) for dim, total in dimension_totals.items()}
    total_score = round(sum(averages.values()) / len(averages), 2)

    await db.flush()

    return {
        **averages,
        "total_score": total_score,
    }
