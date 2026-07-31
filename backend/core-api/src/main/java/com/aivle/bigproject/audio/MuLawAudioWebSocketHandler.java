package com.aivle.bigproject.audio;

import java.nio.ByteBuffer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.BinaryMessage;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.BinaryWebSocketHandler;

// 8비트 G.711 μ-law로 인코딩된 오디오 프레임을 WebSocket을 통해 수신한다.
// 바이너리 메시지의 각 바이트가 곧 μ-law 샘플 1개이므로 별도 프레이밍 없이 그대로 디코딩한다.
@Component
public class MuLawAudioWebSocketHandler extends BinaryWebSocketHandler {

    private static final Logger log = LoggerFactory.getLogger(MuLawAudioWebSocketHandler.class);

    // ITU-T G.711 μ-law 디코딩 바이어스(표준값 0x84/132). PCM 선형 변환식에 사용된다.
    private static final int MU_LAW_BIAS = 0x84;

    private final AudioSessionRegistry sessionRegistry;

    public MuLawAudioWebSocketHandler(AudioSessionRegistry sessionRegistry) {
        this.sessionRegistry = sessionRegistry;
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        sessionRegistry.register(session);
        log.info("μ-law audio stream connected: session={}", session.getId());
    }

    @Override
    protected void handleBinaryMessage(WebSocketSession session, BinaryMessage message) {
        ByteBuffer payload = message.getPayload();
        byte[] muLawBytes = new byte[payload.remaining()];
        payload.get(muLawBytes);

        short[] pcm16 = decode(muLawBytes);
        onSamplesDecoded(session, pcm16);
    }

    // 디코딩된 16비트 선형 PCM 샘플을 소비하는 지점. 기본은 로깅만 하므로
    // 실제 활용(STT 전달, 저장 등)이 필요하면 이 클래스를 상속해 재정의한다.
    protected void onSamplesDecoded(WebSocketSession session, short[] pcm16Samples) {
        log.debug("session={} decoded {} PCM samples", session.getId(), pcm16Samples.length);
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.warn("μ-law audio stream transport error: session={}", session.getId(), exception);
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        sessionRegistry.unregister(session);
        log.info("μ-law audio stream closed: session={} status={}", session.getId(), status);
    }

    private static short[] decode(byte[] muLawBytes) {
        short[] pcm = new short[muLawBytes.length];
        for (int i = 0; i < muLawBytes.length; i++) {
            pcm[i] = toLinear(muLawBytes[i]);
        }
        return pcm;
    }

    private static short toLinear(byte encoded) {
        int mu = ~encoded & 0xFF;
        int sign = mu & 0x80;
        int exponent = (mu >> 4) & 0x07;
        int mantissa = mu & 0x0F;
        int magnitude = ((mantissa << 3) + MU_LAW_BIAS) << exponent;
        int sample = magnitude - MU_LAW_BIAS;
        return (short) (sign != 0 ? -sample : sample);
    }
}
