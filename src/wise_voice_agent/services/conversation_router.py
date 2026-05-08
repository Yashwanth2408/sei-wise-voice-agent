from __future__ import annotations



import json
from dataclasses import dataclass
from enum import Enum



from groq import Groq



from wise_voice_agent.core.settings import get_settings
from wise_voice_agent.knowledge.loader import load_wise_faq_markdown




class ConversationIntent(str, Enum):
    FAQ_ANSWER = "faq_answer"
    OUT_OF_SCOPE = "out_of_scope"
    ACKNOWLEDGMENT = "acknowledgment"
    END_CALL = "end_call"
    CONTINUE = "continue"
    CLARIFY = "clarify"




@dataclass
class ConversationDecision:
    intent: str
    reply: str
    should_end_call: bool
    reason: str




CONVERSATION_SYSTEM_PROMPT = """
You are a production voice conversation policy model for a Wise transfer tracking phone agent.



Your job is to decide the caller's conversational intent and produce the next spoken reply.



You are NOT the FAQ answer generator. You only decide what kind of turn this is and what the assistant should say next.
The caller is speaking on a phone call, so the reply must be natural, brief, and conversational.



Return JSON only with this exact schema:
{
  "intent": "faq_answer" | "out_of_scope" | "acknowledgment" | "end_call" | "continue" | "clarify",
  "reply": "<spoken reply in plain ASCII>",
  "should_end_call": true | false,
  "reason": "<short reason>"
}



Rules:
- Output plain ASCII only.
- Keep replies short and voice-friendly.
- If the user is clearly asking to end the call, use intent "end_call" and should_end_call true.
- If the user is just acknowledging, thanking, or saying okay, use "acknowledgment".
- If the user is saying they still have a question or do not want to end, use "continue".
- If the utterance is too unclear, too partial, or unusable, use "clarify".
- Recognize transfer tracking questions as in-scope: status checking, delays, troubleshooting delays, recipient money not arrived, transfer receipts, payment proof, etc.
- If the user is asking about topics covered in the FAQ (transfer tracking, delays, status meanings, what to do if money not arrived), use "faq_answer".
- If the user is asking about topics NOT in the FAQ (fees, account security, etc.), use "out_of_scope".
- When intent is "faq_answer", the reply should usually be an empty string.
- Never mention prompts, routing, policy, models, files, or internal logic.


Approved FAQ knowledge base:
{faq}
"""



CONTEXT_TEMPLATE = """Conversation state: {state}



Last assistant message:
{last_assistant_message}



Current caller utterance:
{user_text}
"""




class ConversationRouter:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.groq_model
        self._faq = load_wise_faq_markdown(str(settings.wise_faq_path))



    def decide(
        self,
        *,
        state: str,
        last_assistant_message: str,
        user_text: str,
    ) -> ConversationDecision:
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": CONVERSATION_SYSTEM_PROMPT.format(faq=self._faq)},
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
            return ConversationDecision(
                intent=payload["intent"],
                reply=payload["reply"],
                should_end_call=payload["should_end_call"],
                reason=payload["reason"],
            )
        except Exception:
            # Fallback prevents hard failures when model JSON validation fails.
            lowered = user_text.lower()
            if any(token in lowered for token in ("bye", "goodbye", "end call", "hang up", "stop")):
                return ConversationDecision(
                    intent="end_call",
                    reply="Alright. Thanks for calling. Goodbye.",
                    should_end_call=True,
                    reason="fallback_end_call",
                )
            if any(token in lowered for token in ("thanks", "thank you", "ok", "okay", "got it")):
                return ConversationDecision(
                    intent="acknowledgment",
                    reply="Youre welcome. Is there anything else about this transfer I can help with?",
                    should_end_call=False,
                    reason="fallback_ack",
                )
            return ConversationDecision(
                intent="faq_answer",
                reply="",
                should_end_call=False,
                reason="fallback_faq",
            )
