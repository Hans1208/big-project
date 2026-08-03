package com.aivle.bigproject.auth;

import com.aivle.bigproject.auth.dto.AuthResponse;
import com.aivle.bigproject.auth.dto.ChangePasswordRequest;
import com.aivle.bigproject.auth.dto.LoginRequest;
import com.aivle.bigproject.auth.dto.RegisterRequest;
import com.aivle.bigproject.common.exception.UnauthorizedException;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
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

    // POST /api/auth/password — 로그인한 본인의 비밀번호 변경
    //
    // 대상 계정을 body로 받지 않고 토큰에서 꺼낸다. 이메일을 받으면 남의 계정 비밀번호를
    // 바꾸는 요청을 그대로 보낼 수 있다. SecurityConfig에서 /api/auth/**를 permitAll로
    // 열어두고 있어 이 경로만 인증을 요구하도록 따로 지정해뒀다.
    @PostMapping("/api/auth/password")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void changePassword(@RequestBody ChangePasswordRequest request, Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new UnauthorizedException("로그인이 필요합니다.");
        }
        authService.changePassword(authentication.getName(), request);
    }
}
