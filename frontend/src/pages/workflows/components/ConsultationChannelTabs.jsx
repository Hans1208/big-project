import React, { useState } from 'react';
import { RealtimeAnalysisPanel } from '../analysis/RealtimeAnalysisPanel.jsx';
import { InPersonAnalysisPanel } from '../analysis/InPersonAnalysisPanel.jsx';

// RealtimeAnalysisPanel(전화상담)과 InPersonAnalysisPanel(대면상담) 사이를 전환하는 채널 탭.
// 탭 전환 시 진행 중이던 통화/녹음 상태를 자동으로 종료시키는 정책은 이번 범위에 넣지 않습니다.
export function ConsultationChannelTabs(props) {
  const [channel, setChannel] = useState('phone'); // 'phone' | 'inperson'
  return (
    <>
      <div className="categoryTabs">
        <button
          type="button"
          className={channel === 'phone' ? 'categoryTab active' : 'categoryTab'}
          onClick={() => setChannel('phone')}
        >
          전화상담
        </button>
        <button
          type="button"
          className={channel === 'inperson' ? 'categoryTab active' : 'categoryTab'}
          onClick={() => setChannel('inperson')}
        >
          대면상담
        </button>
      </div>
      {channel === 'phone' ? <RealtimeAnalysisPanel {...props} /> : <InPersonAnalysisPanel {...props} />}
    </>
  );
}
