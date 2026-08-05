import React from 'react';
import { AlertTriangle } from 'lucide-react';

// 실시간 상담과 상담 자료 올리기 화면이 같은 "사건 번호 · 상담받은 사람 · 상담 제목 · 작성 시간"
// 박스를 완전히 같은 모양으로 써서(코치 피드백), 두 화면 중 한 곳에서만 이름·제목을 고치고
// 끝내는 게 아니라 어느 화면에서 들어와도 같은 정보를 보고 고칠 수 있게 합니다.
export function ConsultationCaseMeta({ selectedCase, onUpdateConsultation }) {
  if (!selectedCase) return null;
  return (
    <div className="analysisCaseMeta">
      <span>사건 번호 <strong>{selectedCase.caseNo}</strong></span>
      <label className={`analysisCaseMetaEdit realtimeRequiredNameField${selectedCase.name ? '' : ' missing'}`}>
        <span>
          {!selectedCase.name ? <AlertTriangle size={13} strokeWidth={2.4} className="realtimeRequiredNameFieldIcon" aria-hidden="true" /> : null}
          <span className="realtimeRequiredNameFieldLabelText">상담받은 사람</span>
          {selectedCase.name
            ? (selectedCase.nameSource === 'ai' ? <em className="nameSourceAi">AI가 찾음 · 확인해주세요</em> : null)
            : (
              <>
                <em>필수 입력</em>
                <small className="analysisCaseMetaHint">이름은 서식 생성과 검토 요청에 쓰이니 입력해주세요</small>
              </>
            )}
        </span>
        <input
          value={selectedCase.name || ''}
          onChange={(event) => onUpdateConsultation(selectedCase.id, {
            name: event.target.value,
            nameSource: 'counselor',
          })}
          placeholder="이름 입력"
        />
        {selectedCase.name && selectedCase.nameSource === 'ai'
          ? <small>통화 내용에서 찾은 이름입니다. 잘못 들었을 수 있으니 맞는지 봐주세요.</small>
          : null}
      </label>
      <label className="analysisCaseMetaEdit">
        <span>상담 제목</span>
        <input
          value={selectedCase.title || ''}
          onChange={(event) => onUpdateConsultation(selectedCase.id, { title: event.target.value })}
          placeholder="상담 제목 입력"
        />
      </label>
      <span>작성 시간 <strong>{selectedCase.date || '-'}{selectedCase.registeredTime ? ` ${selectedCase.registeredTime}` : ''}</strong></span>
    </div>
  );
}
