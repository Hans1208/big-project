package com.aivle.bigproject.config;

import com.aivle.bigproject.audio.AudioStreamHandshakeInterceptor;
import com.aivle.bigproject.audio.MuLawAudioWebSocketHandler;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final MuLawAudioWebSocketHandler muLawAudioWebSocketHandler;
    private final AudioStreamHandshakeInterceptor audioStreamHandshakeInterceptor;

    public WebSocketConfig(MuLawAudioWebSocketHandler muLawAudioWebSocketHandler,
                           AudioStreamHandshakeInterceptor audioStreamHandshakeInterceptor) {
        this.muLawAudioWebSocketHandler = muLawAudioWebSocketHandler;
        this.audioStreamHandshakeInterceptor = audioStreamHandshakeInterceptor;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        // 핸드셰이크에서 1회성 티켓을 확인한다(AudioStreamHandshakeInterceptor).
        // 브라우저의 new WebSocket()에는 Authorization 헤더를 넣을 수 없어서 SecurityConfig의
        // 필터 체인으로는 이 경로를 막을 수 없다 — 막으면 브라우저가 붙을 방법이 사라진다.
        // 그래서 /ws/audio/**는 필터 체인에서 통과시키고 인증을 여기로 옮겼다.
        registry.addHandler(muLawAudioWebSocketHandler, "/ws/audio/mulaw")
                .addInterceptors(audioStreamHandshakeInterceptor)
                .setAllowedOrigins("http://localhost:5173");
    }
}
