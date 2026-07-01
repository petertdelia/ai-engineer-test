"""
Unit tests for scoring logic in app/core/scoring.py.

Tests dimension parsing, difficulty modifier selection, and total_score computation.
No database I/O — mocks the Claude call and verifies the math.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.scoring import DIFFICULTY_MODIFIERS, score_session


# ── DIFFICULTY_MODIFIERS ───────────────────────────────────────────────────────

def test_difficulty_modifiers_all_keys_present():
    assert "low" in DIFFICULTY_MODIFIERS
    assert "medium" in DIFFICULTY_MODIFIERS
    assert "high" in DIFFICULTY_MODIFIERS


def test_difficulty_modifiers_are_strings():
    for key, val in DIFFICULTY_MODIFIERS.items():
        assert isinstance(val, str), f"{key} modifier is not a string"
        assert len(val) > 0


def test_difficulty_modifier_low_is_lenient():
    assert "lenient" in DIFFICULTY_MODIFIERS["low"].lower() or "partial" in DIFFICULTY_MODIFIERS["low"].lower()


def test_difficulty_modifier_high_is_strict():
    assert "strict" in DIFFICULTY_MODIFIERS["high"].lower()


# ── Score calculation helpers ──────────────────────────────────────────────────

def _make_scores(es=80, ac=70, atc=60, ej=90):
    """Build a canned Claude response JSON matching the scoring schema."""
    return {
        "engineering_skill": {"score": es, "rationale": "Good depth"},
        "ai_collaboration": {"score": ac, "rationale": "Used AI well"},
        "ai_trust_calibration": {"score": atc, "rationale": "Reasonable trust"},
        "engineering_judgement": {"score": ej, "rationale": "Strong tradeoffs"},
    }


def _expected_total(es, ac, atc, ej):
    """Replicate the averaging formula: average of four dimension scores."""
    return round((es + ac + atc + ej) / 4, 2)


def test_total_score_is_average_of_four_dimensions():
    es, ac, atc, ej = 80, 70, 60, 90
    expected = _expected_total(es, ac, atc, ej)
    assert expected == 75.0


def test_total_score_all_100():
    assert _expected_total(100, 100, 100, 100) == 100.0


def test_total_score_all_zero():
    assert _expected_total(0, 0, 0, 0) == 0.0


def test_total_score_mixed_values():
    # (55 + 65 + 75 + 85) / 4 = 70.0
    assert _expected_total(55, 65, 75, 85) == 70.0


# ── score_session integration (DB mocked) ─────────────────────────────────────

def _build_mock_session(difficulty_value: str = "medium"):
    """Build minimal mock objects for score_session."""
    from app.models.session import SessionDifficulty
    mock_session = MagicMock()
    mock_session.difficulty = MagicMock()
    mock_session.difficulty.value = difficulty_value
    return mock_session


def _build_mock_sq(response_text: str = "I would approach this by..."):
    """Build a minimal mock SessionQuestion."""
    sq = MagicMock()
    sq.id = uuid.uuid4()
    sq.response_text = response_text
    sq.ai_interactions = []
    sq.score_engineering_skill = None
    sq.score_ai_collaboration = None
    sq.score_ai_trust_calibration = None
    sq.score_engineering_judgement = None
    sq.scoring_notes = {}
    return sq


def _build_mock_question(title: str = "Test Q", scenario: str = "Scenario text"):
    q = MagicMock()
    q.title = title
    q.scenario = scenario
    return q


@pytest.mark.asyncio
async def test_score_session_returns_all_dimension_keys():
    """score_session returns a dict with all four dimension keys + total_score."""
    session_id = uuid.uuid4()
    mock_session = _build_mock_session("medium")
    sq = _build_mock_sq()
    question = _build_mock_question()
    canned = _make_scores(80, 70, 60, 90)

    mock_db = AsyncMock()

    session_result_mock = MagicMock()
    session_result_mock.scalar_one_or_none.return_value = mock_session

    sq_result_mock = MagicMock()
    sq_result_mock.all.return_value = [(sq, question)]

    mock_db.execute = AsyncMock(side_effect=[session_result_mock, sq_result_mock])
    mock_db.flush = AsyncMock()

    with patch("app.core.scoring.get_ai_simple_response", new=AsyncMock(return_value=json.dumps(canned))):
        result = await score_session(session_id, mock_db)

    assert "engineering_skill" in result
    assert "ai_collaboration" in result
    assert "ai_trust_calibration" in result
    assert "engineering_judgement" in result
    assert "total_score" in result


@pytest.mark.asyncio
async def test_score_session_correct_total_score():
    """total_score is the average of the four dimension averages."""
    session_id = uuid.uuid4()
    mock_session = _build_mock_session("medium")
    sq = _build_mock_sq()
    question = _build_mock_question()
    canned = _make_scores(80, 70, 60, 90)  # total = (80+70+60+90)/4 = 75.0

    mock_db = AsyncMock()
    session_result_mock = MagicMock()
    session_result_mock.scalar_one_or_none.return_value = mock_session
    sq_result_mock = MagicMock()
    sq_result_mock.all.return_value = [(sq, question)]
    mock_db.execute = AsyncMock(side_effect=[session_result_mock, sq_result_mock])
    mock_db.flush = AsyncMock()

    with patch("app.core.scoring.get_ai_simple_response", new=AsyncMock(return_value=json.dumps(canned))):
        result = await score_session(session_id, mock_db)

    assert result["total_score"] == 75.0


@pytest.mark.asyncio
async def test_score_session_updates_sq_attributes():
    """score_session sets score_* and scoring_notes on the SessionQuestion."""
    session_id = uuid.uuid4()
    mock_session = _build_mock_session("low")
    sq = _build_mock_sq()
    question = _build_mock_question()
    canned = _make_scores(85, 75, 65, 95)

    mock_db = AsyncMock()
    session_result_mock = MagicMock()
    session_result_mock.scalar_one_or_none.return_value = mock_session
    sq_result_mock = MagicMock()
    sq_result_mock.all.return_value = [(sq, question)]
    mock_db.execute = AsyncMock(side_effect=[session_result_mock, sq_result_mock])
    mock_db.flush = AsyncMock()

    with patch("app.core.scoring.get_ai_simple_response", new=AsyncMock(return_value=json.dumps(canned))):
        await score_session(session_id, mock_db)

    assert sq.score_engineering_skill == 85.0
    assert sq.score_ai_collaboration == 75.0
    assert sq.score_ai_trust_calibration == 65.0
    assert sq.score_engineering_judgement == 95.0
    assert isinstance(sq.scoring_notes, dict)
    assert "engineering_skill" in sq.scoring_notes


@pytest.mark.asyncio
async def test_score_session_handles_missing_session():
    """score_session raises ValueError when session is not found."""
    mock_db = AsyncMock()
    session_result_mock = MagicMock()
    session_result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=session_result_mock)

    with pytest.raises(ValueError, match="not found"):
        await score_session(uuid.uuid4(), mock_db)


@pytest.mark.asyncio
async def test_score_session_zero_scores_when_claude_fails():
    """When Claude raises for a question, that question gets 0 scores (not a crash)."""
    session_id = uuid.uuid4()
    mock_session = _build_mock_session("high")
    sq = _build_mock_sq()
    question = _build_mock_question()

    mock_db = AsyncMock()
    session_result_mock = MagicMock()
    session_result_mock.scalar_one_or_none.return_value = mock_session
    sq_result_mock = MagicMock()
    sq_result_mock.all.return_value = [(sq, question)]
    mock_db.execute = AsyncMock(side_effect=[session_result_mock, sq_result_mock])
    mock_db.flush = AsyncMock()

    with patch("app.core.scoring.get_ai_simple_response", new=AsyncMock(side_effect=Exception("Claude down"))):
        result = await score_session(session_id, mock_db)

    assert result["total_score"] == 0.0
    assert sq.score_engineering_skill == 0.0
    assert "error" in sq.scoring_notes


@pytest.mark.asyncio
async def test_score_session_averages_across_multiple_questions():
    """When a session has 2 questions, scores are averaged across both."""
    session_id = uuid.uuid4()
    mock_session = _build_mock_session("medium")
    sq1 = _build_mock_sq("Answer 1")
    sq2 = _build_mock_sq("Answer 2")
    q1 = _build_mock_question("Q1")
    q2 = _build_mock_question("Q2")

    # Q1: 80,80,80,80 → avg 80; Q2: 60,60,60,60 → avg 60
    # Final avg: (80+60)/2 = 70 per dimension → total = 70
    canned1 = _make_scores(80, 80, 80, 80)
    canned2 = _make_scores(60, 60, 60, 60)

    mock_db = AsyncMock()
    session_result_mock = MagicMock()
    session_result_mock.scalar_one_or_none.return_value = mock_session
    sq_result_mock = MagicMock()
    sq_result_mock.all.return_value = [(sq1, q1), (sq2, q2)]
    mock_db.execute = AsyncMock(side_effect=[session_result_mock, sq_result_mock])
    mock_db.flush = AsyncMock()

    ai_responses = [json.dumps(canned1), json.dumps(canned2)]
    call_count = [0]

    async def fake_ai(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        return ai_responses[idx]

    with patch("app.core.scoring.get_ai_simple_response", new=fake_ai):
        result = await score_session(session_id, mock_db)

    assert result["total_score"] == 70.0
    assert result["engineering_skill"] == 70.0
