from __future__ import annotations


import asyncio
from enum import Enum


import structlog
from pipecat.frames.frames import (
    EndTaskFrame,
    InterruptionFrame,
    InterimTranscriptionFrame,
    OutputTransportMessageFrame,
    TTSSpeakFrame,
    TTSStoppedFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    VADUserStartedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


from sei_voice_agent.core.settings import get_settings
from sei_voice_agent.services.merged_router import MergedConversationScopeRouter
from sei_voice_agent.services.responder import AnswerResponder
from sei_voice_agent.telemetry.call_telemetry import CallTelemetry


logger = structlog.get_logger(__name__)



class ConversationState(str, Enum):
    ACTIVE = "active"
    AWAITING_SCOPE_CONFIRMATION = "awaiting_scope_confirmation"
    ENDING = "ending"



class WiseVoiceAgentProcessor(FrameProcessor):
    def __init__(self) -> None:
        super().__init__()
        settings = get_settings()
        self._router = MergedConversationScopeRouter()
        self._responder = AnswerResponder()
        self._telemetry = CallTelemetry(settings.call_telemetry_path)
        self._lock = asyncio.Lock()
        self._state = ConversationState.ACTIVE
        self._last_final_transcript = ""
        self._last_assistant_message = ""
        self._end_after_tts = False
        self._closing = False
        self._assistant_speaking = False
        self._latest_queued_text: str | None = None
        self._first_user_utterance_processed = False


    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)


        if isinstance(frame, InterimTranscriptionFrame):
            return


        if isinstance(frame, (UserStartedSpeakingFrame, VADUserStartedSpeakingFrame)):
            # Barge-in: caller starts speaking while TTS is active, so interrupt speech.
            if self._assistant_speaking:
                logger.info("barge_in_detected", state=self._state.value)
                self._telemetry.log("barge_in_detected", state=self._state.value)
                self._assistant_speaking = False
                if self._closing:
                    self._closing = False
                    self._end_after_tts = False
                    self._state = ConversationState.ACTIVE
                await self.push_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
                await self._push_demo_event(
                    {
                        "type": "demo-status",
                        "status": "listening",
                        "label": "Listening",
                    }
                )
            await self.push_frame(frame, direction)
            return


        if isinstance(frame, TranscriptionFrame) and direction == FrameDirection.DOWNSTREAM:
            if self._closing:
                return


            user_text = frame.text.strip()
            if not user_text:
                return


            normalized = self._normalize_text(user_text)
            if not normalized or normalized == self._last_final_transcript:
                return


            self._last_final_transcript = normalized


            if self._lock.locked():
                self._latest_queued_text = user_text
                self._telemetry.log("turn_queued", text=user_text)
                return


            async with self._lock:
                await self._process_turn_with_queue(user_text)
                self._first_user_utterance_processed = True
            return


        if isinstance(frame, TTSStoppedFrame) and self._end_after_tts:
            await self._push_demo_event(
                {
                    "type": "demo-status",
                    "status": "ending",
                    "label": "Ending call",
                }
            )
            self._end_after_tts = False
            self._closing = False
            self._assistant_speaking = False
            self._state = ConversationState.ENDING
            self._telemetry.log("call_ending")
            await self.push_frame(EndTaskFrame(), FrameDirection.DOWNSTREAM)
            return


        if isinstance(frame, TTSStoppedFrame):
            self._assistant_speaking = False
            self._telemetry.log("tts_stopped")
            await self._push_demo_event(
                {
                    "type": "demo-status",
                    "status": "listening",
                    "label": "Listening",
                }
            )
            await self.push_frame(frame, direction)
            return


        await self.push_frame(frame, direction)


    async def _process_turn_with_queue(self, user_text: str) -> None:
        current_text = user_text
        while current_text:
            normalized = self._normalize_text(current_text)
            if not normalized:
                current_text = self._latest_queued_text
                self._latest_queued_text = None
                continue


            logger.info(
                "caller_transcript",
                text=current_text,
                normalized_text=normalized,
                state=self._state.value,
            )
            self._telemetry.log("caller_transcript", text=current_text, state=self._state.value)
            await self._push_demo_event(
                {
                    "type": "demo-transcript",
                    "role": "user",
                    "text": current_text,
                    "state": self._state.value,
                }
            )
            await self._push_demo_event(
                {
                    "type": "demo-status",
                    "status": "thinking",
                    "label": "Thinking",
                }
            )


            reply = await self._handle_turn(current_text)
            if reply:
                self._last_assistant_message = reply
                self._telemetry.log("assistant_reply", text=reply, state=self._state.value)
                await self._push_demo_event(
                    {
                        "type": "demo-transcript",
                        "role": "assistant",
                        "text": reply,
                        "state": self._state.value,
                    }
                )
                await self._push_demo_event(
                    {
                        "type": "demo-status",
                        "status": "speaking",
                        "label": "Speaking",
                    }
                )
                self._assistant_speaking = True
                await self.push_frame(TTSSpeakFrame(reply), FrameDirection.DOWNSTREAM)


            if self._latest_queued_text:
                current_text = self._latest_queued_text
                self._latest_queued_text = None
            else:
                current_text = ""


    async def _handle_turn(self, user_text: str) -> str | None:
        try:
            # Route through the merged router for all decisions
            decision = await asyncio.to_thread(
                self._router.decide,
                state=self._state.value,
                last_assistant_message=self._last_assistant_message,
                user_text=user_text,
            )


            logger.info(
                "merged_router_decision",
                intent=decision.intent,
                route=decision.route,
                allowed=decision.allowed,
                should_end_call=decision.should_end_call,
                reason=decision.reason,
                reply=decision.reply,
                state=self._state.value,
            )
            self._telemetry.log(
                "merged_router_decision",
                intent=decision.intent,
                route=decision.route,
                allowed=decision.allowed,
                should_end_call=decision.should_end_call,
                reason=decision.reason,
            )


            # End call
            if decision.intent == "end_call" or decision.should_end_call:
                self._state = ConversationState.ENDING
                self._end_after_tts = True
                self._closing = True
                return decision.reply or "Thanks for calling. Goodbye."


            # Acknowledgment - just return router's reply
            if decision.intent == "acknowledgment":
                self._state = ConversationState.ACTIVE
                return decision.reply or "Is there anything else I can help with?"


            # Clarification needed
            if decision.intent == "clarify":
                self._state = ConversationState.ACTIVE
                return decision.reply or "Sorry, can you say that again?"


            # Caller wants to continue
            if decision.intent == "continue":
                self._state = ConversationState.ACTIVE
                return decision.reply or "Alright. What transfer tracking question can I help with?"


            # Transfer tracking question - get LLM answer
            if decision.route == "faq_answer" and decision.allowed:
                try:
                    answer = await asyncio.to_thread(
                        self._responder.answer,
                        user_text,
                        self._last_assistant_message,
                    )
                    self._state = ConversationState.ACTIVE
                    return answer
                except Exception as e:
                    logger.error("responder_error", error=str(e))
                    self._telemetry.log("responder_error", error=str(e))
                    return "I'm having trouble getting that information. Can you ask again?"


            # Out of scope - use router's reply
            if decision.intent == "out_of_scope":
                self._state = ConversationState.AWAITING_SCOPE_CONFIRMATION
                return (
                    decision.reply
                    or "That is outside Wise transfer tracking. If you want, I can keep helping with transfer questions, or we can end the call."
                )


            # Default: let router decide
            self._state = ConversationState.ACTIVE
            return decision.reply or ""


        except Exception as e:
            logger.error("handle_turn_error", error=str(e))
            self._telemetry.log("handle_turn_error", error=str(e))
            return "Sorry, I'm having trouble. Can you ask that again?"


    def _normalize_text(self, text: str) -> str:
        cleaned = text.lower().strip()
        for ch in ("?", ".", ",", "!", ";", ":", "'", '"'):
            cleaned = cleaned.replace(ch, "")
        cleaned = " ".join(cleaned.split())
        if len(cleaned) <= 2:
            return ""
        return cleaned


    def _looks_transfer_related(self, text: str) -> bool:
        lowered = text.lower()
        hints = ("transfer", "money", "recipient", "sender", "status", "sent", "received", "pending", "complete")
        return any(token in lowered for token in hints)


    def _looks_fragmentary(self, text: str) -> bool:
        lowered = text.lower().strip()
        words = lowered.split()
        if len(words) <= 4:
            return True
        dangling = ("and", "or", "but", "by", "with", "because", "if", "when", "like")
        return lowered.endswith(dangling)


    async def _push_demo_event(self, payload: dict) -> None:
        await self.push_frame(
            OutputTransportMessageFrame(message=payload),
            FrameDirection.DOWNSTREAM,
        )

