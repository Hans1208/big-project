package com.aivle.bigproject.auth;

import com.aivle.bigproject.auth.dto.AuthResponse;
import com.aivle.bigproject.auth.dto.LoginRequest;
import com.aivle.bigproject.auth.dto.RegisterRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    // POST /api/auth/register — 회원가입(이름/역할/이메일/비밀번호), 성공 시 바로 토큰 발급
    @PostMapping("/api/auth/register")
    @ResponseStatus(HttpStatus.CREATED)
    public AuthResponse register(@RequestBody RegisterRequest request) {
        return authService.register(request);
    }

    // POST /api/auth/login — 이메일/비밀번호로 로그인, 토큰 발급
    @PostMapping("/api/auth/login")
    public AuthResponse login(@RequestBody LoginRequest request) {
        return authService.login(request);
    }
}
