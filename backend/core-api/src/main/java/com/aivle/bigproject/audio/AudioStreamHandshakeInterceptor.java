package com.aivle.bigproject.audio;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.server.HandshakeInterceptor;

// 오퍼레이터(브라우저)가 특정 통화에 붙으려는 오디오 WebSocket 핸드셰이크에서 티켓과 callId를 검사한다.
//
// SecurityConfig는 /ws/audio/**를 permitAll로 열어두고, 실제 인증은 여기서 한다.
// 브라우저가 핸드셰이크에 Authorization 헤더를 붙일 수 없어서 필터 체인으로는 막을 수가 없다
// (막으면 브라우저는 붙을 방법이 아예 없어진다). 대신 주소에 실은 1회성 티켓을 여기서 확인한다.
//
// 티켓이 없거나 만료·재사용이면 403으로 끊는다. beforeHandshake가 false를 돌려주면
// 소켓이 열리지 않으므로, 핸들러(OperatorWebSocketHandler)는 인증된 연결만 보게 된다.
// 실제로 이 통화에 오퍼레이터로 붙을 수 있는지(존재 여부·중복 여부)는 CallRegistry가 판단한다.
@Component
public class AudioStreamHandshakeInterceptor implements HandshakeInterceptor {

    // 연결된 세션이 누구 것인지 핸들러 쪽에서 알 수 있도록 남겨둔다.
    // 나중에 STT 결과를 상담에 붙이려면 어느 상담원의 통화인지가 필요하다.
    public static final String ATTR_EMAIL = "audioStreamUserEmail";
    public static final String ATTR_ROLE = "audioStreamUserRole";

    private final AudioStreamTicketService ticketService;

    public AudioStreamHandshakeInterceptor(AudioStreamTicketService ticketService) {
        this.ticketService = ticketService;
    }

    @Override
    public boolean beforeHandshake(ServerHttpRequest request, ServerHttpResponse response,
                                    WebSocketHandler wsHandler, Map<String, Object> attributes) {
        String callId = WsRequestUtils.firstQueryValue(request, "callId");
        String ticket = WsRequestUtils.firstQueryValue(request, "ticket");
        var issued = ticketService.consume(ticket);
        if (callId == null || callId.isBlank() || issued.isEmpty()) {
            response.setStatusCode(HttpStatus.FORBIDDEN);
            return false;
        }
        attributes.put(WsRequestUtils.ATTR_CALL_ID, callId);
        attributes.put(ATTR_EMAIL, issued.get().email());
        attributes.put(ATTR_ROLE, issued.get().role());
        return true;
    }

    @Override
    public void afterHandshake(ServerHttpRequest request, ServerHttpResponse response,
                                WebSocketHandler wsHandler, Exception exception) {
        // 핸드셰이크 이후에 할 일 없음.
    }
}
