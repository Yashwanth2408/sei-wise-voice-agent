from __future__ import annotations


import asyncio
import sys
from pathlib import Path


from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.runner.run import app, main
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams


from sei_voice_agent.core.settings import get_settings
from sei_voice_agent.services.voice_processor import WiseVoiceAgentProcessor
from sei_voice_agent.telemetry.logging import configure_logging


FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


if FRONTEND_DIR.exists():
	app.mount("/demo-assets", StaticFiles(directory=FRONTEND_DIR), name="demo-assets")



@app.get("/demo", include_in_schema=False)
async def demo_page():
	return FileResponse(FRONTEND_DIR / "index.html")



async def bot(runner_args):
	settings = get_settings()
	configure_logging(settings.log_level)


	transport = await create_transport(
		runner_args,
		{
			"webrtc": lambda: TransportParams(
				audio_in_enabled=True,
				audio_out_enabled=True,
				audio_in_sample_rate=16000,
				audio_out_sample_rate=24000,
				audio_in_channels=1,
				audio_out_channels=1,
				vad_analyzer=SileroVADAnalyzer(),
			)
		},
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


	# ── Greeting fires AFTER the client fully connects, not on a timer ──────
	@transport.event_handler("on_client_connected")
	async def on_client_connected(transport, client):
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