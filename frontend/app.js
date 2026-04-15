const state = {
    pc: null,
    dataChannel: null,
    localStream: null,
    remoteStream: null,
    sessionId: null,
    pcId: null,
    candidateQueue: [],
    canSendCandidates: false,
    userAudioContext: null,
    assistantAudioContext: null,
    userAnalyser: null,
    assistantAnalyser: null,
    userMeterFrame: null,
    assistantMeterFrame: null,
    started: false,
    muted: false,
    callStartedAt: null,
    timerInterval: null,
    turnCount: 0,
};


const startButton = document.getElementById("start-call");
const endButton = document.getElementById("end-call");
const muteButton = document.getElementById("mute-call");
const clearButton = document.getElementById("clear-transcript");
const transcriptEl = document.getElementById("transcript");
const remoteAudioEl = document.getElementById("remote-audio");
const statusPill = document.getElementById("status-pill");
const statusText = document.getElementById("status-text");
const connectionLabel = document.getElementById("connection-label");
const sessionText = document.getElementById("session-text");
const micState = document.getElementById("mic-state");
const agentState = document.getElementById("agent-state");
const userMeter = document.getElementById("user-meter");
const assistantMeter = document.getElementById("assistant-meter");
const durationText = document.getElementById("duration-text");
const turnCountText = document.getElementById("turn-count");
const lastEventText = document.getElementById("last-event");


startButton.addEventListener("click", startCall);
endButton.addEventListener("click", endCall);
muteButton.addEventListener("click", toggleMute);
clearButton.addEventListener("click", clearTranscript);


function setStatus(kind, text, pillText = text) {
    statusPill.className = `status-pill ${kind}`;
    statusPill.textContent = pillText;
    statusText.textContent = text;
}


function setConnection(text) {
    connectionLabel.textContent = text;
}


function addTranscript(role, text) {
    const emptyState = transcriptEl.querySelector(".empty-state");
    if (emptyState) {
        emptyState.remove();
    }


    const row = document.createElement("div");
    row.className = `transcript-line ${role}`;


    const tag = document.createElement("span");
    tag.className = "transcript-tag";
    tag.textContent = role === "assistant" ? "Agent" : "Caller";


    const bubble = document.createElement("div");
    bubble.className = "transcript-bubble";


    const paragraph = document.createElement("p");
    paragraph.textContent = text;


    const time = document.createElement("span");
    time.className = "transcript-time";
    time.textContent = new Date().toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
    });


    bubble.appendChild(paragraph);
    bubble.appendChild(time);
    row.appendChild(tag);
    row.appendChild(bubble);
    transcriptEl.appendChild(row);
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
    state.turnCount += 1;
    turnCountText.textContent = String(state.turnCount);
    lastEventText.textContent = role === "assistant" ? "Agent spoke" : "Caller spoke";
}


function clearTranscript() {
    transcriptEl.innerHTML = `
        <div class="empty-state">
            Start the call to see live caller and assistant turns appear here.
        </div>
    `;
    state.turnCount = 0;
    turnCountText.textContent = "0";
    lastEventText.textContent = "Cleared";
}


function formatDuration(ms) {
    const totalSeconds = Math.max(0, Math.floor(ms / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}


function startTimer() {
    if (state.timerInterval) {
        clearInterval(state.timerInterval);
    }
    state.callStartedAt = Date.now();
    durationText.textContent = "00:00";
    state.timerInterval = setInterval(() => {
        durationText.textContent = formatDuration(Date.now() - state.callStartedAt);
    }, 1000);
}


function stopTimer() {
    if (state.timerInterval) {
        clearInterval(state.timerInterval);
        state.timerInterval = null;
    }
    state.callStartedAt = null;
    durationText.textContent = "00:00";
}


function applyMuteState() {
    if (state.localStream) {
        state.localStream.getAudioTracks().forEach((track) => {
            track.enabled = !state.muted;
        });
    }
    muteButton.textContent = state.muted ? "Unmute" : "Mute";
    micState.textContent = state.muted ? "Muted" : "Listening";
    lastEventText.textContent = state.muted ? "Mic muted" : "Mic unmuted";
}


function toggleMute() {
    if (!state.started || !state.localStream) {
        return;
    }
    state.muted = !state.muted;
    applyMuteState();
}


function updateMeterBars(container, level) {
    const bars = container.querySelectorAll("span");
    bars.forEach((bar, index) => {
        const multiplier = 0.45 + index * 0.11;
        const height = Math.max(14, Math.min(100, level * 120 * multiplier));
        bar.style.height = `${height}%`;
        bar.style.opacity = `${Math.min(1, 0.45 + level * 1.2)}`;
    });
}


function animateMeter(analyser, container, labelEl, activeText, idleText) {
    const data = new Uint8Array(analyser.fftSize);


    const tick = () => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i += 1) {
            const normalized = (data[i] - 128) / 128;
            sum += normalized * normalized;
        }
        const rms = Math.sqrt(sum / data.length);
        updateMeterBars(container, rms * 3.8);
        labelEl.textContent = rms > 0.02 ? activeText : idleText;
        const frameId = requestAnimationFrame(tick);
        if (container === userMeter) {
            state.userMeterFrame = frameId;
        } else {
            state.assistantMeterFrame = frameId;
        }
    };


    tick();
}


