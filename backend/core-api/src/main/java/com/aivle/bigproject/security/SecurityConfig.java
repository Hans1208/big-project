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
                        // 오디오 스트림 소켓만 여기서 통과시킨다. 인증을 푸는 게 아니라
                        // 검사 위치를 옮기는 것이다 — 실제 확인은 핸드셰이크에서 한다
                        // (AudioStreamHandshakeInterceptor, 티켓 없으면 403으로 끊는다).
                        //
                        // 여기서 막을 수 없는 이유: 브라우저의 new WebSocket(url)에는 헤더를
                        // 넣을 수 없다. 이 필터 체인은 Authorization 헤더를 보고 판단하므로
                        // 그대로 두면 브라우저는 붙을 방법이 아예 없다(토큰이 있어도 403).
                        // 주소에 JWT를 실으면 통과는 하지만 접속 로그·브라우저 히스토리에
                        // 24시간짜리 토큰이 남는다. 그래서 30초 1회용 티켓을 대신 싣는다.
                        //
                        // /api/audio/** (티켓 발급, 세션 목록)는 평범한 REST라 아래 규칙대로
                        // 인증이 그대로 걸린다.
                        .requestMatchers("/ws/audio/**").permitAll()
                        // 오류 응답 자리. 여기가 막혀 있으면 모든 오류가 403 빈 응답으로 바뀐다.
                        //
                        // 컨트롤러에서 처리되지 않은 오류(잘못된 JSON, 없는 경로 등)는 서블릿이
                        // /error로 다시 넘겨서 응답을 만든다. 그런데 이 재요청에는 JwtAuthenticationFilter가
                        // 다시 돌지 않고(OncePerRequestFilter), 세션도 쓰지 않으므로(STATELESS)
                        // 인증 정보가 없는 상태로 평가돼 여기서 403으로 끊겼다.
                        // 그래서 실제로는 400(본문 오류)이나 404(없는 경로)인데 클라이언트는
                        // 본문 없는 403만 받았다 — 프론트는 사용자에게 무엇이 잘못됐는지 알릴 수 없고,
                        // 개발 중에도 권한 문제로 오인해 원인을 찾는 데 오래 걸린다.
                        //
                        // 열어도 새로 드러나는 정보는 없다. /error는 직전 요청의 오류를 그대로
                        // 보여주는 자리이고, 스택트레이스·예외 메시지는 스프링 기본값에서 응답에
                        // 포함되지 않는다(server.error.include-* 를 켜지 않는 한).
                        .requestMatchers("/error").permitAll()
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
