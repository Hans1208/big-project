package com.aivle.bigproject.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;

    public SecurityConfig(JwtAuthenticationFilter jwtAuthenticationFilter) {
        this.jwtAuthenticationFilter = jwtAuthenticationFilter;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                // JWT만 쓰는 무상태 REST API라 세션/CSRF 토큰이 필요 없음
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/api/auth/**").permitAll()
                        // 가입 승인/거절/대기목록은 관리자 권한 로직의 핵심이라 실제로 막아둔다.
                        // 토큰 없이 호출하면 인증 자체가 안 잡혀 401, LAWYER/CONSULTANT 토큰으로
                        // 호출하면 권한 부족으로 403이 난다.
                        .requestMatchers(HttpMethod.GET, "/api/users/pending").hasRole("ADMIN")
                        .requestMatchers(HttpMethod.POST, "/api/users/*/approve").hasRole("ADMIN")
                        .requestMatchers(HttpMethod.POST, "/api/users/*/reject").hasRole("ADMIN")
                        // 관리자 대시보드 통계도 관리자 전용.
                        .requestMatchers(HttpMethod.GET, "/api/admin/stats").hasRole("ADMIN")
                        // 감사 로그 조회/검증도 관리자 전용.
                        .requestMatchers(HttpMethod.GET, "/api/admin/audit-logs/**").hasRole("ADMIN")
                        // 서식 초안 승인/반려는 변호사 권한 로직의 핵심이라 실제로 막아둔다.
                        .requestMatchers(HttpMethod.POST, "/api/consultations/*/documents/*/approve").hasRole("LAWYER")
                        .requestMatchers(HttpMethod.POST, "/api/consultations/*/documents/*/request-revision").hasRole("LAWYER")
                        // AI 분석 결과 승인/반려도 마찬가지로 변호사 전용.
                        .requestMatchers(HttpMethod.POST, "/api/consultations/*/analyses/*/approve").hasRole("LAWYER")
                        .requestMatchers(HttpMethod.POST, "/api/consultations/*/analyses/*/request-revision").hasRole("LAWYER")
                        // S3를 직접 다루는 개발용 엔드포인트. key만 바꾸면 버킷의 아무 오브젝트나
                        // 읽고 지울 수 있어서, 인증 여부와 별개로 외부에 열려 있으면 안 된다.
                        // 운영에 나가기 전에 이 컨트롤러 자체를 지우는 게 맞다.
                        .requestMatchers("/test/**").denyAll()
                        // 위에서 역할을 지정하지 않은 나머지(상담 CRUD·분석·첨부·서식 등)는
                        // 로그인한 사용자만 쓸 수 있다.
                        //
                        // 예전에는 여기가 permitAll이라 토큰 없이도 GET /api/consultations로
                        // 상담 전체가 그대로 조회됐고, PUT/DELETE도 통과했다. 화면에서 역할별로
                        // 메뉴를 나눠도 서버가 요청의 출처를 구분하지 못하므로 아무 의미가 없었다.
                        //
                        // 프론트가 모든 요청에 토큰을 싣기 시작해서(coreApiClientV2 requestCoreJson)
                        // 이제 좁힐 수 있다. 역할별 구분이 더 필요한 곳은 위쪽에 개별 규칙을 추가하면 된다.
                        .anyRequest().authenticated()
                )
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }
}
