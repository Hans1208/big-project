package com.aivle.bigproject.audio.dto;

import java.time.Instant;

public record AudioSessionResponse(
        String sessionId,
        String remoteAddress,
        Instant connectedAt
) {
}
