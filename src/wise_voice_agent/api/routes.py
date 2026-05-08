from fastapi import APIRouter
from pydantic import BaseModel


from wise_voice_agent.services.responder import AnswerResponder
from wise_voice_agent.services.router import ScopeRouter


router = APIRouter()
scope_router = ScopeRouter()
answer_responder = AnswerResponder()



class RouteRequest(BaseModel):
    text: str



@router.post("/route")
async def route_request(body: RouteRequest) -> dict:
    decision = scope_router.decide(body.text)
    return {
        "route": decision.route,
        "reason": decision.reason,
        "allowed": decision.allowed,
    }



@router.post("/respond")
async def respond_request(body: RouteRequest) -> dict:
    decision = scope_router.decide(body.text)


    if decision.route == "faq_answer":
        reply = answer_responder.answer(body.text)
        end_call = False
    else:
        reply = answer_responder.deflect()
        end_call = True


    return {
        "route": decision.route,
        "allowed": decision.allowed,
        "reply": reply,
        "end_call": end_call,
    }

