package com.aivle.bigproject.config;

import com.aivle.bigproject.audio.AudioStreamHandshakeInterceptor;
import com.aivle.bigproject.audio.ExternalCallAuthInterceptor;
import com.aivle.bigproject.audio.ExternalCallWebSocketHandler;
import com.aivle.bigproject.audio.InPersonAudioHandshakeInterceptor;
import com.aivle.bigproject.audio.InPersonRecordingWebSocketHandler;
import com.aivle.bigproject.audio.OperatorWebSocketHandler;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;
import org.springframework.web.socket.server.standard.ServletServerContainerFactoryBean;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final ExternalCallWebSocketHandler externalCallWebSocketHandler;
    private final ExternalCallAuthInterceptor externalCallAuthInterceptor;
    private final OperatorWebSocketHandler operatorWebSocketHandler;
    private final AudioStreamHandshakeInterceptor audioStreamHandshakeInterceptor;
    // app.cors.allowed-origins(콤마 구분)를 WebConfig의 REST CORS 설정과 공유한다.
    private final String[] allowedOrigins;
    private final InPersonRecordingWebSocketHandler inPersonRecordingWebSocketHandler;
    private final InPersonAudioHandshakeInterceptor inPersonAudioHandshakeInterceptor;

    public WebSocketConfig(ExternalCallWebSocketHandler externalCallWebSocketHandler,
                           ExternalCallAuthInterceptor externalCallAuthInterceptor,
                           OperatorWebSocketHandler operatorWebSocketHandler,
                           AudioStreamHandshakeInterceptor audioStreamHandshakeInterceptor,
                           @Value("${app.cors.allowed-origins:http://localhost:5173}") String allowedOrigins,
                           InPersonRecordingWebSocketHandler inPersonRecordingWebSocketHandler,
                           InPersonAudioHandshakeInterceptor inPersonAudioHandshakeInterceptor) {
        this.externalCallWebSocketHandler = externalCallWebSocketHandler;
        this.externalCallAuthInterceptor = externalCallAuthInterceptor;
        this.operatorWebSocketHandler = operatorWebSocketHandler;
        this.audioStreamHandshakeInterceptor = audioStreamHandshakeInterceptor;
        this.allowedOrigins = allowedOrigins.split("\\s*,\\s*");
        this.inPersonRecordingWebSocketHandler = inPersonRecordingWebSocketHandler;
        this.inPersonAudioHandshakeInterceptor = inPersonAudioHandshakeInterceptor;
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
                .setAllowedOrigins(allowedOrigins);

        // 브라우저(상담원)가 대면 상담 녹음을 시작할 때 붙는 레그. 통화가 아니라 특정 상담의
        // 녹음 세션이라 CallRegistry를 거치지 않지만, 인증 방식(1회성 티켓)은 operator와 동일하다.
        registry.addHandler(inPersonRecordingWebSocketHandler, "/ws/audio/in-person")
                .addInterceptors(inPersonAudioHandshakeInterceptor)
                .setAllowedOrigins(allowedOrigins);
    }

    // Tomcat(WebSocket 컨테이너)의 바이너리 메시지 버퍼 기본값은 8KB다. 전화 상담(operator)은
    // 4096 샘플짜리 μ-law 프레임(4KB)만 보내서 문제가 없었지만, 대면 상담은 MediaRecorder가
    // 5초마다 만드는 webm 조각을 그대로 보내서(수십 KB) 기본값을 넘기면 Tomcat이 "No async
    // message support and buffer too small"로 소켓을 정책 위반(1009) 종료시킨다.
    // supportsPartialMessages()로 조각내 받는 대신, 5초 오디오가 넉넉히 들어갈 만큼 버퍼를 키운다.
    @Bean
    public ServletServerContainerFactoryBean createWebSocketContainer() {
        ServletServerContainerFactoryBean container = new ServletServerContainerFactoryBean();
        container.setMaxBinaryMessageBufferSize(2 * 1024 * 1024);
        container.setMaxTextMessageBufferSize(64 * 1024);
        return container;
    }
}
