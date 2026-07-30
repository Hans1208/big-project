package com.aivle.bigproject.auth;

import com.aivle.bigproject.auth.dto.AuthResponse;
import com.aivle.bigproject.auth.dto.LoginRequest;
import com.aivle.bigproject.auth.dto.RegisterRequest;
import com.aivle.bigproject.common.exception.BadRequestException;
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
        validatePasswordRule(request.password(), request.email());
        userRepository.findByEmail(request.email()).ifPresent(existing -> {
            throw new ConflictException("이미 가입된 이메일입니다: " + request.email());
        });
        User user = new User(request.name(), request.role(), request.email());
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        // ADMIN은 가입 즉시 사용 가능, CONSULTANT/LAWYER는 관리자 승인 전까지 로그인 불가(login() 참고)
        user.setApprovalStatus(request.role() == UserRole.ADMIN ? ApprovalStatus.APPROVED : ApprovalStatus.PENDING);
        User saved = userRepository.save(user);
        // PENDING 상태에서 토큰을 바로 내주면 login()의 승인 대기 차단을 그대로 우회할 수 있다
        // (JwtAuthenticationFilter는 토큰만 보고 요청마다 승인 상태를 다시 확인하지 않음) —
        // 승인되기 전까지는 token을 null로 돌려주고, 승인 후 /login으로만 토큰을 받게 한다.
        if (saved.getApprovalStatus() != ApprovalStatus.APPROVED) {
            return new AuthResponse(null, saved.getId(), saved.getName(), saved.getRole(), saved.getEmail());
        }
        return toAuthResponse(saved);
    }

    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.email())
                .orElseThrow(() -> new UnauthorizedException("이메일 또는 비밀번호가 올바르지 않습니다."));
        if (user.getPasswordHash() == null || !matchesPassword(request.password(), user)) {
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

    // ── 비밀번호 작성규칙 ──
    //
    // "개인정보의 기술적·관리적 보호조치 기준" 제4조 ⑧항:
    //   1. 영문·숫자·특수문자 중 2종류 이상 조합 시 최소 10자리 이상,
    //      3종류 이상 조합 시 최소 8자리 이상
    //   2. 아이디와 비슷한 비밀번호는 사용하지 않을 것
    //
    // 회원가입 화면(auth.jsx validatePassword)에서도 같은 규칙을 안내하지만, 화면 검사만으로는
    // /api/auth/register를 직접 부르면 그냥 통과한다. 실제 차단은 여기가 담당한다.
    //
    // MasterAccountInitializer가 만드는 테스트 계정은 이 경로를 타지 않아 영향받지 않는다.
    private static final int MIN_LENGTH_TWO_KINDS = 10;
    private static final int MIN_LENGTH_THREE_KINDS = 8;

    private void validatePasswordRule(String password, String email) {
        if (password == null || password.isBlank()) {
            throw new BadRequestException("비밀번호를 입력해주세요.");
        }
        int kindCount = 0;
        if (password.matches(".*[A-Za-z].*")) kindCount++;
        if (password.matches(".*[0-9].*")) kindCount++;
        if (password.matches(".*[^A-Za-z0-9].*")) kindCount++;

        boolean longEnough = (kindCount >= 3 && password.length() >= MIN_LENGTH_THREE_KINDS)
                || (kindCount >= 2 && password.length() >= MIN_LENGTH_TWO_KINDS);
        if (!longEnough) {
            throw new BadRequestException(
                    "비밀번호는 영문·숫자·특수문자 중 2종류 이상 10자리, 또는 3종류를 모두 섞어 8자리 이상이어야 합니다.");
        }

        // 이메일 앞부분(아이디)을 그대로 넣은 비밀번호는 추측이 쉬워 규칙 2항에서 막는다.
        String localPart = email == null ? "" : email.split("@")[0].trim();
        if (localPart.length() >= 3 && password.toLowerCase().contains(localPart.toLowerCase())) {
            throw new BadRequestException("이메일 아이디가 그대로 들어간 비밀번호는 사용할 수 없습니다.");
        }
    }

    // MasterAccountInitializer가 만드는 @test.test 마스터 계정은 평문 비밀번호로 저장되므로
    // BCrypt matches() 대신 단순 문자열 비교로 분기한다 (이메일 도메인만으로 테스트 계정 식별).
    private boolean matchesPassword(String rawPassword, User user) {
        if (user.getEmail() != null && user.getEmail().endsWith("@test.test")) {
            return rawPassword.equals(user.getPasswordHash());
        }
        return passwordEncoder.matches(rawPassword, user.getPasswordHash());
    }

    private AuthResponse toAuthResponse(User user) {
        return new AuthResponse(jwtService.generateToken(user), user.getId(), user.getName(),
                user.getRole(), user.getEmail());
    }
}
