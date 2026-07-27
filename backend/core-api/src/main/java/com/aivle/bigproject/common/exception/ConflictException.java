package com.aivle.bigproject.common.exception;

// "이미 존재함" 상황(예: 이메일 중복 가입)을 표현하는 공통 예외.
// GlobalExceptionHandler가 이걸 409로 변환한다.
public class ConflictException extends RuntimeException {
    public ConflictException(String message) {
        super(message);
    }
}
