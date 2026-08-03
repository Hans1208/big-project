package com.aivle.bigproject.auth;

import com.aivle.bigproject.auth.dto.AuthResponse;
import com.aivle.bigproject.auth.dto.ChangePasswordRequest;
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
import java.time.LocalDateTime;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(readOnly = true)
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final LoginAttemptTracker loginAttemptTracker;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtService jwtService,
                        LoginAttemptTracker loginAttemptTracker) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
        this.loginAttemptTracker = loginAttemptTracker;
    }

    @Transactional
    public AuthResponse register(RegisterRequest request) {
        validatePasswordRule(request.password(), request.email());
        // 개인정보 수집·이용에 동의해야 가입할 수 있다(개인정보 보호법 제15조 제2항).
        // 화면에서도 막고 있지만 이 엔드포인트를 직접 부르면 그 검사를 지나칠 수 있어 여기서도 본다.
        if (!Boolean.TRUE.equals(request.privacyAgreed())) {
            throw new BadRequestException("개인정보 수집·이용 동의가 필요합니다.");
        }
        userRepository.findByEmail(request.email()).ifPresent(existing -> {
            throw new ConflictException("이미 가입된 이메일입니다: " + request.email());
        });
        User user = new User(request.name(), request.role(), request.email());
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        // 동의한 사실을 시각과 함께 남긴다 — 분쟁이 생기면 이게 증빙이 된다.
        user.setPrivacyAgreedAt(LocalDateTime.now());
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
        // 비밀번호를 무제한으로 넣어볼 수 없게 실패 횟수를 세어 잠시 막는다(LoginAttemptTracker).
        // 비밀번호 검사보다 먼저 봐야 잠긴 동안의 시도가 아예 처리되지 않는다.
        long lockedSeconds = loginAttemptTracker.lockedSecondsRemaining(request.email());
        if (lockedSeconds > 0) {
            throw new ForbiddenException(
                    "로그인 시도가 너무 많습니다. %d분 %d초 후에 다시 시도해주세요."
                            .formatted(lockedSeconds / 60, lockedSeconds % 60));
        }

        // 없는 이메일도 실패로 세고 같은 메시지를 준다 — 응답이 다르면 어떤 이메일이
        // 가입돼 있는지 알아낼 수 있다.
        User user = userRepository.findByEmail(request.email()).orElse(null);
        if (user == null || user.getPasswordHash() == null || !matchesPassword(request.password(), user)) {
            loginAttemptTracker.recordFailure(request.email());
            throw new UnauthorizedException("이메일 또는 비밀번호가 올바르지 않습니다.");
        }

        // 승인 대기·거절은 비밀번호가 맞은 경우다. 본인이 맞으므로 실패로 세지 않는다 —
        // 승인만 기다리는 사람이 여러 번 눌렀다고 잠기면 안 된다.
        if (user.getApprovalStatus() == ApprovalStatus.PENDING) {
            throw new ForbiddenException("관리자 승인 대기 중인 계정입니다.");
        }
        if (user.getApprovalStatus() == ApprovalStatus.REJECTED) {
            throw new ForbiddenException("가입이 거절된 계정입니다.");
        }

        loginAttemptTracker.recordSuccess(request.email());
        return toAuthResponse(user);
    }

    // 로그인한 본인의 비밀번호를 바꾼다.
    //
    // 현재 비밀번호를 함께 받는 이유: 로그인한 화면을 잠깐 두고 자리를 비운 사이 남이
    // 비밀번호를 바꿔 계정을 가져가는 것을 막기 위함이다(보호조치 기준 제5조).
    //
    // 같은 비밀번호로 바꾸는 것도 막는다. 화면에는 "변경되었습니다"가 뜨는데 실제로는
    // 아무것도 안 바뀌면, 상담원은 바꾼 줄 알고 넘어간다 — 주기적 변경을 요구하는
    // 운영 규칙이 그 자리에서 무의미해진다.
    @Transactional
    public void changePassword(String email, ChangePasswordRequest request) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new UnauthorizedException("로그인이 필요합니다."));

        if (request.currentPassword() == null || !matchesPassword(request.currentPassword(), user)) {
            throw new UnauthorizedException("현재 비밀번호가 올바르지 않습니다.");
        }
        if (request.newPassword() != null && matchesPassword(request.newPassword(), user)) {
            throw new ConflictException("지금 쓰고 있는 비밀번호와 같습니다. 다른 비밀번호를 입력해주세요.");
        }
        validatePasswordRule(request.newPassword(), email);

        user.setPasswordHash(passwordEncoder.encode(request.newPassword()));
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
    //
    // TODO(규제): 배포 전 이 분기를 제거할 것.
    //   보호조치 기준 제6조는 비밀번호를 복호화되지 않도록 일방향 암호화해 저장하라고 한다.
    //   지우는 걸 잊어도 운영에서 안 켜지도록, 남겨야 한다면 프로파일 플래그로 감쌀 것:
    //     @Value("${app.auth.allow-plain-test-login:false}") private boolean allowPlainTestLogin;
    //   마스터 계정 비밀번호 test1234도 아래 validatePasswordRule 기준에 미달한다
    //   (가입 경로를 타지 않아 지금 로그인은 되지만, 테스트 계정 정리 시 함께 바꿔야 함).
    private boolean matchesPassword(String rawPassword, User user) {
        // 저장된 값이 BCrypt 해시면 도메인과 무관하게 해시로 비교한다.
        // 테스트 계정이 changePassword로 비밀번호를 바꾸면 그때부터는 해시가 저장되는데,
        // 도메인만 보고 평문 비교로 가면 방금 바꾼 비밀번호로도 로그인이 안 되어 계정이 잠긴다.
        if (isBcryptHash(user.getPasswordHash())) {
            return passwordEncoder.matches(rawPassword, user.getPasswordHash());
        }
        if (user.getEmail() != null && user.getEmail().endsWith("@test.test")) {
            return rawPassword.equals(user.getPasswordHash());
        }
        return passwordEncoder.matches(rawPassword, user.getPasswordHash());
    }

    private boolean isBcryptHash(String stored) {
        return stored != null
                && (stored.startsWith("$2a$") || stored.startsWith("$2b$") || stored.startsWith("$2y$"));
    }

    private AuthResponse toAuthResponse(User user) {
        return new AuthResponse(jwtService.generateToken(user), user.getId(), user.getName(),
                user.getRole(), user.getEmail());
    }
}
