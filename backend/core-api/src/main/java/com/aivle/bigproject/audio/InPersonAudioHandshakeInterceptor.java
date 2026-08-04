package com.aivle.bigproject.audio;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.server.HandshakeInterceptor;

// 대면 상담 녹음(브라우저)이 /ws/audio/in-person에 붙으려는 핸드셰이크에서 티켓과 consultationId를
// 검사한다. AudioStreamHandshakeInterceptor(전화 상담의 /ws/audio/operator)와 인증 구조는
// 동일하다(1회성 티켓 — 브라우저 WebSocket에는 Authorization 헤더를 못 실으므로) — 다만 전화처럼
// 외부 SIP 통화 레그에 붙는 게 아니라 특정 상담(consultationId)의 녹음 세션을 여는 것이므로
// CallRegistry를 거치지 않는다.
@Component
public class InPersonAudioHandshakeInterceptor implements HandshakeInterceptor {

    public static final String ATTR_CONSULTATION_ID = "inPersonConsultationId";
    public static final String ATTR_EMAIL = "inPersonAudioUserEmail";

    private final AudioStreamTicketService ticketService;

    public InPersonAudioHandshakeInterceptor(AudioStreamTicketService ticketService) {
        this.ticketService = ticketService;
    }

    @Override
    public boolean beforeHandshake(ServerHttpRequest request, ServerHttpResponse response,
                                    WebSocketHandler wsHandler, Map<String, Object> attributes) {
        String consultationId = WsRequestUtils.firstQueryValue(request, "consultationId");
        String ticket = WsRequestUtils.firstQueryValue(request, "ticket");
        var issued = ticketService.consume(ticket);
        if (consultationId == null || consultationId.isBlank() || issued.isEmpty()) {
            response.setStatusCode(HttpStatus.FORBIDDEN);
            return false;
        }
        attributes.put(ATTR_CONSULTATION_ID, consultationId);
        attributes.put(ATTR_EMAIL, issued.get().email());
        return true;
    }

    @Override
    public void afterHandshake(ServerHttpRequest request, ServerHttpResponse response,
                                WebSocketHandler wsHandler, Exception exception) {
        // 핸드셰이크 이후에 할 일 없음.
    }
}
