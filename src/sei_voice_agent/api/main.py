from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from sei_voice_agent.api.routes import router as api_router
from sei_voice_agent.core.settings import get_settings
from sei_voice_agent.knowledge.loader import load_wise_faq_markdown
from sei_voice_agent.telemetry.logging import configure_logging


settings = get_settings()
configure_logging(settings.log_level)


app = FastAPI(
    title="Sei Wise Voice Agent",
    version="0.1.0",
    default_response_class=ORJSONResponse,
)


app.include_router(api_router)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "groq_model": settings.groq_model,
        "cartesia_model": settings.cartesia_model,
    }


@app.get("/ready")
async def ready() -> dict:
    faq_text = load_wise_faq_markdown("data/wise_where_is_my_money_faq.md")
    return {
        "status": "ready",
        "faq_loaded": bool(faq_text.strip()),
        "faq_chars": len(faq_text),
        "deepgram_configured": bool(settings.deepgram_api_key),
        "groq_configured": bool(settings.groq_api_key),
        "cartesia_configured": bool(settings.cartesia_api_key),
    }

