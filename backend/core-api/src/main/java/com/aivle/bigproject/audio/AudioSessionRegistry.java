package com.aivle.bigproject.audio;

import com.aivle.bigproject.audio.dto.AudioSessionResponse;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketSession;

// 현재 연결되어 있는 μ-law 오디오 WebSocket 세션을 추적한다.
// 프론트엔드가 GET /api/audio/mulaw/sessions로 연결 목록을 조회할 때 이 레지스트리를 사용한다.
@Component
public class AudioSessionRegistry {

    private record Entry(WebSocketSession session, Instant connectedAt) {
    }

    private final Map<String, Entry> sessions = new ConcurrentHashMap<>();

    public void register(WebSocketSession session) {
        sessions.put(session.getId(), new Entry(session, Instant.now()));
    }

    public void unregister(WebSocketSession session) {
        sessions.remove(session.getId());
    }

    public List<AudioSessionResponse> list() {
        return sessions.values().stream()
                .map(entry -> new AudioSessionResponse(
                        entry.session().getId(),
                        remoteAddress(entry.session()),
                        entry.connectedAt()))
                .toList();
    }

    private static String remoteAddress(WebSocketSession session) {
        return session.getRemoteAddress() != null ? session.getRemoteAddress().toString() : null;
    }
}