async function setupAnalyser(stream, side) {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor || !stream) {
        return;
    }


    const context = new AudioContextCtor();
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);


    if (side === "user") {
        state.userAudioContext = context;
        state.userAnalyser = analyser;
        animateMeter(analyser, userMeter, micState, "Speaking", "Listening");
    } else {
        state.assistantAudioContext = context;
        state.assistantAnalyser = analyser;
        animateMeter(analyser, assistantMeter, agentState, "Responding", "Waiting");
    }
}


function stopMeters() {
    if (state.userMeterFrame) {
        cancelAnimationFrame(state.userMeterFrame);
        state.userMeterFrame = null;
    }
    if (state.assistantMeterFrame) {
        cancelAnimationFrame(state.assistantMeterFrame);
        state.assistantMeterFrame = null;
    }
    updateMeterBars(userMeter, 0.1);
    updateMeterBars(assistantMeter, 0.1);
    micState.textContent = "Mic offline";
    agentState.textContent = "Waiting";
}


function randomId() {
    return Math.random().toString(16).slice(2, 10);
}


function buildClientReadyPayload() {
    return {
        label: "rtvi-ai",
        type: "client-ready",
        id: randomId(),
        data: {
            version: "1.0.0",
            about: {
                library: "sei-wise-demo-ui",
                library_version: "1.0.0",
                platform: navigator.platform,
                platform_version: navigator.userAgent,
                platform_details: {
                    browser: navigator.userAgent,
                    platform_type: "desktop",
                },
            },
        },
    };
}


async function startCall() {
    if (state.started) {
        return;
    }


    try {
        setStatus("live", "Requesting microphone access", "Starting");
        setConnection("Connecting");
        sessionText.textContent = "Initializing";
        startButton.disabled = true;


        state.localStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
            video: false,
        });
        await setupAnalyser(state.localStream, "user");


        const startResponse = await fetch("/start", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                createDailyRoom: false,
                enableDefaultIceServers: true,
                transport: "webrtc",
            }),
        });
        const startData = await startResponse.json();


        state.sessionId = startData.sessionId;
        sessionText.textContent = startData.sessionId;


        state.pc = new RTCPeerConnection({
            iceServers: startData.iceConfig?.iceServers || [],
        });
        state.remoteStream = new MediaStream();
        remoteAudioEl.srcObject = state.remoteStream;


        state.dataChannel = state.pc.createDataChannel("chat", { ordered: true });
        state.dataChannel.addEventListener("open", () => {
            setConnection("Connected");
            setStatus("live", "Call live. Speak naturally.", "Live");
            state.dataChannel.send(JSON.stringify(buildClientReadyPayload()));
        });
        state.dataChannel.addEventListener("message", onDataChannelMessage);


        const audioTrack = state.localStream.getAudioTracks()[0];
        if (!audioTrack) {
            throw new Error("No microphone track available");
        }
        state.pc.addTrack(audioTrack, state.localStream);


        state.pc.ontrack = (event) => {
            if (event.track.kind === "audio") {
                state.remoteStream.addTrack(event.track);
                setupAnalyser(state.remoteStream, "assistant");
            }
        };


        state.pc.onicecandidate = async (event) => {
            if (!event.candidate) {
                return;
            }


            if (!state.canSendCandidates || !state.pcId) {
                state.candidateQueue.push(event.candidate);
                return;
            }


            await sendIceCandidates([event.candidate]);
        };


        state.pc.onconnectionstatechange = () => {
            if (["failed", "disconnected", "closed"].includes(state.pc.connectionState)) {
                if (state.started) {
                    setStatus("warn", "Connection closed", "Closed");
                    setConnection("Disconnected");
                    void endCall();
                }
            }
        };


        const offer = await state.pc.createOffer();
        await state.pc.setLocalDescription(offer);


        const offerResponse = await fetch(`/sessions/${state.sessionId}/api/offer`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                sdp: state.pc.localDescription.sdp,
                type: state.pc.localDescription.type,
            }),
        });


        const answer = await offerResponse.json();
        state.pcId = answer.pc_id;


        await state.pc.setRemoteDescription({
            type: answer.type,
            sdp: answer.sdp,
        });


        state.canSendCandidates = true;
        if (state.candidateQueue.length) {
            const pending = [...state.candidateQueue];
            state.candidateQueue = [];
            await sendIceCandidates(pending);
        }


        state.started = true;
        endButton.disabled = false;
        muteButton.disabled = false;
        state.muted = false;
        applyMuteState();
        startTimer();
        lastEventText.textContent = "Call connected";
    } catch (error) {
        console.error(error);
        setStatus("warn", "Could not start the call", "Error");
        setConnection("Failed");
        await endCall();
    } finally {
        if (!state.started) {
            startButton.disabled = false;
        }
    }
}


