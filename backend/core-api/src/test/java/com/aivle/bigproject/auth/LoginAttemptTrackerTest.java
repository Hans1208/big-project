package com.aivle.bigproject.auth;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

// 로그인 실패 잠금 규칙 테스트. 스프링 컨텍스트도 DB도 쓰지 않는다.
class LoginAttemptTrackerTest {

    private static final String EMAIL = "someone@example.com";

    private LoginAttemptTracker tracker;

    @BeforeEach
    void setUp() {
        tracker = new LoginAttemptTracker();
    }

    private void fail(int times) {
        for (int i = 0; i < times; i++) {
            tracker.recordFailure(EMAIL);
        }
    }

    @Test
    @DisplayName("처음에는 잠겨 있지 않다")
    void notLockedInitially() {
        assertThat(tracker.lockedSecondsRemaining(EMAIL)).isZero();
    }

    @Test
    @DisplayName("한도 직전까지는 잠기지 않는다")
    void notLockedBeforeLimit() {
        fail(LoginAttemptTracker.MAX_FAILURES - 1);
        assertThat(tracker.lockedSecondsRemaining(EMAIL)).isZero();
    }

    @Test
    @DisplayName("한도에 닿으면 잠긴다")
    void locksAtLimit() {
        fail(LoginAttemptTracker.MAX_FAILURES);
        assertThat(tracker.lockedSecondsRemaining(EMAIL))
                .isGreaterThan(0)
                .isLessThanOrEqualTo(LoginAttemptTracker.LOCK_DURATION.toSeconds());
    }

    @Test
    @DisplayName("성공하면 잠금과 횟수가 풀린다")
    void successClears() {
        fail(LoginAttemptTracker.MAX_FAILURES);
        assertThat(tracker.lockedSecondsRemaining(EMAIL)).isGreaterThan(0);

        tracker.recordSuccess(EMAIL);
        assertThat(tracker.lockedSecondsRemaining(EMAIL)).isZero();

        // 횟수도 처음부터 다시 센다 — 잠금만 풀고 횟수가 남아 있으면 한 번 틀리자마자 또 잠긴다.
        fail(LoginAttemptTracker.MAX_FAILURES - 1);
        assertThat(tracker.lockedSecondsRemaining(EMAIL)).isZero();
    }

    @Test
    @DisplayName("다른 계정은 서로 영향을 주지 않는다")
    void independentPerAccount() {
        fail(LoginAttemptTracker.MAX_FAILURES);
        assertThat(tracker.lockedSecondsRemaining("other@example.com")).isZero();
    }

    @Test
    @DisplayName("대소문자를 바꿔도 같은 계정으로 센다")
    void caseInsensitive() {
        // 대소문자만 바꿔 시도하면 잠금을 우회할 수 있으면 안 된다.
        for (int i = 0; i < LoginAttemptTracker.MAX_FAILURES; i++) {
            tracker.recordFailure(i % 2 == 0 ? EMAIL : EMAIL.toUpperCase());
        }
        assertThat(tracker.lockedSecondsRemaining(EMAIL)).isGreaterThan(0);
        assertThat(tracker.lockedSecondsRemaining(EMAIL.toUpperCase())).isGreaterThan(0);
    }

    @Test
    @DisplayName("앞뒤 공백이 있어도 같은 계정으로 센다")
    void trimsWhitespace() {
        fail(LoginAttemptTracker.MAX_FAILURES);
        assertThat(tracker.lockedSecondsRemaining("  " + EMAIL + "  ")).isGreaterThan(0);
    }

    @Test
    @DisplayName("한도를 넘겨 더 틀려도 잠금이 무한정 늘지 않는다")
    void doesNotAccumulateBeyondLockDuration() {
        fail(LoginAttemptTracker.MAX_FAILURES + 20);
        assertThat(tracker.lockedSecondsRemaining(EMAIL))
                .isLessThanOrEqualTo(LoginAttemptTracker.LOCK_DURATION.toSeconds());
    }

    @Test
    @DisplayName("null이나 빈 이메일에도 터지지 않는다")
    void handlesNullEmail() {
        tracker.recordFailure(null);
        assertThat(tracker.lockedSecondsRemaining(null)).isZero();
        tracker.recordSuccess(null);
        assertThat(tracker.lockedSecondsRemaining("")).isZero();
    }
}
