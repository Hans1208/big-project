// 서식 초안 검토 상태(DocumentReviewStatus, backend/core-api)를 화면에 보여줄 라벨/톤으로 바꿉니다.
export const DOCUMENT_STATUS_LABEL = {
  DRAFTED: '초안 작성됨 (검토 요청 전)',
  SUBMITTED_FOR_REVIEW: '변호사 검토 요청됨',
  APPROVED: '변호사 승인 완료',
  REVISION_REQUESTED: '반려됨 (수정 필요)',
};
export function documentStatusTone(status) {
  if (status === 'APPROVED') return 'success';
  if (status === 'REVISION_REQUESTED') return 'danger';
  if (status === 'SUBMITTED_FOR_REVIEW') return 'info';
  return 'muted';
}
export function normalizeGeneratedDocument(response = {}) {
  return {
    documentId: response.document_id || response.documentId || response.local_key,
    consultationId: response.consultation_id || response.consultationId || '',
    status: response.status || 'DRAFTED',
    formName: response.form_name || response.formName || '',
    requestedFormName: response.requested_form_name || response.requestedFormName || '',
    draftFilePath: response.draft_file_path || response.draftFilePath || response.file || '',
    downloadFileName: response.download_file_name || response.downloadFileName || '',
    draftContent: response.draft_content || response.draftContent || '',
    source: response.source || 'core-api',
    localKey: response.local_key || '',
  };
}

// 예전엔 서버가 돌려준 원문 예외 메시지(예: "I/O error on POST request for
// "http://localhost:8001/forms/draft": null")와 내부 서비스 이름('ai-api')을 그대로
// 보여줘서, 상담원이 읽어도 무엇을 해야 할지 알 수 없었습니다(코치 피드백: 개발자 용어를
// 유저 친화적으로). 원인을 알 수 있을 때만 짧게 덧붙이고, 항상 다음 행동을 안내합니다.
export function draftGenerationErrorMessage(error) {
  const isConnectionIssue = /I\/O error|Connection refused|ECONNREFUSED|timeout/i.test(error?.message || '');
  const reason = isConnectionIssue ? ' · 서식 생성 서버에 연결하지 못했습니다' : '';
  return `HWPX 생성에 실패했습니다${reason}. 잠시 후 다시 시도하거나 관리자에게 문의해 주세요.`;
}