async function sendIceCandidates(candidates) {
    if (!state.sessionId || !state.pcId || candidates.length === 0) {
        return;
    }


    await fetch(`/sessions/${state.sessionId}/api/offer`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            pc_id: state.pcId,
            candidates: candidates.map((candidate) => ({
                candidate: candidate.candidate,
                sdp_mid: candidate.sdpMid,
                sdp_mline_index: candidate.sdpMLineIndex,
            })),
        }),
    });
}


function onDataChannelMessage(event) {
    let message;
    try {
        message = JSON.parse(event.data);
    } catch (error) {
        return;
    }


    const payloads = extractDemoPayloads(message);
    for (const payload of payloads) {
        if (payload.type === "demo-transcript" && payload.text) {
            const role = payload.role === "assistant" ? "assistant" : "user";
            addTranscript(role, payload.text);
            continue;
        }
        if (payload.type === "demo-status" && payload.label) {
            const kind = payload.status === "ending" ? "warn" : "live";
            setStatus(kind, payload.label, payload.label);
            lastEventText.textContent = payload.label;
            if (payload.status === "ending") {
                void endCall();
            }
        }
    }
}


function extractDemoPayloads(message) {
    const results = [];
    const queue = [message];
    const seen = new Set();


    while (queue.length) {
        const current = queue.shift();
        if (!current || typeof current !== "object") {
            continue;
        }


        if (seen.has(current)) {
            continue;
        }
        seen.add(current);


        if (current.type === "signalling") {
            continue;
        }


        if (current.type === "demo-transcript" || current.type === "demo-status") {
            results.push(current);
        }


        if (Array.isArray(current)) {
            for (const item of current) {
                queue.push(item);
            }
            continue;
        }


        for (const value of Object.values(current)) {
            if (value && typeof value === "object") {
                queue.push(value);
            }
        }
    }


    return results;
}


async function endCall() {
    if (state.dataChannel && state.dataChannel.readyState === "open") {
        try {
            state.dataChannel.close();
        } catch (error) {
            console.warn(error);
        }
    }


    if (state.pc) {
        try {
            state.pc.getSenders().forEach((sender) => sender.track && sender.track.stop());
            state.pc.close();
        } catch (error) {
            console.warn(error);
        }
    }


    if (state.localStream) {
        state.localStream.getTracks().forEach((track) => track.stop());
    }


    if (state.remoteStream) {
        state.remoteStream.getTracks().forEach((track) => track.stop());
    }


    if (state.userAudioContext) {
        await state.userAudioContext.close();
    }


    if (state.assistantAudioContext) {
        await state.assistantAudioContext.close();
    }


    state.pc = null;
    state.dataChannel = null;
    state.localStream = null;
    state.remoteStream = null;
    state.sessionId = null;
    state.pcId = null;
    state.candidateQueue = [];
    state.canSendCandidates = false;
    state.userAudioContext = null;
    state.assistantAudioContext = null;
    state.userAnalyser = null;
    state.assistantAnalyser = null;
    state.started = false;
    state.muted = false;


    stopMeters();
    stopTimer();
    remoteAudioEl.srcObject = null;
    startButton.disabled = false;
    endButton.disabled = true;
    muteButton.disabled = true;
    muteButton.textContent = "Mute";
    setStatus("idle", "Ready for a live voice demo", "Idle");
    setConnection("Disconnected");
    sessionText.textContent = "Not started";
    lastEventText.textContent = "Disconnected";
}
    