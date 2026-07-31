package com.aivle.bigproject.audio;

import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServletServerHttpRequest;
import org.springframework.web.util.UriComponentsBuilder;

final class WsRequestUtils {

    // 핸드셰이크 attributes에 통화 ID를 저장할 때 쓰는 공용 키.
    // 오퍼레이터/외부 서버 두 인터셉터가 같은 키로 채워야 핸들러가 하나의 이름으로 읽을 수 있다.
    static final String ATTR_CALL_ID = "audioCallId";

    private WsRequestUtils() {
    }

    // ServletServerHttpRequest면 서블릿 파라미터를 그대로 쓰는 편이 안전하다(디코딩까지 끝나 있다).
    static String firstQueryValue(ServerHttpRequest request, String name) {
        if (request instanceof ServletServerHttpRequest servletRequest) {
            return servletRequest.getServletRequest().getParameter(name);
        }
        return UriComponentsBuilder.fromUri(request.getURI()).build()
                .getQueryParams().getFirst(name);
    }
}
