from functools import lru_cache
from pathlib import Path


from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		case_sensitive=False,
		extra="ignore",
	)


	app_env: str = Field(default="local", alias="APP_ENV")
	app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
	app_port: int = Field(default=7860, alias="APP_PORT")
	log_level: str = Field(default="INFO", alias="LOG_LEVEL")


	deepgram_api_key: str = Field(default="", alias="DEEPGRAM_API_KEY")
	groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
	groq_model: str = Field(default="gpt-oss-20b", alias="GROQ_MODEL")
	cartesia_api_key: str = Field(default="", alias="CARTESIA_API_KEY")
	cartesia_model: str = Field(default="sonic-3", alias="CARTESIA_MODEL")
	cartesia_voice_id: str = Field(default="", alias="CARTESIA_VOICE_ID")
	livekit_url: str = Field(default="", alias="LIVEKIT_URL")
	livekit_api_key: str = Field(default="", alias="LIVEKIT_API_KEY")
	livekit_api_secret: str = Field(default="", alias="LIVEKIT_API_SECRET")
	livekit_room_prefix: str = Field(default="sei-wise", alias="LIVEKIT_ROOM_PREFIX")


	wise_faq_doc_path: str = Field(alias="WISE_FAQ_DOC_PATH")
	call_telemetry_dir: str = Field(default="logs/calls", alias="CALL_TELEMETRY_DIR")


	session_timeout_seconds: int = Field(
		default=300,
		alias="SESSION_TIMEOUT_SECONDS",
	)
	barge_in_enabled: bool = Field(
		default=True,
		alias="BARGE_IN_ENABLED",
	)
	vad_confidence: float = Field(
		default=0.75,
		alias="VAD_CONFIDENCE",
	)
	vad_start_secs: float = Field(
		default=0.12,
		alias="VAD_START_SECS",
	)
	vad_stop_secs: float = Field(
		default=0.45,
		alias="VAD_STOP_SECS",
	)
	vad_min_volume: float = Field(
		default=0.45,
		alias="VAD_MIN_VOLUME",
	)
	pause_call_seconds: int = Field(
		default=10,
		alias="PAUSE_CALL_SECONDS",
	)
	pause_checkin_message: str = Field(
		default="Are you still there? Can we continue?",
		alias="PAUSE_CHECKIN_MESSAGE",
	)
	enable_edge_tts_fallback: bool = Field(
		default=True,
		alias="ENABLE_EDGE_TTS_FALLBACK",
	)


	@property
	def wise_faq_path(self) -> Path:
		return Path(self.wise_faq_doc_path)


	@property
	def call_telemetry_path(self) -> Path:
		return Path(self.call_telemetry_dir)



@lru_cache(maxsize=1)
def get_settings() -> Settings:
	return Settings()
