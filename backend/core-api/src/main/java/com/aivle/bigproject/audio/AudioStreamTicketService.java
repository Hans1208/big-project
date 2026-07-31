package com.aivle.bigproject.audio;

import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;

// 오디오 WebSocket 연결용 1회성 티켓을 발급/검증한다.
//
// 왜 토큰을 그대로 안 쓰는가:
// 브라우저의 new WebSocket(url)에는 헤더를 넣을 수 없다. 그래서 핸드셰이크에 JWT를 실으려면
// 주소에 붙이는 수밖에 없는데, 주소는 접속 로그·브라우저 히스토리·Referer에 남는다.
// JWT는 24시간짜리라 한 번 새면 그동안 계정 전체가 열린다.
//
// 대신 이 티켓을 쓴다. 로그인된 사용자가 REST로 받아가고(POST /api/audio/tickets),
// 30초 안에 한 번만 쓸 수 있다. 주소에 남더라도 이미 만료됐거나 소모된 값이다.
//
// 저장은 메모리다. AudioSessionRegistry와 같은 이유로 지금은 서버가 한 대뿐이라 충분하고,
// 티켓 수명이 30초라 서버를 재시작해도 잃을 게 없다. 여러 대로 늘리면 공유 저장소가 필요하다.
@Component
public class AudioStreamTicketService {

    // 소켓을 여는 데 걸리는 시간만 버티면 된다. 길게 잡을수록 주소에 남은 값이 살아 있는 시간도 길어진다.
    static final Duration TICKET_TTL = Duration.ofSeconds(30);

    private final SecureRandom random = new SecureRandom();
    private final Base64.Encoder encoder = Base64.getUrlEncoder().withoutPadding();
    private final Map<String, Issued> tickets = new ConcurrentHashMap<>();

    public record Issued(String email, String role, Instant expiresAt) {
        boolean isExpired(Instant now) {
            return now.isAfter(expiresAt);
        }
    }

    public record Ticket(String ticket, Instant expiresAt) {
    }

    public Ticket issue(String email, String role) {
        purgeExpired();
        byte[] raw = new byte[32];
        random.nextBytes(raw);
        String value = encoder.encodeToString(raw);
        Instant expiresAt = Instant.now().plus(TICKET_TTL);
        tickets.put(value, new Issued(email, role, expiresAt));
        return new Ticket(value, expiresAt);
    }

    // 검증과 동시에 소모한다. 같은 티켓으로 두 번 붙을 수 없어야, 주소에 남은 값을 주워도 못 쓴다.
    public Optional<Issued> consume(String ticket) {
        if (ticket == null || ticket.isBlank()) {
            return Optional.empty();
        }
        Issued issued = tickets.remove(ticket);
        if (issued == null || issued.isExpired(Instant.now())) {
            return Optional.empty();
        }
        return Optional.of(issued);
    }

    // 쓰이지 않은 티켓은 아무도 remove하지 않아 그대로 쌓인다. 발급할 때마다 만료분을 걷어낸다.
    private void purgeExpired() {
        Instant now = Instant.now();
        tickets.entrySet().removeIf(entry -> entry.getValue().isExpired(now));
    }
}
