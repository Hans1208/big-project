package com.aivle.bigproject.audio;

import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.server.HandshakeInterceptor;

// 외부 서버(전화/SIP 게이트웨이 등)가 통화 오디오를 흘려보내려고 붙는 핸드셰이크를 인증한다.
//
// 이 연결은 브라우저가 아니라 우리 쪽에서 만든/신뢰하는 서버 클라이언트가 여는 것이므로
// Authorization 헤더를 자유롭게 붙일 수 있다. 그래서 오퍼레이터 쪽처럼 URL에 실리는 1회성
// 티켓 대신, 고정된 공유 비밀키(app.audio.external-api-key)를 헤더로 검증한다.
@Component
public class ExternalCallAuthInterceptor implements HandshakeInterceptor {

    private final String externalApiKey;

    public ExternalCallAuthInterceptor(@Value("${app.audio.external-api-key}") String externalApiKey) {
        this.externalApiKey = externalApiKey;
    }

    @Override
    public boolean beforeHandshake(ServerHttpRequest request, ServerHttpResponse response,
                                    WebSocketHandler wsHandler, Map<String, Object> attributes) {
        String callId = WsRequestUtils.firstQueryValue(request, "callId");
        if (callId == null || callId.isBlank() || !hasValidKey(request)) {
            response.setStatusCode(HttpStatus.FORBIDDEN);
            return false;
        }
        attributes.put(WsRequestUtils.ATTR_CALL_ID, callId);
        return true;
    }

    @Override
    public void afterHandshake(ServerHttpRequest request, ServerHttpResponse response,
                                WebSocketHandler wsHandler, Exception exception) {
        // 핸드셰이크 이후에 할 일 없음.
    }

    private boolean hasValidKey(ServerHttpRequest request) {
        String header = request.getHeaders().getFirst("Authorization");
        if (header == null || !header.startsWith("Bearer ")) {
            return false;
        }
        return header.substring(7).equals(externalApiKey);
    }
}
