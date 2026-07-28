package com.aivle.bigproject.config;

import java.net.http.HttpClient;
import java.time.Duration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.http.converter.json.JacksonJsonHttpMessageConverter;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.json.JsonMapper;

// core-api가 ai-api(FastAPI)를 서버 간(backend-to-backend)으로 호출할 때 쓰는 RestClient 빈.
// webflux(WebClient) 의존성을 새로 추가하지 않기 위해, 서블릿 스택에서도 쓸 수 있는
// 동기식 RestClient(spring-boot-starter-webmvc에 이미 포함됨)를 사용.
@Configuration
public class AiApiClientConfig {

    // RestClient.builder()의 기본 컨버터 목록엔 이 프로젝트가 쓰는 Jackson 3(tools.jackson) JSON
    // 컨버터가 자동으로 들어오지 않아서(이 프로젝트엔 RestClientAutoConfiguration이 없음), 앱이 이미
    // 쓰고 있는 ObjectMapper(AiAnalysisService 등과 동일한 빈)로 JacksonJsonHttpMessageConverter를
    // 직접 만들어 등록함. 이게 없으면 요청 body가 빈 값으로 나가서 ai-api가 422를 돌려줌.
    @Bean
    public RestClient aiApiRestClient(JsonMapper jsonMapper,
                                       @Value("${app.ai-api.base-url}") String baseUrl) {
        // HTTP/1.1로 고정 — 기본값(HTTP_2)이면 JDK HttpClient가 평문 연결에도 "Upgrade: h2c" 협상
        // 헤더를 얹어 보내는데, ai-api(uvicorn)가 이를 처리하지 못해 body를 못 읽고 422를 돌려줌.
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(10))
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        // /consult/analyze는 STT + 여러 LLM 호출이 서버에서 순차로 도는 파이프라인이라 오래 걸릴 수 있음
        requestFactory.setReadTimeout(Duration.ofMinutes(3));

        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .messageConverters(converters -> converters.add(0, new JacksonJsonHttpMessageConverter(jsonMapper)))
                .build();
    }
}
