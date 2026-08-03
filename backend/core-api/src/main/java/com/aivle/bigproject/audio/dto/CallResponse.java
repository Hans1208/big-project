package com.aivle.bigproject.audio.dto;

import java.time.Instant;

public record CallResponse(
        String callId,
        String status,
        Instant connectedAt,
        String operatorEmail
) {
}
