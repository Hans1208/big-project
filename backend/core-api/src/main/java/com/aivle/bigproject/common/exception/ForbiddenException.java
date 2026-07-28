package com.aivle.bigproject.common.exception;

// 인증(이메일/비밀번호)은 맞지만 접근 권한이 없는 상황(예: 승인 대기/거절된 계정의 로그인 시도).
// GlobalExceptionHandler가 이걸 403으로 변환한다.
public class ForbiddenException extends RuntimeException {
    public ForbiddenException(String message) {
        super(message);
    }
}
