# Sei Wise Voice Agent

Sei Wise Voice Agent is a scoped voice support demo for Wise transfer-tracking questions. It listens to callers over LiveKit, transcribes in real time, routes requests through a Wise FAQ scope, and responds with grounded TTS answers. The system is intentionally narrow and deflects anything outside transfer tracking.

![UI Demo](data/ui.gif)

## What It Does

- Answers Wise transfer status questions: processing, transfer sent, complete, delayed
- Explains common reasons for delays and missing funds
- Guides users to receipts, proof of payment, and reference numbers
- Deflects out-of-scope topics and ends calls when asked
- Supports barge-in and pause requests for a smoother call experience

## How It Works

1. The browser streams microphone audio to the backend via LiveKit.
2. Pipecat handles streaming and VAD with Silero.
3. Deepgram converts speech to text.
4. The voice processor routes the turn and enforces scope.
5. Groq generates replies for in-scope questions.
6. Cartesia produces TTS audio back to the browser.
7. The demo UI shows transcript, status, and call controls.

## Tech Stack

- Python 3.11+
- FastAPI
- Pipecat LiveKit pipeline
- Silero VAD
- Deepgram STT
- Groq for routing and answers
- Cartesia TTS
- Vanilla HTML, CSS, and JavaScript frontend

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bot.py
```

Open the demo UI at `/demo`. The static assets are served from `/demo-assets`.

## Configuration

Create a `.env` file in the project root:

```env
APP_ENV=local
APP_HOST=127.0.0.1
APP_PORT=7860
LOG_LEVEL=INFO

DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key
GROQ_MODEL=gpt-oss-20b
CARTESIA_API_KEY=your_cartesia_key
CARTESIA_MODEL=sonic-3
CARTESIA_VOICE_ID=your_voice_id

LIVEKIT_URL=your_livekit_url
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_ROOM_PREFIX=sei-wise

WISE_FAQ_DOC_PATH=data/wise_where_is_my_money_faq.md
CALL_TELEMETRY_DIR=logs/calls
SESSION_TIMEOUT_SECONDS=300
BARGE_IN_ENABLED=true
VAD_CONFIDENCE=0.75
VAD_START_SECS=0.12
VAD_STOP_SECS=0.45
VAD_MIN_VOLUME=0.45
PAUSE_CALL_SECONDS=10
PAUSE_CHECKIN_MESSAGE=Are you still there? Can we continue?
ENABLE_EDGE_TTS_FALLBACK=true
```

## API Endpoints

The API app exposes readiness and routing endpoints. If you run the API app directly, use:

```powershell
uvicorn sei_voice_agent.api.main:app --host 127.0.0.1 --port 7860
```

Endpoints:

- `GET /health` returns app status and configured model names.
- `GET /ready` confirms FAQ loading and API key presence.
- `POST /livekit/session` creates a room and returns a join token.

## Scope Rules

In scope:

- Transfer status and where money is
- Processing, transfer sent, and complete statuses
- Delayed or stuck transfers
- Recipient bank processing delays
- Proof of payment and transfer receipts
- Reference numbers and banking partner references
- Payment speed for card, bank transfer, and SWIFT transfers

Out of scope:

- Fees and exchange rates
- Account creation or setup
- Fraud or account security issues
- Wise card problems
- Transfer cancellation
- Recipient management outside transfer tracking

## Conversation Behavior

- Replies are short, spoken, and conversational.
- Repeated questions are rephrased instead of repeated verbatim.
- The call ends gracefully when the caller asks to stop or hang up.
- If the caller asks to wait, the agent pauses and checks in again.

## Telemetry

Call activity is logged to JSONL files in `logs/calls/`. Logs include routing decisions, transcripts, and call termination events.

## Repository Layout

```text
bot.py                         # Pipecat bootstrap entry point
data/wise_where_is_my_money_faq.md
frontend/                      # Demo UI assets served from /demo-assets
logs/calls/                    # JSONL call telemetry output
src/sei_voice_agent/api/       # FastAPI app and routes
src/sei_voice_agent/core/      # Settings and environment config
src/sei_voice_agent/knowledge/ # FAQ scope rules
src/sei_voice_agent/prompts/   # System prompt text
src/sei_voice_agent/services/  # Router, responder, voice processor
src/sei_voice_agent/telemetry/ # Logging and call telemetry
tests/                         # Test folder
```

## Troubleshooting

- If the agent is silent, verify the Deepgram, Groq, and Cartesia keys first.
- If the browser cannot connect, confirm LiveKit URL and API credentials.
- If the FAQ is not loading, verify `WISE_FAQ_DOC_PATH` points to `data/wise_where_is_my_money_faq.md`.
- On Windows, run from the repository root so relative paths resolve correctly.
