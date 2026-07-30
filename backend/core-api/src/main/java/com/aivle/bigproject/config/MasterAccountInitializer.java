package com.aivle.bigproject.config;

import com.aivle.bigproject.user.ApprovalStatus;
import com.aivle.bigproject.user.User;
import com.aivle.bigproject.user.UserRepository;
import com.aivle.bigproject.user.UserRole;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

// 회원가입 없이도 역할별(상담원/변호사/관리자) 마스터 계정으로 실제 로그인 플로우(/api/auth/login)를
// 그대로 태워볼 수 있도록, 앱 기동 시 계정이 없으면 생성한다. findByEmail로 매번 존재 여부를 확인하고
// 없을 때만 만들기 때문에 idempotent하고, DB를 리셋해도 다음 기동 시 자동 복구된다.
// 비밀번호는 BCrypt로 인코딩하지 않고 평문 그대로 저장한다 — AuthService.login()이 이메일 도메인이
// @test.test인 계정은 평문 비교로 분기해서 처리한다.
@Component
public class MasterAccountInitializer implements CommandLineRunner {

    private final UserRepository userRepository;

    private final String talkerEmail;
    private final String talkerPassword;
    private final String talkerName;
    private final String lawyerEmail;
    private final String lawyerPassword;
    private final String lawyerName;
    private final String adminEmail;
    private final String adminPassword;
    private final String adminName;

    public MasterAccountInitializer(
            UserRepository userRepository,
            @Value("${app.master-account.talker.email}") String talkerEmail,
            @Value("${app.master-account.talker.password}") String talkerPassword,
            @Value("${app.master-account.talker.name}") String talkerName,
            @Value("${app.master-account.lawyer.email}") String lawyerEmail,
            @Value("${app.master-account.lawyer.password}") String lawyerPassword,
            @Value("${app.master-account.lawyer.name}") String lawyerName,
            @Value("${app.master-account.admin.email}") String adminEmail,
            @Value("${app.master-account.admin.password}") String adminPassword,
            @Value("${app.master-account.admin.name}") String adminName) {
        this.userRepository = userRepository;
        this.talkerEmail = talkerEmail;
        this.talkerPassword = talkerPassword;
        this.talkerName = talkerName;
        this.lawyerEmail = lawyerEmail;
        this.lawyerPassword = lawyerPassword;
        this.lawyerName = lawyerName;
        this.adminEmail = adminEmail;
        this.adminPassword = adminPassword;
        this.adminName = adminName;
    }

    @Override
    @Transactional
    public void run(String... args) {
        createIfAbsent(talkerEmail, talkerPassword, talkerName, UserRole.CONSULTANT);
        createIfAbsent(lawyerEmail, lawyerPassword, lawyerName, UserRole.LAWYER);
        createIfAbsent(adminEmail, adminPassword, adminName, UserRole.ADMIN);
    }

    private void createIfAbsent(String email, String password, String name, UserRole role) {
        if (userRepository.findByEmail(email).isPresent()) {
            return;
        }
        User user = new User(name, role, email);
        user.setPasswordHash(password);
        user.setApprovalStatus(ApprovalStatus.APPROVED);
        userRepository.save(user);
    }
}
