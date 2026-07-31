package com.aivle.bigproject.audio;

import com.aivle.bigproject.audio.dto.AudioSessionResponse;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AudioSessionController {

    private final AudioSessionRegistry sessionRegistry;

    public AudioSessionController(AudioSessionRegistry sessionRegistry) {
        this.sessionRegistry = sessionRegistry;
    }

    // GET /api/audio/mulaw/sessions — 현재 연결된 μ-law 오디오 WebSocket 세션 목록
    @GetMapping("/api/audio/mulaw/sessions")
    public List<AudioSessionResponse> listSessions() {
        return sessionRegistry.list();
    }
}
