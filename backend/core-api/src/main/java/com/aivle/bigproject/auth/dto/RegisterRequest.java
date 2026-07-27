package com.aivle.bigproject.auth.dto;

import com.aivle.bigproject.user.UserRole;

public record RegisterRequest(String name, UserRole role, String email, String password) {
}
