package com.aivle.bigproject.auth.dto;

import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

// 본인 비밀번호 변경. 현재 비밀번호를 함께 받는다 —
// 로그인한 화면을 잠깐 두고 자리를 비운 사이 남이 바꿔버리는 것을 막기 위함.
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ChangePasswordRequest(String currentPassword, String newPassword) {
}
