package com.aivle.bigproject.audio;

import com.aivle.bigproject.audio.dto.AudioSessionResponse;
import com.aivle.bigproject.audio.dto.AudioStreamTicketResponse;
import java.util.List;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AudioSessionController {

    private final AudioSessionRegistry sessionRegistry;
    private final AudioStreamTicketService ticketService;

    public AudioSessionController(AudioSessionRegistry sessionRegistry,
                                   AudioStreamTicketService ticketService) {
        this.sessionRegistry = sessionRegistry;
        this.ticketService = ticketService;
    }

    // GET /api/audio/mulaw/sessions — 현재 연결된 μ-law 오디오 WebSocket 세션 목록
    @GetMapping("/api/audio/mulaw/sessions")
    public List<AudioSessionResponse> listSessions() {
        return sessionRegistry.list();
    }

    // POST /api/audio/tickets — 오디오 WebSocket에 붙을 때 쓸 1회성 티켓 발급.
    //
    // 이 요청 자체는 평범한 REST라 Authorization 헤더로 인증된다. 티켓이 필요한 이유는
    // 그다음 단계인 WebSocket 핸드셰이크 때문이다 — 브라우저의 new WebSocket()에는 헤더를
    // 넣을 수 없어서, 인증 정보를 주소에 실을 수밖에 없다. 24시간짜리 JWT를 주소에 그대로
    // 붙이면 접속 로그와 브라우저 히스토리에 남으므로, 30초 1회용 티켓으로 바꿔서 넘긴다.
    @PostMapping("/api/audio/tickets")
    public AudioStreamTicketResponse issueTicket(Authentication authentication) {
        String email = authentication.getName();
        String role = authentication.getAuthorities().stream()
                .map(authority -> authority.getAuthority().replaceFirst("^ROLE_", ""))
                .findFirst()
                .orElse(null);
        var ticket = ticketService.issue(email, role);
        return new AudioStreamTicketResponse(ticket.ticket(), ticket.expiresAt());
    }
}
