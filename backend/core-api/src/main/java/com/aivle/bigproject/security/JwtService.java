package com.aivle.bigproject.security;

import com.aivle.bigproject.user.User;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.util.Date;
import java.util.Optional;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

// JWT 발급/검증을 담당. 토큰 payload에는 email(subject) + userId + role만 담는다
// (그 이상은 필요할 때 /api/users/{id}로 다시 조회하면 됨 — 토큰을 가볍게 유지).
@Component
public class JwtService {

    private final Key key;
    private final long expirationMs;

    public JwtService(@Value("${app.jwt.secret}") String secret,
                       @Value("${app.jwt.expiration-ms:86400000}") long expirationMs) {
        // HS256은 최소 256비트(32바이트) 키가 필요 — 운영 배포 시 반드시 JWT_SECRET 환경변수로 교체해야 함
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expirationMs = expirationMs;
    }

    public String generateToken(User user) {
        Date now = new Date();
        Date expiry = new Date(now.getTime() + expirationMs);
        return Jwts.builder()
                .subject(user.getEmail())
                .claim("userId", user.getId())
                .claim("role", user.getRole().name())
                .claim("name", user.getName())
                .issuedAt(now)
                .expiration(expiry)
                .signWith(key)
                .compact();
    }

    // 검증 실패(만료·위변조 등) 시 빈 Optional — 호출부가 401로 처리
    public Optional<Claims> parseClaims(String token) {
        try {
            return Optional.of(Jwts.parser().verifyWith((javax.crypto.SecretKey) key).build()
                    .parseSignedClaims(token).getPayload());
        } catch (JwtException | IllegalArgumentException e) {
            return Optional.empty();
        }
    }
}
