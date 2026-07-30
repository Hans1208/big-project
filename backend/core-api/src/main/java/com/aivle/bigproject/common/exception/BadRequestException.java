package com.aivle.bigproject.common.exception;

// 요청 값 자체가 규칙에 어긋난 상황(예: 비밀번호 작성규칙 미달)을 표현하는 공통 예외.
// GlobalExceptionHandler가 이걸 400으로 변환한다.
//
// @Valid 애노테이션(-> MethodArgumentNotValidException)으로 표현하기 어려운,
// 여러 조건이 얽힌 검증에 쓴다. 비밀번호 규칙이 그 예로, "문자 종류 수"와 "길이"가
// 서로 맞물려 있어(2종류면 10자리, 3종류면 8자리) 애노테이션 하나로는 못 적는다.
public class BadRequestException extends RuntimeException {
    public BadRequestException(String message) {
        super(message);
    }
}
