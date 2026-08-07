import { useEffect } from 'react';

// 사건 선택(CasePicker)·서식 선택(ChoicePicker)·달력(CalendarPicker) 드롭다운이 각자 따로
// 구현되면서 셋 다 같은 구멍이 있었습니다: 열어놓은 채로 Esc를 누르거나 팝업 바깥을 눌러도
// 안 닫혔습니다(트리거 버튼을 다시 눌러야만 닫힘). 키보드 사용자는 다른 곳으로 포커스를
// 옮기기도 전에 팝업이 계속 열려 있어 혼란스럽습니다. 세 컴포넌트가 같은 문제를 각자
// 겪고 있어 한 곳에서 고칩니다.
export function useDismissOnOutsideOrEscape(containerRef, isOpen, onDismiss) {
  useEffect(() => {
    if (!isOpen) return undefined;
    const handlePointerDown = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) onDismiss();
    };
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onDismiss();
    };
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);
}
