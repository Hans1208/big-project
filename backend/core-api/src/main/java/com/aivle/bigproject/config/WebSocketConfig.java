package com.aivle.bigproject.config;

import com.aivle.bigproject.audio.MuLawAudioWebSocketHandler;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final MuLawAudioWebSocketHandler muLawAudioWebSocketHandler;

    public WebSocketConfig(MuLawAudioWebSocketHandler muLawAudioWebSocketHandler) {
        this.muLawAudioWebSocketHandler = muLawAudioWebSocketHandler;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(muLawAudioWebSocketHandler, "/ws/audio/mulaw")
                .setAllowedOrigins("http://localhost:5173");
    }
}
