import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';

// 브라우저 기본 alert/confirm은 OS 창이라 이 시스템의 글꼴·색·모서리와 전혀 다르게 보이고,
// 자바스크립트를 멈춰 세워 화면 전환이 끊겨 보입니다.
// 그래서 알림(토스트)과 확인창을 앱 안에서 같은 디자인으로 처리하도록 모아 둡니다.
// 사용법은 LoadingProvider와 동일하게 Provider로 감싸고 훅으로 꺼내 씁니다.

const TOAST_DURATION_MS = 4000;

const ToastContext = createContext(null);
const ConfirmContext = createContext(null);

const TOAST_ICON = {
  success: CheckCircle2,
  warn: AlertTriangle,
  info: Info,
};

function ToastStack({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    // aria-live="polite"로 두면 화면낭독기 사용자에게도 결과가 전달됩니다.
    <div className="toastStack" role="status" aria-live="polite">
      {toasts.map((toast) => {
        const Icon = TOAST_ICON[toast.tone] || TOAST_ICON.info;
        return (
          <div className={`toastItem tone-${toast.tone}`} key={toast.id}>
            <Icon size={18} strokeWidth={2.2} />
            <p>{toast.message}</p>
            <button type="button" aria-label="알림 닫기" onClick={() => onDismiss(toast.id)}>
              <X size={15} strokeWidth={2.4} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

function ConfirmDialog({ request, onAnswer }) {
  const confirmButtonRef = useRef(null);

  // 확인창이 뜨면 기본 버튼에 포커스를 옮겨, 키보드만으로도 바로 Enter/Esc로 답할 수 있게 합니다.
  useEffect(() => {
    if (request) confirmButtonRef.current?.focus();
  }, [request]);

  useEffect(() => {
    if (!request) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onAnswer(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [request, onAnswer]);

  if (!request) return null;

  return (
    <div className="modalBackdrop" role="presentation" onClick={() => onAnswer(false)}>
      <div
        className="modal confirmModal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modalHeader"><h2 id="confirm-title">{request.title}</h2></div>
        {request.message ? <p className="confirmModalMessage">{request.message}</p> : null}
        <div className="inlineControls statusConfirmActions">
          <button className="smallButton light" type="button" onClick={() => onAnswer(false)}>
            {request.cancelLabel || '취소'}
          </button>
          <button
            className={`smallButton ${request.tone === 'danger' ? 'danger' : 'dark'}`}
            type="button"
            ref={confirmButtonRef}
            onClick={() => onAnswer(true)}
          >
            {request.confirmLabel || '확인'}
          </button>
        </div>
      </div>
    </div>
  );
}

function FeedbackProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  // 확인창은 한 번에 하나만 뜨고, 사용자가 답할 때까지 기다려야 하므로 resolve 함수를 함께 들고 있습니다.
  const [confirmState, setConfirmState] = useState(null);

  const dismissToast = useCallback((id) => {
    setToasts((items) => items.filter((item) => item.id !== id));
  }, []);

  const showToast = useCallback((message, tone = 'success') => {
    if (!message) return;
    const id = Date.now() + Math.random();
    setToasts((items) => [...items, { id, message, tone }]);
    setTimeout(() => dismissToast(id), TOAST_DURATION_MS);
  }, [dismissToast]);

  const confirm = useCallback((request) => new Promise((resolve) => {
    // 이미 답변을 기다리는 확인창이 있는데 또 confirm()이 호출되면(중복 클릭 등),
    // 뒤 호출이 앞 호출의 confirmState를 그대로 덮어써서 앞 Promise의 resolve가 유실되고
    // 그 호출부는 영원히 await에서 멈춰 있었습니다. 새 확인창을 띄우기 전에 먼저
    // 이전 확인창을 "취소"로 정리해 그 Promise부터 풀어줍니다.
    setConfirmState((current) => {
      current?.resolve(false);
      return { request: typeof request === 'string' ? { title: request } : request, resolve };
    });
  }), []);

  const answerConfirm = useCallback((answer) => {
    setConfirmState((current) => {
      current?.resolve(answer);
      return null;
    });
  }, []);

  return (
    <ToastContext.Provider value={showToast}>
      <ConfirmContext.Provider value={confirm}>
        {children}
        <ToastStack toasts={toasts} onDismiss={dismissToast} />
        <ConfirmDialog request={confirmState?.request || null} onAnswer={answerConfirm} />
      </ConfirmContext.Provider>
    </ToastContext.Provider>
  );
}

// 화면 오른쪽 아래에 잠깐 떴다 사라지는 알림을 띄웁니다. showToast(메시지, 'success' | 'warn' | 'info')
function useToast() {
  const showToast = useContext(ToastContext);
  if (!showToast) throw new Error('useToast는 <FeedbackProvider> 내부에서만 사용할 수 있습니다.');
  return showToast;
}

// window.confirm 대체. await confirm({ title, message, confirmLabel, tone }) 형태로 씁니다.
function useConfirm() {
  const confirm = useContext(ConfirmContext);
  if (!confirm) throw new Error('useConfirm은 <FeedbackProvider> 내부에서만 사용할 수 있습니다.');
  return confirm;
}

export { FeedbackProvider, useToast, useConfirm };
