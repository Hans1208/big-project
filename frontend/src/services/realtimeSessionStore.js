import { readStorage, storageKeys } from './storage.js';

// 실제 통화 연동 없이 상담원이 직접 버튼을 눌러 관리하는 상태라, 브라우저를 오래 열어둔 채
// 방치된 '진행 중' 표시를 언제까지고 진짜처럼 보여주면 오히려 혼란을 줍니다. 이 시간이 지난
// ongoing 기록은 복원하지 않고 새로 시작한 것으로 취급합니다.
const STALE_AFTER_MS = 6 * 60 * 60 * 1000; // 6시간

function readAllDrafts() {
  return readStorage(storageKeys.realtimeSessionDrafts, {});
}

function isStaleOngoingDraft(draft) {
  return draft.callStatus === 'ongoing' && Date.now() - (draft.callStartedAt || 0) > STALE_AFTER_MS;
}

// 지금 통화 중인 사건이 있으면(다른 메뉴에 가 있어도) 화면 상단에서 바로 알 수 있도록,
// 사건을 가리지 않고 '통화 중' 상태인 기록을 하나 찾아줍니다. 동시에 두 통화를 받을 수는 없으므로
// 하나만 있으면 충분합니다.
export function findOngoingCallDraft() {
  const drafts = readAllDrafts();
  const ongoingEntry = Object.entries(drafts).find(([, draft]) => !isStaleOngoingDraft(draft) && draft.callStatus === 'ongoing');
  if (!ongoingEntry) return null;
  const [consultationId, draft] = ongoingEntry;
  return { consultationId, ...draft };
}
