package com.aivle.bigproject.common.exception;

// stt-mask-api(FastAPI, POST /transcribe) 호출이 실패했을 때(연결 불가, 5xx, 응답에 error 필드 등)
// 던지는 예외. AiApiException과 같은 이유로 별도 타입을 둔다 — core-api 자체 문제가 아니라
// 의존하는 외부 서비스 문제라는 걸 구분하기 위해서.
public class SttMaskApiException extends RuntimeException {
    public SttMaskApiException(String message, Throwable cause) {
        super(message, cause);
    }

    public SttMaskApiException(String message) {
        super(message);
    }
}
