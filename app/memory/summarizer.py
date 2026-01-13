"""
Week 3: LLM-based Conversation Summarizer
==========================================

Replaces keyword-based summarization with Gemini LLM for better context retention.

Key Features:
- Georgian language support
- Extracts user preferences, allergies, product interests
- Maintains conversation context across pruning
- Falls back to simple summary on error
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Google GenAI SDK (new unified SDK)
from google import genai
from google.genai.types import GenerateContentConfig

logger = logging.getLogger(__name__)


# Summarization prompt in Georgian for best results
SUMMARIZATION_PROMPT = """შეაჯამე ეს საუბარი მოკლედ (2-3 წინადადებით).

გამოყავი:
1. მომხმარებლის მთავარი ინტერესები (პროდუქტები, კატეგორიები)
2. აღმოჩენილი პრეფერენციები (ბიუჯეტი, ბრენდები)
3. მნიშვნელოვანი შეზღუდვები (ალერგიები, დიეტური შეზღუდვები)
4. დასმული კითხვები და მიღებული პასუხები

შენიშვნა: პასუხი დაწერე მხოლოდ ქართულად.

საუბარი:
{conversation}"""


class ConversationSummarizer:
    """
    LLM-based conversation summarizer using Google GenAI SDK.

    Uses Gemini to generate semantic summaries of conversation history,
    preserving user preferences, allergies, and product interests.
    """

    def __init__(
        self,
        client: genai.Client,
        model_name: str = "gemini-2.5-flash",
        max_tokens: int = 300,
        temperature: float = 0.3,
    ):
        """
        Initialize the summarizer.

        Args:
            client: Google GenAI client instance
            model_name: Model to use for summarization (default: gemini-2.5-flash)
            max_tokens: Maximum output tokens for summary
            temperature: Lower = more focused/deterministic
        """
        self.client = client
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature

        logger.info(f"Initialized ConversationSummarizer with model={model_name}")

    def _format_conversation(self, messages: List[Dict[str, Any]]) -> str:
        """
        Format messages into readable conversation text for the LLM.

        Args:
            messages: List of message dicts with role and parts

        Returns:
            Formatted conversation string
        """
        formatted_lines = []

        for msg in messages:
            role = msg.get("role", "user")
            role_label = "მომხმარებელი" if role == "user" else "ასისტენტი"

            for part in msg.get("parts", []):
                if "text" in part:
                    text = part["text"]
                    # Truncate very long messages
                    if len(text) > 500:
                        text = text[:500] + "..."
                    formatted_lines.append(f"{role_label}: {text}")
                elif "function_call" in part:
                    # Note function calls but don't include full details
                    fc = part["function_call"]
                    formatted_lines.append(f"[ფუნქცია გამოძახებულია: {fc.get('name', 'unknown')}]")

        return "\n".join(formatted_lines)

    async def summarize(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """
        Generate an LLM summary of the conversation.

        Args:
            messages: List of message dicts to summarize

        Returns:
            Summary string or None if failed
        """
        if not messages:
            logger.warning("No messages to summarize")
            return None

        try:
            # Format conversation for prompt
            conversation_text = self._format_conversation(messages)

            # Build prompt
            prompt = SUMMARIZATION_PROMPT.format(conversation=conversation_text)

            # Call Gemini using new SDK
            config = GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            )

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

            # Extract text from response
            summary = response.text.strip() if response.text else None

            if summary:
                logger.info(f"Generated LLM summary ({len(summary)} chars): {summary[:100]}...")
                return summary
            else:
                logger.warning("LLM returned empty summary")
                return None

        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            return None

    def summarize_sync(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """
        Synchronous version of summarize for use in sync contexts.

        Args:
            messages: List of message dicts to summarize

        Returns:
            Summary string or None if failed
        """
        if not messages:
            logger.warning("No messages to summarize")
            return None

        try:
            # Format conversation for prompt
            conversation_text = self._format_conversation(messages)

            # Build prompt
            prompt = SUMMARIZATION_PROMPT.format(conversation=conversation_text)

            # Call Gemini using sync API
            config = GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

            # Extract text from response
            summary = response.text.strip() if response.text else None

            if summary:
                logger.info(f"Generated LLM summary ({len(summary)} chars): {summary[:100]}...")
                return summary
            else:
                logger.warning("LLM returned empty summary")
                return None

        except Exception as e:
            logger.error(f"LLM summarization (sync) failed: {e}")
            return None


# Fallback simple summary (same as original _generate_simple_summary)
def generate_simple_summary(messages: List[Dict[str, Any]]) -> str:
    """
    Fallback keyword-based summary when LLM is unavailable.

    This is the original Week 1 implementation, kept as backup.
    """
    topics = []

    for msg in messages:
        for part in msg.get("parts", []):
            text = part.get("text", "").lower()

            # Extract key topics (Georgian keywords)
            if "პროტეინ" in text:
                topics.append("პროტეინი")
            if "კრეატინ" in text:
                topics.append("კრეატინი")
            if "ალერგია" in text:
                topics.append("ალერგია")
            if "ლაქტოზ" in text:
                topics.append("ლაქტოზის აუტანლობა")
            if "ვეგან" in text or "ვეგეტარიან" in text:
                topics.append("მცენარეული დიეტა")
            if "ბიუჯეტ" in text or "ლარ" in text:
                topics.append("ბიუჯეტი")
            if "bcaa" in text:
                topics.append("BCAA")
            if "ვიტამინ" in text:
                topics.append("ვიტამინები")
            if "ომეგა" in text:
                topics.append("ომეგა-3")

    unique_topics = list(set(topics))

    if unique_topics:
        return f"წინა საუბარში განხილული: {', '.join(unique_topics)}"
    else:
        return "წინა საუბარში განხილული: ზოგადი კითხვები სპორტულ კვებაზე"
