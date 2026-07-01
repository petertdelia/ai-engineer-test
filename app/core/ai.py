import asyncio
import json
from typing import AsyncGenerator, Optional

import pybreaker
import structlog
from anthropic import AsyncAnthropic, APIError

from app.core.config import settings

logger = structlog.get_logger()

ASSISTANT_SYSTEM_PROMPT = """You are an AI assistant helping a candidate work through an engineering problem during \
an assessment. Your role is to guide their thinking — ask clarifying questions, point \
them toward relevant concepts, and help them reason through their approach. You must \
NOT provide the final answer, complete working code, or a direct solution. If the \
candidate asks you to solve the problem outright, redirect them with a question instead."""

ANSWER_CLASSIFIER_PROMPT = """You are a classifier. Review the following AI assistant response and determine \
whether it provides a direct answer, complete working code, or direct solution to an engineering problem \
in a way that effectively gives the answer away.

Respond with a JSON object: {"contains_direct_answer": true/false, "reason": "brief explanation"}

AI Response to classify:
{response}"""

MAX_TURNS_PER_QUESTION = 15
MAX_INPUT_TOKENS = 8000
MAX_USER_MESSAGE_CHARS = 2000

_circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=60,
    name="anthropic_api",
)

_anthropic_client: Optional[AsyncAnthropic] = None


def get_anthropic_client() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


def _truncate_messages_to_token_budget(
    messages: list[dict], max_tokens: int = MAX_INPUT_TOKENS
) -> list[dict]:
    """Truncate older messages while always keeping the most recent ones."""
    # Simple character-based approximation: ~4 chars per token
    max_chars = max_tokens * 4

    total_chars = sum(len(m.get("content", "")) for m in messages)
    if total_chars <= max_chars:
        return messages

    # Remove oldest messages (but keep the most recent ones)
    truncated = list(messages)
    while truncated and sum(len(m.get("content", "")) for m in truncated) > max_chars:
        if len(truncated) > 2:
            truncated.pop(0)
        else:
            break
    return truncated


async def get_ai_response_stream(
    question_scenario: str,
    ai_interactions: list[dict],
    new_user_message: str,
    difficulty: str = "medium",
) -> AsyncGenerator[str, None]:
    """Stream AI assistant response as SSE chunks."""
    client = get_anthropic_client()

    # Sanitize user input
    sanitized_message = new_user_message[:MAX_USER_MESSAGE_CHARS]

    # Build system prompt with difficulty context
    difficulty_addendum = ""
    if difficulty == "low":
        difficulty_addendum = "\nThis is a low-difficulty assessment. You may be slightly more direct in your hints."
    elif difficulty == "high":
        difficulty_addendum = "\nThis is a high-difficulty assessment. Be more Socratic and guide rather than hint."

    system_prompt = ASSISTANT_SYSTEM_PROMPT + difficulty_addendum
    system_prompt += f"\n\nThe question scenario is:\n{question_scenario}"

    # Build message history
    messages = []
    for interaction in ai_interactions:
        messages.append({
            "role": interaction["role"],
            "content": interaction["content"],
        })
    messages.append({"role": "user", "content": sanitized_message})

    # Truncate to token budget
    messages = _truncate_messages_to_token_budget(messages, MAX_INPUT_TOKENS)

    try:
        @_circuit_breaker
        def _breaker_wrap():
            pass

        _breaker_wrap()  # Check circuit breaker state

        async with client.messages.stream(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        ) as stream:
            full_response = ""
            async for text in stream.text_stream:
                full_response += text
                yield f"data: {json.dumps({'content': text})}\n\n"

            # Post-message classifier to detect direct answers
            is_direct_answer = await _classify_response_for_direct_answer(full_response)
            if is_direct_answer:
                logger.warning("ai_response_suppressed_direct_answer")
                yield f"data: {json.dumps({'suppressed': True, 'content': ''})}\n\n"
                yield f"data: {json.dumps({'content': 'I notice I was about to give you the answer directly. Let me redirect: what approach have you considered so far?'})}\n\n"

            yield "data: [DONE]\n\n"

    except pybreaker.CircuitBreakerError:
        logger.error("circuit_breaker_open")
        yield f"data: {json.dumps({'error': 'AI assistant temporarily unavailable', 'circuit_open': True})}\n\n"
        yield "data: [DONE]\n\n"
    except APIError as e:
        logger.error("anthropic_api_error", error=str(e))
        raise


async def _classify_response_for_direct_answer(response: str) -> bool:
    """Use a cheap Haiku call to classify whether the response contains a direct answer."""
    client = get_anthropic_client()
    try:
        result = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": ANSWER_CLASSIFIER_PROMPT.format(response=response[:2000]),
            }],
        )
        content = result.content[0].text if result.content else "{}"
        parsed = json.loads(content)
        return parsed.get("contains_direct_answer", False)
    except Exception:
        # If classifier fails, don't suppress the response
        return False


async def get_ai_simple_response(
    system_prompt: str,
    user_message: str,
    model: str = "claude-sonnet-4-5",
    max_tokens: int = 2048,
) -> str:
    """Simple non-streaming call for scoring, pipeline, etc."""
    client = get_anthropic_client()
    result = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return result.content[0].text if result.content else ""
