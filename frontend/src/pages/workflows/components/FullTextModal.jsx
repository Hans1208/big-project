import React, { useEffect, useState } from 'react';
import { X, FileText } from 'lucide-react';
import { fetchPrecedentFullText, fetchStatuteFullText } from '../../../services/aiApiClient.js';
import { friendlyErrorMessage } from '../../../components/common.jsx';

// 검색 결과 카드에 실리는 본문은 색인이 쪼개 둔 '조각 하나'입니다.
//   · 조문은 800자씩 잘립니다 — 가사소송법 제2조가 797자에서, 그것도 항목 중간에서 끊겼습니다.
//   · 판례는 판시사항/판결요지/판례내용이 각각 따로 들어가고, 그것도 다시 쪼개집니다 —
//     2022느단5199는 chunk-0002만 걸려 본문이 "비율에 따라"라는 문장 중간부터 시작했습니다.
//
// 잘렸다는 표시가 어디에도 없어서, 끝까지 읽고 "이 조문엔 그런 내용 없다"고 결론내면
// 틀릴 수 있습니다. 변호사가 근거로 담을 자료라 이대로 두면 안 됩니다.
//
// 그래서 '전문 보기'는 카드 안에서 펼치지 않고, 서버에서 문서 전체를 다시 받아
// 이 창에 띄웁니다. 목록을 벗어나지 않으면서 원문을 끝까지 읽을 수 있습니다.
export function FullTextModal({ item, referenceType, onClose }) {
  const [status, setStatus] = useState('loading'); // loading | ready | error
  const [text, setText] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!item) return undefined;
    let cancelled = false;
    setStatus('loading');
    setText('');
    setMessage('');

    const request = referenceType === 'precedent'
      ? fetchPrecedentFullText({ id: item.id, precedentId: item.precedentId || '' })
      : fetchStatuteFullText(item.id);

    request
      .then((payload) => {
        if (cancelled) return;
        setText(payload?.content || '');
        setStatus('ready');
      })
      .catch((error) => {
        if (cancelled) return;
        setMessage(friendlyErrorMessage(error, '원문을 불러오지 못했습니다.'));
        setStatus('error');
      });

    return () => { cancelled = true; };
  }, [item, referenceType]);

  // 긴 원문을 읽다가 목록으로 돌아가는 가장 빠른 길입니다. 창이 화면을 덮고 있어
  // 바깥을 누를 곳을 찾기 어려울 때가 있습니다.
  useEffect(() => {
    const onKeyDown = (event) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  if (!item) return null;

  return (
    <div className="modalBackdrop" role="presentation" onClick={onClose}>
      <div
        className="modal fullTextModal"
        role="dialog"
        aria-modal="true"
        aria-label={`${item.title} 원문`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="fullTextModalHead">
          <div>
            <h2><FileText size={16} strokeWidth={2.2} aria-hidden="true" /> {item.title}</h2>
            <p>{item.source}{item.effectiveDate ? ` · ${item.effectiveDate}` : ''}</p>
          </div>
          <button type="button" className="fullTextModalClose" onClick={onClose} aria-label="닫기">
            <X size={18} strokeWidth={2.4} aria-hidden="true" />
          </button>
        </div>

        <div className="fullTextModalBody">
          {status === 'loading' ? <p className="helperText">원문을 불러오는 중…</p> : null}
          {status === 'error' ? <p className="apiPendingMessage" role="status">{message}</p> : null}
          {status === 'ready' ? (
            text
              ? <pre className="fullTextModalText">{text}</pre>
              : <p className="helperText">원문이 비어 있습니다. 국가법령정보센터에서 확인해 주세요.</p>
          ) : null}
        </div>

        <div className="fullTextModalFoot">
          {/* 목록 카드에 보이던 것이 조각 하나였다는 사실을 밝혀 둡니다. 여기 뜬 것이
              '전체'라는 것을 알아야, 카드에서 본 것과 길이가 달라도 오류로 읽지 않습니다. */}
          <span className="helperText">색인에 저장된 원문 전체입니다 · 목록 카드에는 일부만 보입니다</span>
          <button type="button" className="secondaryActionButton compactAction" onClick={onClose}>닫기</button>
        </div>
      </div>
    </div>
  );
}
