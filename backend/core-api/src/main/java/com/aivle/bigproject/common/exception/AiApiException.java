package com.aivle.bigproject.common.exception;

// ai-api(FastAPI) 호출이 실패했을 때(연결 불가, 5xx 등) 던지는 예외.
// GlobalExceptionHandler가 이걸 502로 변환함 — core-api 자체 문제가 아니라
// 의존하는 외부 서비스 문제라는 걸 클라이언트가 구분할 수 있도록.
public class AiApiException extends RuntimeException {
    public AiApiException(String message, Throwable cause) {
        super(message, cause);
    }
}
