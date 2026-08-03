package com.aivle.bigproject.analysis.job;

// "분석 작업이 접수됐다"는 신호. AnalysisJobRunner가 이걸 받아 백그라운드 실행을 시작한다.
//
// 서비스가 러너를 직접 부르지 않고 이벤트를 거치는 이유: 백그라운드 스레드는 작업 행을
// id로 다시 조회하는데, 접수 트랜잭션이 아직 커밋되기 전이면 그 행이 DB에 없어서 못 찾는다.
// 러너 쪽에서 커밋 이후에만 실행되도록 받기 때문에(@TransactionalEventListener) 그 경합이 없다.
// 접수가 롤백되면 이벤트도 전달되지 않아 유령 작업이 돌지 않는다.
public record AnalysisJobSubmittedEvent(Long jobId) {
}
