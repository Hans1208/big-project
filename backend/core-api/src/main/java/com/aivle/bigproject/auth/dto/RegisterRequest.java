package com.aivle.bigproject.auth.dto;

import com.aivle.bigproject.user.UserRole;

// privacyAgreed는 개인정보 수집·이용 동의 여부다(개인정보 보호법 제15조 제2항).
// 화면에서 이미 동의 없이는 가입 버튼이 눌리지 않지만, /api/auth/register를 직접 부르면
// 그 검사를 지나칠 수 있어 서버에서도 확인한다.
public record RegisterRequest(String name, UserRole role, String email, String password,
                              Boolean privacyAgreed) {
}
