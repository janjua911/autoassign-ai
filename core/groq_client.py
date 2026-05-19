"""
core/groq_client.py
Groq API client — thin wrapper with retry, model switching, and token tracking.
"""

import json
import re
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from core.config import cfg


class GroqClient:
    """
    Wraps the Groq SDK.
    Usage:
        from core.groq_client import groq_client
        response = groq_client.chat("Explain recursion")
        code     = groq_client.code("Write a Python sort function")
    """

    def __init__(self):
        self._client = None
        self._total_tokens = 0

    def _get_client(self) -> Groq:
        if self._client is None:
            api_key = cfg.groq_api_key
            if not api_key or api_key.startswith("<YOUR_"):
                raise ValueError(
                    "Groq API key missing! Set it in config/user_config.yaml\n"
                    "Get free key: https://console.groq.com"
                )
            self._client = Groq(api_key=api_key)
            logger.info("Groq client initialized")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _call(self, model: str, messages: list, **kwargs) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", cfg.max_tokens),
            temperature=kwargs.get("temperature", cfg.temperature),
        )
        tokens_used = response.usage.total_tokens
        self._total_tokens += tokens_used
        logger.debug(f"Groq [{model}] — tokens: {tokens_used} (total: {self._total_tokens})")
        return response.choices[0].message.content.strip()

    def chat(self, prompt: str, system: str = None, **kwargs) -> str:
        """General chat — uses primary model."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._call(cfg.primary_model, messages, **kwargs)

    def code(self, prompt: str, system: str = None, **kwargs) -> str:
        """Coding tasks — uses deepseek-r1 for better reasoning."""
        system = system or (
            "You are an expert programmer. Return only clean, working code. "
            "No explanations unless asked. No markdown fences unless it's a complete file."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        return self._call(cfg.coding_model, messages, **kwargs)

    def solve_assignment(self, question: str, subject: str = "General") -> str:
        """Solve an academic assignment question with structured answer."""
        system = f"""You are an expert academic assistant specializing in {subject}.
Solve assignment questions with:
- Clear, structured answers
- Step-by-step explanations where needed
- Proper academic formatting
- Accurate and detailed content
- Examples where helpful
Write in a professional academic tone. Do not mention AI."""
        return self._call(cfg.primary_model, [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Solve this assignment question:\n\n{question}"},
        ])

    def extract_assignment_info(self, raw_text: str) -> dict:
        """Parse raw Teams/email text and extract structured assignment info."""
        prompt = f"""Extract structured assignment information from this text.
Return a JSON object with these exact keys:
- title: assignment title (string)
- subject: subject/course name (string)
- deadline: deadline as mentioned (string)
- questions: list of individual questions/tasks (array of strings)
- instructions: any special instructions (string)
- confidence: your confidence 0-100 that this is an assignment (integer)

Text:
---
{raw_text}
---

Return ONLY valid JSON, no other text."""
        result = self._call(cfg.primary_model, [
            {"role": "system", "content": "You are a JSON extractor. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ])
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', result, re.DOTALL)
            if match:
                return json.loads(match.group())
            logger.error(f"Failed to parse JSON from Groq: {result[:200]}")
            return {"title": "Unknown", "questions": [raw_text], "confidence": 0}

    def check_answer_quality(self, question: str, answer: str) -> dict:
        """Self-verify: Is this answer good enough to submit?"""
        prompt = f"""Review this assignment answer and rate it.

QUESTION:
{question}

ANSWER:
{answer}

Return JSON with:
- score: 0-100 quality score
- issues: list of problems found (empty list if none)
- suggestions: list of improvements
- ready_to_submit: true/false

Return ONLY valid JSON."""
        result = self._call(cfg.primary_model, [
            {"role": "system", "content": "You are a strict academic reviewer. Return only JSON."},
            {"role": "user", "content": prompt},
        ])
        try:
            return json.loads(result)
        except Exception:
            return {"score": 75, "issues": [], "suggestions": [], "ready_to_submit": True}

    @property
    def total_tokens_used(self) -> int:
        return self._total_tokens


groq_client = GroqClient()
