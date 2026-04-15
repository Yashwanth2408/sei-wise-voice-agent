# Sei Wise Voice Agent

Sei Wise Voice Agent is a scoped voice support demo for Wise transfer-tracking questions. It listens to the caller over WebRTC, transcribes speech in real time, routes the request through a Wise-specific FAQ scope, and speaks a grounded answer back with TTS.

The project is intentionally narrow: it is designed to answer only "Where is my money?" style questions and to deflect everything else politely.

## What It Does

- Answers Wise transfer status questions such as processing, transfer sent, complete, and delayed transfers.
- Explains common reasons for transfer delays, missing funds, and recipient bank processing issues.
- Provides guidance on receipts, proof of payment, reference numbers, and payment method speed.
- Deflects out-of-scope questions like fees, exchange rates, account setup, fraud, card issues, and transfer cancellation.
- Ends the call cleanly when the caller asks to stop, hang up, or cut the call.

## Tech Stack

- Python 3.11+
- FastAPI
- Pipecat WebRTC pipeline
- Silero VAD
- Deepgram STT
- Groq for routing and answer generation
- Cartesia TTS
- Vanilla HTML, CSS, and JavaScript frontend

## How The System Works

1. The browser captures microphone audio and sends it to the backend over WebRTC.
2. Pipecat runs the streaming pipeline and uses Silero VAD to detect speech boundaries.
3. Deepgram converts speech to text.
4. The voice processor classifies the turn and decides whether the caller is in scope, out of scope, or ending the call.
5. Groq generates the reply for in-scope FAQ answers and conversational routing.
6. Cartesia converts the reply into spoken audio and sends it back to the browser.
7. The frontend shows a live transcript, audio meters, session status, and call controls.

## Repository Structure

```text
bot.py                         # Main Pipecat bootstrap entry point
check.py                       # Local helper script
data/wise_where_is_my_money_faq.md
frontend/                      # Demo UI served from /demo
logs/calls/                    # JSONL call telemetry output
src/sei_voice_agent/api/       # FastAPI app and API routes
src/sei_voice_agent/core/      # Settings and environment config
src/sei_voice_agent/knowledge/ # FAQ loading and scope rules
src/sei_voice_agent/prompts/   # System prompt text
src/sei_voice_agent/services/  # Router, responder, and voice processor
src/sei_voice_agent/telemetry/ # Logging and call telemetry
tests/                         # Test folder
```

## Scope Rules

### In Scope

The agent should answer questions about:

- Transfer status and where money is
- Processing, transfer sent, and complete statuses
- Delayed or stuck transfers
- Recipient bank processing delays
- Proof of payment and transfer receipts
- Reference numbers and banking partner references
- Payment speed for card, bank transfer, and SWIFT transfers

### Out of Scope

The agent should deflect questions about:

- Fees and exchange rates
- Account creation or setup
- Fraud or account security issues
- Wise card problems
- Transfer cancellation
- Recipient management that is not part of transfer tracking

## Conversation Behavior

- The agent keeps answers short, spoken, and conversational.
- Repeated questions should be answered with natural variation instead of the same wording every time.
- If the caller says things like "cut the call" or "end the call", the agent closes the call gracefully.
- If the caller asks something outside scope, the agent should politely explain the limitation and offer to continue with transfer-tracking questions or end the call.

## Configuration

Create a `.env` file in the project root with the following values:

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

WISE_FAQ_DOC_PATH=data/wise_where_is_my_money_faq.md
CALL_TELEMETRY_DIR=logs/calls
SESSION_TIMEOUT_SECONDS=300
ENABLE_EDGE_TTS_FALLBACK=true
```

### Important Variables

- `WISE_FAQ_DOC_PATH` is required. It points to the Wise FAQ markdown file used as the grounded knowledge source.
- `GROQ_API_KEY`, `DEEPGRAM_API_KEY`, and `CARTESIA_API_KEY` must be set for the live voice pipeline.
- `CALL_TELEMETRY_DIR` controls where per-call JSONL logs are written.
- `ENABLE_EDGE_TTS_FALLBACK` enables a fallback voice path if needed.

## Local Setup

1. Create and activate a virtual environment.
2. Install the Python dependencies.
3. Set the environment variables in `.env`.
4. Start the agent from the project root.

Example on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bot.py
```

## Running The Demo

Once the app is running, open the demo page in the browser:

- Demo UI: `/demo`
- Health check: `/health`
- Readiness check: `/ready`

The demo UI includes:

- A live audio monitor
- A real-time transcript feed
- Call start, mute, and end controls
- A visible FAQ boundary-test box

## API Endpoints

- `GET /health` returns the app status and configured model names.
- `GET /ready` confirms that the FAQ file is loaded and the API keys are present.
- `POST /start` begins a new voice session.
- `POST /sessions/{sessionId}/api/offer` completes the WebRTC offer/answer exchange.

## Frontend Behavior

The browser UI is built with plain HTML, CSS, and JavaScript and is served from the local demo assets. It:

- Requests microphone access
- Establishes the WebRTC session
- Streams the remote agent audio
- Shows live status updates and transcripts
- Automatically ends the call when the backend signals an ending state

## Telemetry

Call activity is logged to JSONL files in `logs/calls/`. These logs are useful for reviewing routing decisions, transcript turns, and call termination behavior.

## Troubleshooting

- If the app starts but the agent is silent, check the Deepgram, Groq, and Cartesia keys first.
- If the browser cannot connect, confirm the WebRTC transport is allowed in your environment.
- If the FAQ is not loading, verify `WISE_FAQ_DOC_PATH` points to `data/wise_where_is_my_money_faq.md`.
- If answers sound repetitive, confirm the latest responder and router changes are present and the Groq model is reachable.
- On Windows, always run the app from the repository root so relative paths resolve correctly.

## Notes

- The project is designed as a focused support demo, not a general-purpose assistant.
- The FAQ scope is intentionally strict so the agent stays grounded and predictable.
- The UI is intentionally product-like so the voice experience can be evaluated quickly.
