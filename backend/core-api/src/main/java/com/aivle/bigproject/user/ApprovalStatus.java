package com.aivle.bigproject.user;

// 가입 승인 상태. ADMIN 역할은 가입과 동시에 APPROVED로 시작하고,
// CONSULTANT/LAWYER는 PENDING으로 시작해 관리자 승인이 있어야 로그인할 수 있다.
public enum ApprovalStatus {
    PENDING,
    APPROVED,
    REJECTED
}
