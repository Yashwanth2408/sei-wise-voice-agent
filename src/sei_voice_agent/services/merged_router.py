from __future__ import annotations


import json
from dataclasses import dataclass
from typing import Any


import structlog
from groq import Groq


from sei_voice_agent.core.settings import get_settings


logger = structlog.get_logger(__name__)


MERGED_ROUTER_PROMPT = """
You are a Wise transfer-tracking voice agent router.


Decide what the caller is asking and what reply to speak.


Return ONLY valid JSON with this exact schema:
{
  "intent": "faq_answer" | "out_of_scope" | "acknowledgment" | "end_call" | "continue" | "clarify" | "pause_call",
  "reply": "<plain ASCII spoken text, 1-2 sentences max>",
  "should_end_call": false,
  "route": "faq_answer" | "deflect",
  "allowed": false,
  "reason": "<short reason>",
  "function_call": null | {
    "name": "pause_call",
    "arguments": {
      "seconds": 10
    }
  }
}


Rules:
- Output plain ASCII only, no markdown or special characters.
- Keep replies brief, natural, and conversational.
- Never repeat the previous assistant message verbatim.
- If the caller repeats a question, rephrase the answer with a different opening or a small extra detail.
- If the state is awaiting_scope_confirmation and the caller says continue, keep going, don't cut, or stay on the line: intent=continue.
- If the state is awaiting_scope_confirmation and the caller says cut the call, end the call, hang up, or stop: intent=end_call.
- If caller says bye/goodbye/end call/hang up/stop: intent=end_call, should_end_call=true, reply="Understood. I will end the call now. Thanks for calling."
- If caller says hold on, wait, wait a second, one second, give me a moment, just a sec, pause, pause the call, let me check, I'll be right back, or can you wait: intent=pause_call, route=deflect, allowed=false, reply="Sure, I will wait.", function_call={"name":"pause_call","arguments":{"seconds":10}}.
- If caller says thanks/ok/yes/got it: intent=acknowledgment, reply="Of course. Ask me anything else about your Wise transfer."
- If connection check (hello/hi/can you hear): intent=continue, reply="Yes, I can help. What transfer question do you have?"
- If unclear or fragmentary: intent=clarify, reply="Sorry, can you say that again?"


TRANSFER QUESTIONS (route to faq_answer):
- "How do I check my transfer status?"
- "Why is my transfer delayed?"
- "What does Transfer sent mean?"
- "Money not arrived - what to do?"
- "How long does it take?"
- "What about weekend delays?"
- "Do I need proof of payment?"
- "What's a transfer receipt?"
- Any question about transfer tracking, delays, statuses, or where money is


NOT TRANSFER TRACKING (out_of_scope):
- "What's the transfer fee?"
- "Can I change recipient details?"
- "I want to open account"
- "What's the exchange rate?"
- "I was defrauded"


Out-of-scope reply style:
- Explain that the question is outside Wise transfer tracking.
- Offer to continue with transfer questions or end the call.
- Sound calm, helpful, and spoken, not abrupt.


CRITICAL: If ANY chance it's about transfer status/delays/tracking, use faq_answer. Only deflect if 100% certain it's out of scope.
"""


CONTEXT_TEMPLATE = """Conversation state: {state}
Last assistant message: {last_assistant_message}
Current caller utterance: {user_text}
"""



@dataclass
class MergedRouteDecision:
    intent: str
    reply: str
    should_end_call: bool
    route: str
    allowed: bool
    reason: str
    function_name: str | None = None
    function_arguments: dict[str, Any] | None = None



class MergedConversationScopeRouter:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.groq_model


    def decide(
        self,
        *,
        state: str,
        last_assistant_message: str,
        user_text: str,
    ) -> MergedRouteDecision:
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": MERGED_ROUTER_PROMPT},
                    {
                        "role": "user",
                        "content": CONTEXT_TEMPLATE.format(
                            state=state,
                            last_assistant_message=last_assistant_message or "(none)",
                            user_text=user_text,
                        ),
                    },
                ],
            )
            payload = json.loads(completion.choices[0].message.content)
            function_call = payload.get("function_call") or {}
            if not isinstance(function_call, dict):
                function_call = {}
            function_arguments = function_call.get("arguments") or {}
            if not isinstance(function_arguments, dict):
                function_arguments = {}
            return MergedRouteDecision(
                intent=payload["intent"],
                reply=payload.get("reply", ""),
                should_end_call=bool(payload.get("should_end_call", False)),
                route=payload.get("route", "deflect"),
                allowed=bool(payload.get("allowed", False)),
                reason=payload.get("reason", "model_decision"),
                function_name=function_call.get("name"),
                function_arguments=function_arguments,
            )
        except Exception as e:
            logger.warning("router_exception", error=str(e))
            lowered = user_text.lower()
            if self._looks_like_pause_request(lowered):
                return MergedRouteDecision(
                    intent="pause_call",
                    reply="Sure, I will wait.",
                    should_end_call=False,
                    route="deflect",
                    allowed=False,
                    reason="fallback_pause_call",
                    function_name="pause_call",
                    function_arguments={"seconds": 10},
                )
            if any(token in lowered for token in ("bye", "goodbye", "end call", "hang up", "stop", "cut the call")):
                return MergedRouteDecision(
                    intent="end_call",
                    reply="Understood. I will end the call now. Thanks for calling.",
                    should_end_call=True,
                    route="deflect",
                    allowed=False,
                    reason="fallback_end_call",
                )
            if any(token in lowered for token in ("thanks", "thank you", "ok", "okay", "got it", "yes", "continue", "keep going", "dont cut", "don't cut", "stay on the line")):
                return MergedRouteDecision(
                    intent="acknowledgment",
                    reply="Of course. Ask me anything else about your Wise transfer.",
                    should_end_call=False,
                    route="deflect",
                    allowed=False,
                    reason="fallback_ack",
                )
            if any(token in lowered for token in ("hello", "hi", "hear me", "can you hear")):
                return MergedRouteDecision(
                    intent="continue",
                    reply="Yes, I can help. What transfer question do you have?",
                    should_end_call=False,
                    route="deflect",
                    allowed=False,
                    reason="fallback_connection",
                )
            if any(token in lowered for token in ("fee", "fees", "exchange rate", "account opening", "fraud", "card")):
                return MergedRouteDecision(
                    intent="out_of_scope",
                    reply="That is outside Wise transfer tracking. If you want, I can stay with transfer questions, or we can end the call.",
                    should_end_call=False,
                    route="deflect",
                    allowed=False,
                    reason="fallback_out_of_scope",
                )
            # Default: assume it is a transfer question.
            return MergedRouteDecision(
                intent="faq_answer",
                reply="",
                should_end_call=False,
                route="faq_answer",
                allowed=True,
                reason="fallback_assume_transfer_question",
            )


    def _looks_like_pause_request(self, lowered: str) -> bool:
        pause_phrases = (
            "hold on",
            "wait a second",
            "wait one second",
            "one second",
            "give me a moment",
            "give me one moment",
            "just a sec",
            "just a second",
            "pause the call",
            "pause call",
            "let me check",
            "i'll be right back",
            "ill be right back",
            "can you wait",
            "please wait",
        )
        if any(phrase in lowered for phrase in pause_phrases):
            return True
        return lowered.strip() in {"wait", "pause", "hold"}
