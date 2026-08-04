export const legalAidApplicantTypes = [
  { key: 'none', label: '해당 없음', evidence: '대상자 증빙 없음' },
  { key: 'basicLivelihood', label: '기초생활수급자', evidence: '수급자 증명서' },
  { key: 'nearPoverty', label: '차상위계층', evidence: '차상위계층 확인서' },
  { key: 'disabled', label: '장애인', evidence: '장애인증명서 또는 복지카드' },
  { key: 'nationalMerit', label: '국가유공자', evidence: '국가유공자 확인서' },
  { key: 'crimeVictim', label: '범죄피해자', evidence: '피해사실 확인자료' },
  { key: 'domesticViolence', label: '가정폭력·성폭력 피해자', evidence: '상담확인서 또는 피해확인자료' },
  { key: 'wageArrears', label: '임금등 체불 피해근로자', evidence: '체불임금 확인자료' },
  { key: 'courtRescue', label: '법원의 소송구조 결정자', evidence: '소송구조 결정문' },
  { key: 'other', label: '기타 법률구조 대상자', evidence: '대상자 확인자료' },
];
// AI 백본 extracted_content_detail의 status 값을 사람이 읽을 수 있는 라벨로 변환합니다.
export function extractionStatusLabel(status) {
  const labels = { success: '추출 성공', empty: '내용 없음', unsupported: '미지원', failed: '처리 실패' };
  return labels[status] || status;
}

export function getEligibilityBadgeText(isApplicant, evidenceSubmitted) {
  if (!isApplicant) return '대상 아님';
  if (!evidenceSubmitted) return '증빙 필요';
  return '대상 확인';
}

export function getEligibilityHelperText(isApplicant, evidenceSubmitted) {
  if (!isApplicant) return '법률구조 대상 유형에 해당하지 않는 것으로 표시됩니다.';
  if (!evidenceSubmitted) return '법률구조 대상자에 해당할 수 있으나 증빙서류가 아직 제출되지 않았습니다.';
  return '법률구조 대상자로 확인되었고 증빙서류 제출도 완료되었습니다.';
}

// 업로드 상태 문자열을 상태 칩 색 톤으로 매핑합니다.
export function uploadStatusTone(status) {
  if (status === '업로드 완료' || status === '업로드·텍스트 변환 완료' || status === '서버 저장') return 'tone-success';
  if (status === '업로드 실패') return 'tone-danger';
  if (status === '업로드 중') return 'tone-info';
  return 'tone-warn'; // 로컬 보관 (S3 대기) 등
}
// 상담 검토 요청에 이미 담긴 법률구조 대상 정보(사람이 읽는 라벨)를, 이 화면의 select가 쓰는
// key 값으로 되돌립니다. 기존 상담을 골랐을 때 폼을 그 상담의 현재 값으로 채우는 데 씁니다.
export function resolveLegalAidTypeKey(applicantTypeLabel) {
  const matched = legalAidApplicantTypes.find((item) => item.label === applicantTypeLabel);
  return matched ? matched.key : 'none';
}

export function buildEligibilityDraftFromCase(selectedCase) {
  const check = selectedCase?.eligibilityCheck;
  return {
    legalAidType: check ? resolveLegalAidTypeKey(check.applicantType) : 'none',
    eligibilityEvidenceSubmitted: Boolean(check?.evidenceSubmitted),
  };
}

