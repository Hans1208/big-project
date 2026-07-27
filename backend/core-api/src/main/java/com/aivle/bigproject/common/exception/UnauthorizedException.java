package com.aivle.bigproject.common.exception;

// 로그인 실패(이메일 없음/비밀번호 불일치), 유효하지 않은 인증 상태를 표현하는 공통 예외.
// GlobalExceptionHandler가 이걸 401로 변환한다.
public class UnauthorizedException extends RuntimeException {
    public UnauthorizedException(String message) {
        super(message);
    }
}
