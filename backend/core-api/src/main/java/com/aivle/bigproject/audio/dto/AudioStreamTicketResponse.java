package com.aivle.bigproject.audio.dto;

import java.time.Instant;

// POST /api/audio/tickets 응답. 프론트는 이 ticket을 소켓 주소에 붙여 연결한다.
public record AudioStreamTicketResponse(String ticket, Instant expiresAt) {
}