// 통화 전에 자료부터 올려두는 드문 경우를 위한 자동 제목입니다. 상담자 이름·제목은
// 실시간 상담 화면에서 통화 중에 채우므로 여기서는 입력받지 않습니다. (코치 피드백)
export function buildAutoUploadTitle() {
  const now = new Date();
  const label = `${String(now.getMonth() + 1).padStart(2, '0')}/${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  return `상담 자료 올리기 (${label} 등록)`;
}

// 업로드 자료 종류(녹취록/신분증/증빙자료)는 드롭존 옆 select로 고르고, 실제 파일 받기는
// 드롭존 하나로 통일합니다. 버튼 세 개를 늘어놓던 이전 방식보다 화면이 훨씬 단순해집니다.
export const uploadCategoryOptions = ['녹취록', '신분증', '증빙자료'];

// 자료 유형별로 받을 파일 종류를 제한합니다.
//
// 유형은 뒤 단계에서 파일을 어떻게 처리할지를 정합니다 — 녹취록은 STT로 텍스트를 뽑고,
// 신분증·증빙자료는 OCR/문서 추출로 갑니다. 녹취록 자리에 사진이 들어가면 STT가 처리할 수
// 없는 파일을 붙들게 되고, 상담원은 분석 결과에 녹취 내용이 왜 없는지 한참 뒤에야 알게 됩니다.
// 고르는 순간 막아서 그런 상황 자체를 없앱니다.
export const uploadCategoryAccept = {
  '녹취록': '.mp3,.wav,.m4a',
  '신분증': '.jpg,.jpeg,.png',
  '증빙자료': '.pdf,.hwp,.hwpx,.doc,.docx,.txt',
};
export function fileMatchesCategory(file, category) {
  const allowed = uploadCategoryAccept[category];
  if (!allowed) return true;
  const dot = file.name.lastIndexOf('.');
  const ext = dot === -1 ? '' : file.name.slice(dot).toLowerCase();
  return allowed.split(',').includes(ext);
}
// 멀티모달 분석: 면담 텍스트뿐 아니라 녹취(mp3 등)·이미지·문서 첨부자료까지 함께 고려해서
// 사건 유형/긴급도 후보를 산출한다는 것을 화면에서 확인할 수 있도록 구성했습니다.
export function summarizeAttachmentModalities(attachments = []) {
  const audio = attachments.filter((item) => /mp3|wav|m4a/i.test(item.mimeType || item.name || ''));
  const image = attachments.filter((item) => /png|jpe?g/i.test(item.mimeType || item.name || ''));
  const document = attachments.filter((item) => /pdf|hwpx|doc/i.test(item.mimeType || item.name || ''));
  return [
    { key: '녹취(mp3 등)', count: audio.length },
    { key: '이미지(png/jpg)', count: image.length },
    { key: '문서(pdf/hwpx 등)', count: document.length },
  ];
}

// AI 백본(ai-api) case_analysis 출력의 extracted_content_detail을 화면에 그대로 보여주기 위한 mock 생성기입니다.
// 노트북 기준 파일별 상태: success(추출 성공) / empty(내용없음) / unsupported(레거시 hwp 등 변환 필요) / failed(다운로드·추출 실패)
export function buildExtractionDetail(attachments = []) {
  return attachments.map((item) => {
    const name = item.name || '';
    const isHwpx = /\.hwpx$/i.test(name) || /hwpx/i.test(item.mimeType || '');
    const isLegacyHwp = /\.hwp$/i.test(name) || /hwp/i.test(item.mimeType || '') && !isHwpx;
    const isAudio = /mp3|wav|m4a/i.test(item.mimeType || name);
    const status = isLegacyHwp ? 'unsupported' : 'success';
    const fileType = isAudio ? 'audio_video' : isLegacyHwp ? 'legacy_hwp_convert_required' : isHwpx ? 'hwpx_document' : /png|jpe?g/i.test(name) ? 'image' : 'document';
    return {
      fileLink: item.fileKey || item.uploadedUrl || name,
      fileName: name,
      fileType,
      status,
      // 서식 자동 채움은 표/셀 XML 접근이 가능한 hwpx를 기준으로 처리합니다. 이 note는 화면에
      // 그대로 노출되는 문구라(코치 피드백: 개발자 용어를 유저 친화적으로), 내부 기술 이름
      // (Whisper·XML·레거시)은 빼고 상담원이 바로 이해할 수 있는 말로 풀어 씁니다.
      note: isLegacyHwp ? '예전 형식(.hwp) 파일이에요. 최신 형식(.hwpx)으로 바꾸면 자동 채움에 쓸 수 있어요.' : isHwpx ? '문서의 표·항목에서 자동으로 값을 채울 수 있어요.' : isAudio ? '통화 음성을 텍스트로 변환해 분석했습니다.' : '문서 텍스트 추출',
    };
  });
}

export function buildAttachmentLinkMetadata(attachments = []) {
  return attachments.map((item) => ({
    category: item.category || '',
    fileName: item.name || item.fileName || '',
    fileType: item.mimeType || item.fileType || '',
    storageBucket: item.storageBucket || '',
    fileKey: item.fileKey || '',
    fileUrl: item.uploadedUrl || item.fileUrl || '',
    status: item.status || '',
  })).filter((item) => item.fileName || item.fileKey || item.fileUrl);
}

export function attachmentLinkValues(attachments = []) {
  return buildAttachmentLinkMetadata(attachments)
    .map((item) => item.fileKey || item.fileUrl || item.fileName)
    .filter(Boolean);
}
