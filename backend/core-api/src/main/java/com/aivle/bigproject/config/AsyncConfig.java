package com.aivle.bigproject.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.task.AsyncTaskExecutor;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.security.task.DelegatingSecurityContextAsyncTaskExecutor;

// AI 분석을 백그라운드에서 돌리기 위한 스레드풀(AnalysisJobRunner가 사용).
@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean("analysisJobExecutor")
    public AsyncTaskExecutor analysisJobExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        // 분석 한 건은 ai-api에서 STT + LLM 여러 번을 순서대로 돌리는 무거운 작업이라,
        // 동시에 많이 돌린다고 빨라지지 않는다(오히려 ai-api 쪽이 먼저 밀린다).
        // 적게 잡아 두고, 나머지는 큐에서 순서를 기다리게 한다.
        executor.setCorePoolSize(2);
        executor.setMaxPoolSize(4);
        executor.setQueueCapacity(50);
        executor.setThreadNamePrefix("analysis-job-");
        // 서버를 내릴 때 돌던 분석은 끝까지 기다려 준다. 중간에 끊으면 그 작업은 DB에
        // "분석 중"인 채로 남아, 다시 켰을 때 아무도 집어가지 않는 유령 작업이 된다.
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(60);
        executor.initialize();

        // 로그인 정보(SecurityContext)는 스레드마다 따로 보관된다. 그대로 넘기면 백그라운드
        // 스레드에서는 비어 있어서, 감사 로그(AuditLogService)에 "누가 분석을 돌렸는지"가
        // 남지 않는다. 이 래퍼가 요청 스레드의 로그인 정보를 복사해 넘겨준다.
        return new DelegatingSecurityContextAsyncTaskExecutor(executor);
    }
}
