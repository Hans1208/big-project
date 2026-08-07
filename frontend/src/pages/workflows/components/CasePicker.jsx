import React, { useId, useRef, useState } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import { caseOptions, matchesCasePickerQuery, casePickerDateLabel } from '../shared/caseHelpers.js';
import { useDismissOnOutsideOrEscape } from '../../../hooks/useDismissOnOutsideOrEscape.js';

export function CasePicker({ consultations, value, onChange, placeholder = '사건을 선택하세요' }) {
  const containerRef = useRef(null);
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  useDismissOnOutsideOrEscape(containerRef, open, () => setOpen(false));
  const options = caseOptions(consultations);
  const matchedSelection = options.find((item) => String(item.id) === String(value));
  const selected = matchedSelection || options[0];
  const filteredOptions = options.filter((item) => matchesCasePickerQuery(item, query));
  // matchedSelection이 없으면(예: value가 아직 존재하지 않는 사건을 가리킴) 목록의 첫 항목을
  // 화면에 마치 선택된 것처럼 보여주면 안 됩니다 — 실제로는 아무 사건도 선택되지 않은
  // 상태라 통화/메모 컨트롤이 비활성 상태로 남는데, 여기서 첫 사건 정보를 그대로 보여주면
  // 사용자는 사건이 선택된 것으로 착각하고 왜 입력이 안 되는지 알 수 없습니다.
  const hasSelectableCase = Boolean(matchedSelection) && matchedSelection.id !== 'empty';

  const selectCase = (item) => {
    if (item.id === 'empty') return;
    onChange(item.id);
    setQuery('');
    setOpen(false);
  };

  return (
    <div className="casePicker" ref={containerRef}>
      <button
        className="casePickerButton"
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
      >
        <span className="casePickerButtonText">
          <strong>{hasSelectableCase ? selected.caseNo : placeholder}</strong>
          <span>{hasSelectableCase ? `${selected.name || '상담자 미지정'} · ${selected.title || '상담 제목 미입력'}` : selected?.title || '등록된 상담이 없습니다.'}</span>
          {hasSelectableCase ? <small>{casePickerDateLabel(selected)}</small> : null}
        </span>
        <ChevronDown size={18} strokeWidth={2.2} aria-hidden="true" />
      </button>
      {open ? (
        <div className="casePickerPopover">
          <label className="casePickerSearch">
            <Search size={15} strokeWidth={2.2} aria-hidden="true" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="사건번호, 이름, 제목 검색"
            />
          </label>
          <div className="casePickerList" id={listId} aria-label="상담 선택 목록">
            {filteredOptions.length ? filteredOptions.map((item) => (
              <button
                className={String(item.id) === String(value) ? 'casePickerItem active' : 'casePickerItem'}
                type="button"
                key={item.id}
                disabled={item.id === 'empty'}
                onClick={() => selectCase(item)}
              >
                <span>
                  <strong>{item.caseNo || '사건번호 없음'}</strong>
                  <small>{item.name || '상담자 미지정'} · {item.title || '상담 제목 미입력'}</small>
                </span>
                <em>{item.id === 'empty' ? '없음' : casePickerDateLabel(item)}</em>
              </button>
            )) : (
              <p className="casePickerEmpty">검색 결과 없음</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
