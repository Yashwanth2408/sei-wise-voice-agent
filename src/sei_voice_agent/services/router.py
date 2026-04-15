from __future__ import annotations



import json
from dataclasses import dataclass



from groq import Groq



from sei_voice_agent.core.settings import get_settings
from sei_voice_agent.knowledge.loader import load_wise_faq_markdown




ROUTER_SYSTEM_PROMPT = """
You are a strict scope classifier for a Wise transfer tracking voice support agent.



Your job is to decide whether the user's request is fully answerable using ONLY the approved
'Where is my money?' FAQ knowledge base.



Return JSON only with this schema:
{
  "route": "faq_answer" | "deflect",
  "reason": "<short reason>",
  "allowed": true | false
}



Routing rules:
- Choose "faq_answer" only if the request is clearly covered by the FAQ knowledge base.
- Choose "deflect" if the question is outside scope, partially outside scope, ambiguous, asks for actions
  not covered by the FAQ, or would require guessing.
- If a multi-part request includes any out-of-scope part, return "deflect".
- Never answer the user. Only classify.


Approved FAQ knowledge base:
{faq}
"""




@dataclass
class RouteDecision:
    route: str
    reason: str
    allowed: bool




class ScopeRouter:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.groq_model
        self._faq = load_wise_faq_markdown(str(settings.wise_faq_path))



    def decide(self, user_text: str) -> RouteDecision:
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT.format(faq=self._faq)},
                    {"role": "user", "content": f"User request:\\\\n{user_text}"},
                ],
            )
            payload = json.loads(completion.choices[0].message.content)
            return RouteDecision(
                route=payload.get("route", "deflect"),
                reason=payload.get("reason", "model_decision"),
                allowed=bool(payload.get("allowed", False)),
            )
        except Exception:
            return RouteDecision(route="deflect", reason="fallback_deflect", allowed=False)
