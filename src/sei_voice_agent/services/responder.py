from __future__ import annotations


import re
import hashlib
import unicodedata


from groq import Groq


from sei_voice_agent.core.settings import get_settings


ANSWER_SYSTEM_PROMPT = """
You are a professional Wise customer support agent for transfer tracking questions.


Answer the caller's question using your knowledge of Wise transfer tracking.
Be helpful, concise, and conversational.


Rules:
- Be concise: 2 to 3 sentences max.
- Use plain ASCII only, no markdown or special formatting.
- Sound natural, helpful, and spoken, not robotic.
- Avoid one-word answers.
- Vary the phrasing when the caller repeats a question.
- If the previous assistant message is similar, answer again with a different opening and wording.
- Do NOT ask follow-up questions unless the answer needs a short clarification.
- Do NOT mention internal processes or knowledge base.
- For transfer delays: common reasons are sender bank slow, compliance checks, wrong details, weekend/holiday, recipient bank slow, slower payment method chosen
- For money not arrived: suggest checking sender name (may show Wise or partner), verify amount, check reference number, verify account currency
- Transfer statuses: Processing (waiting for sender's bank), Money received (converting), Transfer sent (at recipient bank), Complete (sent, but recipient bank still processing)
- Timelines: card payments instant, bank transfers 1-4 days, Swift 1-6 days
- Transfer receipt: available in Wise account, helps recipient's bank locate transfer
- Weekends/holidays: banks don't process, may delay until next business day


Example answers:
- "You can check your transfer status in your Wise account on the Home page."
- "Weekend and holiday delays are common - your bank may take extra time on those days."
- "Ask the recipient to check if it shows under a different name - it might say Wise or a Wise partner."
"""


DEFLECTION_TEXT = (
    "That is outside Wise transfer tracking. If you want to stay on transfer questions, I can keep helping. "
    "If not, we can end the call."
)



def normalize_voice_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")


    ascii_text = re.sub(r"[*_#`>\[\]\\]", " ", ascii_text)


    ascii_text = re.sub(r"\b\d+\.\s*", "", ascii_text)


    ascii_text = re.sub(r"(?m)^\s*[-–—]\s+", " ", ascii_text)


    ascii_text = re.sub(r"https?://\S+", "", ascii_text)


    return " ".join(ascii_text.split())



class AnswerResponder:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.groq_model


    def answer(self, user_text: str, last_assistant_message: str = "") -> str:
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                temperature=0.45,
                messages=[
                    {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Caller question:\n{user_text}\n\n"
                            f"Previous assistant message:\n{last_assistant_message or '(none)'}"
                        ),
                    },
                ],
            )
            content = completion.choices[0].message.content.strip()
            return normalize_voice_text(content)
        except Exception as e:
            fallback_options = [
                "I can help with that transfer question, but I need a moment to reconnect. Please try again.",
                "I'm having trouble processing that right now. Please ask again in a moment.",
                "I couldn't fetch that answer just now. Ask me again in a moment and I'll try another way.",
            ]
            digest = hashlib.sha256(user_text.encode("utf-8", errors="ignore")).digest()
            index = digest[0] % len(fallback_options)
            return fallback_options[index]


    def deflect(self) -> str:
        return normalize_voice_text(DEFLECTION_TEXT)
