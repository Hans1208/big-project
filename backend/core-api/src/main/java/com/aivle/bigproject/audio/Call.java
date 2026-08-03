package com.aivle.bigproject.audio;

import java.time.Instant;
import org.springframework.web.socket.WebSocketSession;

// 통화 1건의 상태. 외부 서버 쪽 세션은 통화가 생성될 때 고정되고,
// 오퍼레이터(브라우저) 쪽 세션은 누가 언제 붙거나 빠지느냐에 따라 바뀐다.
class Call {

    private final String callId;
    private final WebSocketSession externalSession;
    private final Instant connectedAt;

    private volatile WebSocketSession operatorSession;
    private volatile String operatorEmail;

    Call(String callId, WebSocketSession externalSession) {
        this.callId = callId;
        this.externalSession = externalSession;
        this.connectedAt = Instant.now();
    }

    String callId() {
        return callId;
    }

    WebSocketSession externalSession() {
        return externalSession;
    }

    Instant connectedAt() {
        return connectedAt;
    }

    WebSocketSession operatorSession() {
        return operatorSession;
    }

    String operatorEmail() {
        return operatorEmail;
    }

    // 오퍼레이터가 없을 때만 붙는다 — 통화당 오퍼레이터 1명 원칙을 여기서 지킨다.
    synchronized boolean tryAttachOperator(WebSocketSession session, String email) {
        if (operatorSession != null) {
            return false;
        }
        operatorSession = session;
        operatorEmail = email;
        return true;
    }

    // 지금 붙어 있는 세션이 맞을 때만 뗀다 — 이미 새 오퍼레이터가 붙은 뒤에
    // 예전 세션의 종료 이벤트가 뒤늦게 와서 새 오퍼레이터를 떼어내는 걸 막는다.
    synchronized boolean detachOperator(WebSocketSession session) {
        if (operatorSession != session) {
            return false;
        }
        operatorSession = null;
        operatorEmail = null;
        return true;
    }
}
