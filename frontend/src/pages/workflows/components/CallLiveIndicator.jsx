import React from 'react';
import { formatCallDuration } from '../shared/formatters.js';

// 코치 피드백: "실시간 통화 버튼 누르면 시작되고, 종료 버튼 누르면 끝난 다음, 분석 시작을 누르면
// 바로 분석을 시작하는 방식". 실제 전화 연동(WebRTC 등)은 백엔드 작업이 필요해 아직 없지만,
// 상담원이 겪는 절차 자체(시작 → 통화 중 메모 → 종료 → 분석 시작)는 지금 화면에서 실제로 동작합니다.
// 통화 중 경과 시간을 보여주는 라이브 인디케이터. 버튼 라벨에 시간을 붙이면 버튼이 매초
// 넓이가 바뀌어 깜빡여 보이므로, 버튼과 분리해 깜빡이는 점 + 고정폭 숫자로만 보여줍니다.
export function CallLiveIndicator({ seconds }) {
  return (
    <span className="callLiveIndicator" role="status">
      <span className="callLiveDot" aria-hidden="true" />
      <span className="callLiveTime">{formatCallDuration(seconds)}</span>
    </span>
  );
}
