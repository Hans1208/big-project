package com.aivle.bigproject.config;

import com.aivle.bigproject.audio.AudioStreamHandshakeInterceptor;
import com.aivle.bigproject.audio.ExternalCallAuthInterceptor;
import com.aivle.bigproject.audio.ExternalCallWebSocketHandler;
import com.aivle.bigproject.audio.OperatorWebSocketHandler;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final ExternalCallWebSocketHandler externalCallWebSocketHandler;
    private final ExternalCallAuthInterceptor externalCallAuthInterceptor;
    private final OperatorWebSocketHandler operatorWebSocketHandler;
    private final AudioStreamHandshakeInterceptor audioStreamHandshakeInterceptor;

    public WebSocketConfig(ExternalCallWebSocketHandler externalCallWebSocketHandler,
                           ExternalCallAuthInterceptor externalCallAuthInterceptor,
                           OperatorWebSocketHandler operatorWebSocketHandler,
                           AudioStreamHandshakeInterceptor audioStreamHandshakeInterceptor) {
        this.externalCallWebSocketHandler = externalCallWebSocketHandler;
        this.externalCallAuthInterceptor = externalCallAuthInterceptor;
        this.operatorWebSocketHandler = operatorWebSocketHandler;
        this.audioStreamHandshakeInterceptor = audioStreamHandshakeInterceptor;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        // 필터 체인은 /ws/audio/**를 permitAll로 통과시키고, 인증은 각 핸드셰이크 인터셉터가 맡는다
        // (브라우저의 new WebSocket()에는 Authorization 헤더를 넣을 수 없어서 필터 체인만으로는
        // 막을 방법이 없다 — 막으면 브라우저가 붙을 방법이 아예 사라진다).

        // 외부 서버(전화/SIP 게이트웨이 등)가 통화 오디오를 흘려보내는 레그.
        // 서버 대 서버 연결이라 헤더를 자유롭게 붙일 수 있으므로 공유 비밀키로 인증한다.
        registry.addHandler(externalCallWebSocketHandler, "/ws/audio/external")
                .addInterceptors(externalCallAuthInterceptor);

        // 브라우저(오퍼레이터)가 특정 통화를 골라 붙는 레그. 1회성 티켓으로 인증한다.
        registry.addHandler(operatorWebSocketHandler, "/ws/audio/operator")
                .addInterceptors(audioStreamHandshakeInterceptor)
                .setAllowedOrigins("http://localhost:5173");
    }
}
