package com.aivle.bigproject.document;

import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;

// ai-api(FastAPI, app/routers/forms.py)의 서식 추천/초안생성 엔드포인트를 호출하는 얇은 클라이언트.
// 응답 형태가 아직 유동적(ai-api draft()가 계속 필드를 추가/변경해왔음)이라 고정 DTO 대신
// JsonNode로 그대로 받고, 필요한 필드만 Service에서 뽑아 쓴다.
//
// RestClient가 기본으로 고르는 JDK java.net.http.HttpClient는 POST에 "Expect: 100-continue"를
// 붙이는데, uvicorn(ai-api)이 이를 제대로 처리 못 해서 본문이 아예 전달 안 되고 연결이
//끊기는 문제가 있었다(ai-api 쪽엔 "body 필드 없음"으로만 찍혀서 원인 파악이 오래 걸림).
// HttpURLConnection 기반의 SimpleClientHttpRequestFactory로 명시해서 우회한다.
@Component
public class AiApiClient {

    private final RestClient restClient;

    public AiApiClient(@Value("${app.ai-api.base-url}") String baseUrl) {
        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(new SimpleClientHttpRequestFactory())
                .build();
    }

    public JsonNode recommendForms(String caseType, String caseSubtype, String summary, JsonNode extractedJson) {
        return restClient.post()
                .uri("/forms/recommend")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of(
                        "case_type", caseType,
                        "case_subtype", caseSubtype,
                        "summary", summary,
                        "extracted_json", extractedJson
                ))
                .retrieve()
                .body(JsonNode.class);
    }

    public JsonNode generateDraft(String formName, JsonNode extractedJson, String summary) {
        return restClient.post()
                .uri("/forms/draft")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of(
                        "form_name", formName,
                        "extracted", extractedJson,
                        "summary", summary
                ))
                .retrieve()
                .body(JsonNode.class);
    }
}
