package com.aivle.bigproject.auth;

import com.aivle.bigproject.auth.dto.AuthResponse;
import com.aivle.bigproject.auth.dto.LoginRequest;
import com.aivle.bigproject.auth.dto.RegisterRequest;
import com.aivle.bigproject.common.exception.ConflictException;
import com.aivle.bigproject.common.exception.ForbiddenException;
import com.aivle.bigproject.common.exception.UnauthorizedException;
import com.aivle.bigproject.security.JwtService;
import com.aivle.bigproject.user.ApprovalStatus;
import com.aivle.bigproject.user.User;
import com.aivle.bigproject.user.UserRepository;
import com.aivle.bigproject.user.UserRole;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(readOnly = true)
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtService jwtService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
    }

    @Transactional
    public AuthResponse register(RegisterRequest request) {
        userRepository.findByEmail(request.email()).ifPresent(existing -> {
            throw new ConflictException("이미 가입된 이메일입니다: " + request.email());
        });
        User user = new User(request.name(), request.role(), request.email());
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        // ADMIN은 가입 즉시 사용 가능, CONSULTANT/LAWYER는 관리자 승인 전까지 로그인 불가(login() 참고)
        user.setApprovalStatus(request.role() == UserRole.ADMIN ? ApprovalStatus.APPROVED : ApprovalStatus.PENDING);
        User saved = userRepository.save(user);
        return toAuthResponse(saved);
    }

    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.email())
                .orElseThrow(() -> new UnauthorizedException("이메일 또는 비밀번호가 올바르지 않습니다."));
        if (user.getPasswordHash() == null
                || !passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new UnauthorizedException("이메일 또는 비밀번호가 올바르지 않습니다.");
        }
        if (user.getApprovalStatus() == ApprovalStatus.PENDING) {
            throw new ForbiddenException("관리자 승인 대기 중인 계정입니다.");
        }
        if (user.getApprovalStatus() == ApprovalStatus.REJECTED) {
            throw new ForbiddenException("가입이 거절된 계정입니다.");
        }
        return toAuthResponse(user);
    }

    private AuthResponse toAuthResponse(User user) {
        return new AuthResponse(jwtService.generateToken(user), user.getId(), user.getName(),
                user.getRole(), user.getEmail());
    }
}
