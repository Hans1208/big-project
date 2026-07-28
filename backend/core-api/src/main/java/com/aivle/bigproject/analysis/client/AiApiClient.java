package com.aivle.bigproject.analysis.client;

import com.aivle.bigproject.common.exception.AiApiException;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

// ai-api(FastAPI)의 POST /consult/analyze 하나만 호출하는 좁은 책임의 클라이언트.
// 다른 ai-api 엔드포인트(/analysis, /case-analysis 등)는 이번 작업 범위 밖이라 여기서 다루지 않음.
@Component
public class AiApiClient {

    private final RestClient aiApiRestClient;

    public AiApiClient(RestClient aiApiRestClient) {
        this.aiApiRestClient = aiApiRestClient;
    }

    public ConsultAnalyzeApiResponse analyzeConsult(RawInputRequest request) {
        try {
            return aiApiRestClient.post()
                    .uri("/consult/analyze")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(ConsultAnalyzeApiResponse.class);
        } catch (RestClientException e) {
            throw new AiApiException("ai-api 분석 요청에 실패했습니다: " + e.getMessage(), e);
        }
    }
}
