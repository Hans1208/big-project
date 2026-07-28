package com.aivle.bigproject.auth.dto;

import com.aivle.bigproject.user.UserRole;

public record AuthResponse(String token, Long userId, String name, UserRole role, String email) {
}
