package com.aivle.bigproject.document;

import java.util.Map;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;

// ai-api(FastAPI, app/routers/forms.py)의 서식 추천/초안생성 엔드포인트를 호출하는 얇은 클라이언트.
// 응답 형태가 아직 유동적(ai-api draft()가 계속 필드를 추가/변경해왔음)이라 고정 DTO 대신
// JsonNode로 그대로 받고, 필요한 필드만 Service에서 뽑아 쓴다.
//
// AiApiClientConfig의 공유 RestClient 빈을 쓴다. 예전에는 여기서 클라이언트를 따로 만들었는데,
// 그쪽에는 타임아웃 설정이 없어서 ai-api가 응답하지 않으면 호출한 스레드가 무한정 붙잡혔다.
// 서식 추천과 초안 생성은 둘 다 LLM을 거치는 느린 경로라, 그런 요청이 쌓이면 톰캣 스레드가
// 모두 묶여 로그인·상담 조회 같은 무관한 기능까지 함께 멈춘다.
//
// 두 클라이언트는 같은 uvicorn 문제를 각자 다르게 우회하고 있었다. 여기는
// SimpleClientHttpRequestFactory(HttpURLConnection)로, 공유 빈은 JDK HttpClient를 HTTP/1.1로
// 고정해서 풀었다. 공유 빈 쪽이 이미 /consult/analyze의 POST 본문 전송에 쓰이며 문제없이
// 동작하므로, 우회 방법을 하나로 합치고 타임아웃·Jackson 설정도 함께 물려받는다.
@Component
public class AiApiClient {

    private final RestClient restClient;

    public AiApiClient(RestClient aiApiRestClient) {
        this.restClient = aiApiRestClient;
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

    // applicantName/opponentName은 상담원이 화면에서 확인하고 고친 이름이다.
    // ai-api는 이 값을 주면 이름칸을 직접 채우고, 없으면 요약문에서 뽑아낸 이름을 쓴다.
    // 사람이 고친 값이 있는데도 안 보내면 상담원이 고친 이름이 초안에 반영되지 않는다.
    //
    // Map.of는 null을 넣으면 NPE가 나므로 빈 문자열로 바꿔 보낸다. 이름을 아직
    // 안 적은 상담이 흔해서(통화 중 접수) null이 실제로 자주 들어온다.
    public JsonNode generateDraft(String formName, JsonNode extractedJson, String summary,
                                  String applicantName, String opponentName) {
        return restClient.post()
                .uri("/forms/draft")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of(
                        "form_name", formName,
                        "extracted", extractedJson,
                        "summary", summary,
                        "applicant_name", applicantName == null ? "" : applicantName,
                        "opponent_name", opponentName == null ? "" : opponentName
                ))
                .retrieve()
                .body(JsonNode.class);
    }
}
