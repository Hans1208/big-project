package com.aivle.bigproject.analysis.job;

// 분석 작업 하나의 진행 상태.
//
// 상담원이 "분석 시작"을 누르면 작업이 하나 만들어지고, 화면은 이 상태를 주기적으로 물어보며
// 기다린다. AnalysisReviewStatus(분석 결과의 검토 단계)와는 다른 축이다 — 이건 "AI가 다 돌았나",
// 저건 "사람이 검토했나".
public enum AnalysisJobStatus {

    // 접수만 된 상태. 아직 실행 스레드가 집어가지 않았다.
    PENDING,

    // ai-api 호출 중. 여기서 몇 분씩 머문다.
    RUNNING,

    // 끝났고 결과가 resultJson에 들어 있다.
    SUCCEEDED,

    // 실패했고 사유가 errorMessage에 들어 있다.
    FAILED
}
