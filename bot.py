from __future__ import annotations


import asyncio
import sys
import uuid
from pathlib import Path

# Add src directory to path so wise_voice_agent can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.runner.run import app, main
from pipecat.runner.types import LiveKitRunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transcriptions.language import Language
from pipecat.transports.livekit.transport import LiveKitParams


from wise_voice_agent.core.settings import get_settings
from wise_voice_agent.services.voice_processor import WiseVoiceAgentProcessor
from wise_voice_agent.telemetry.logging import configure_logging


FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
_LIVEKIT_AGENT_TASKS: set[asyncio.Task] = set()


if FRONTEND_DIR.exists():
	app.mount("/demo-assets", StaticFiles(directory=FRONTEND_DIR), name="demo-assets")



@app.get("/demo", include_in_schema=False)
async def demo_page():
	return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/livekit/session")
async def livekit_session():
	settings = get_settings()
	if not settings.livekit_url or not settings.livekit_api_key or not settings.livekit_api_secret:
		raise HTTPException(
			status_code=503,
			detail="LiveKit is not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET.",
		)

	room_name = f"{settings.livekit_room_prefix}-{uuid.uuid4().hex[:10]}"
	user_identity = f"caller-{uuid.uuid4().hex[:8]}"
	agent_identity = f"agent-{uuid.uuid4().hex[:8]}"

	await _create_livekit_room(settings, room_name)
	user_token = _create_livekit_token(
		settings,
		room_name=room_name,
		identity=user_identity,
		name="Caller",
	)
	agent_token = _create_livekit_token(
		settings,
		room_name=room_name,
		identity=agent_identity,
		name="Wise Agent",
	)

	runner_args = LiveKitRunnerArguments(
		room_name=room_name,
		url=settings.livekit_url,
		token=agent_token,
	)
	task = asyncio.create_task(bot(runner_args))
	_LIVEKIT_AGENT_TASKS.add(task)
	task.add_done_callback(_LIVEKIT_AGENT_TASKS.discard)

	return {
		"url": settings.livekit_url,
		"token": user_token,
		"roomName": room_name,
		"identity": user_identity,
	}


def _create_livekit_token(settings, *, room_name: str, identity: str, name: str) -> str:
	from livekit import api

	return (
		api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
		.with_identity(identity)
		.with_name(name)
		.with_grants(
			api.VideoGrants(
				room_join=True,
				room=room_name,
				can_publish=True,
				can_subscribe=True,
				can_publish_data=True,
			)
		)
		.to_jwt()
	)


async def _create_livekit_room(settings, room_name: str) -> None:
	from livekit import api

	livekit_api = api.LiveKitAPI(
		url=settings.livekit_url,
		api_key=settings.livekit_api_key,
		api_secret=settings.livekit_api_secret,
	)
	try:
		await livekit_api.room.create_room(
			api.CreateRoomRequest(
				name=room_name,
				empty_timeout=60,
				max_participants=2,
			)
		)
	finally:
		await livekit_api.aclose()



async def bot(runner_args):
	settings = get_settings()
	configure_logging(settings.log_level)


	transport = await create_transport(
		runner_args,
		{
			"livekit": lambda: LiveKitParams(
				audio_in_enabled=True,
				audio_out_enabled=True,
				audio_in_sample_rate=16000,
				audio_out_sample_rate=24000,
				audio_in_channels=1,
				audio_out_channels=1,
			)
		},
	)

	vad = VADProcessor(
		vad_analyzer=SileroVADAnalyzer(
			sample_rate=16000,
			params=VADParams(
				confidence=settings.vad_confidence,
				start_secs=settings.vad_start_secs,
				stop_secs=settings.vad_stop_secs,
				min_volume=settings.vad_min_volume,
			),
		),
		speech_activity_period=0.12,
		audio_idle_timeout=0.7,
	)


	stt = DeepgramSTTService(
		api_key=settings.deepgram_api_key,
		model="nova-3",
		language="en-US",
		sample_rate=16000,
		channels=1,
		encoding="linear16",
		interim_results=True,
		punctuate=True,
		smart_format=True,
		utterance_end_ms=700,
	)


	tts = CartesiaTTSService(
		api_key=settings.cartesia_api_key,
		sample_rate=24000,
		settings=CartesiaTTSService.Settings(
			model=settings.cartesia_model,
			voice=settings.cartesia_voice_id,
			language=Language.EN,
		),
	)


	agent = WiseVoiceAgentProcessor()


	pipeline = Pipeline(
		[
			transport.input(),
			vad,
			stt,
			agent,
			tts,
			transport.output(),
		]
	)


	task = PipelineTask(
		pipeline,
		params=PipelineParams(
			audio_in_sample_rate=16000,
			audio_out_sample_rate=24000,
			enable_metrics=True,
		),
		idle_timeout_secs=settings.session_timeout_seconds,
	)


	# Greeting fires after the browser participant joins the LiveKit room.
	@transport.event_handler("on_first_participant_joined")
	async def on_first_participant_joined(transport, participant_id):
		await task.queue_frames(
			[
				TTSSpeakFrame(
					"Hello. I can help with Wise transfer tracking questions "
					"about where your money is. How can I help today?"
				)
			]
		)


	runner = PipelineRunner(handle_sigint=True)
	await runner.run(task)


if __name__ == "__main__":
	# Prevent UnicodeEncodeError on Windows consoles when Pipecat prints emoji.
	if hasattr(sys.stdout, "reconfigure"):
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	if hasattr(sys.stderr, "reconfigure"):
		sys.stderr.reconfigure(encoding="utf-8", errors="replace")
	main()
