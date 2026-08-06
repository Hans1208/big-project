import React from 'react';
import { ShieldCheck } from 'lucide-react';

// 서식 작성용 개인정보(주소·전화번호)와 그 동의를 받는 자리.
//
// ── 왜 서식 초안 화면에 있나
// 상담만 받고 끝나는 경우에는 주소·전화번호가 필요 없습니다. 필요한 것은 서식을
// 만들 때뿐이라, 그때 묻습니다(개인정보 보호법 제3조 제1항 — 필요한 최소한).
// 상담 등록 화면에 두면 서식까지 안 가는 상담에서도 매번 묻게 됩니다.
//
// ── 왜 필수인가
// 법원 서식의 당사자 주소는 송달을 위한 법정 필수 기재사항입니다. 없으면 서류가
// 성립하지 않으므로, '서식 작성'이라는 목적에 대해서는 최소한의 정보가 맞습니다.
// 다만 그 목적을 벗어나면 필수가 아닙니다 — 동의하지 않아도 상담은 계속됩니다.
//
// ── 왜 체크박스가 필요한가
// 상담원이 전화번호를 타이핑한 사실만으로는 동의의 증거가 되지 않습니다. 동의를
// 받았다는 것은 처리자가 입증해야 합니다(개인정보 보호법 제15조). 동의 대화 자체는
// 상담 녹취에 남아 증거가 되고, 이 체크는 "나중에 찾을 수 있게" 하는 표시입니다.
//
// 동의 방법은 시행령 제17조 제1항 제2호가 인정하는 '전화로 동의 내용을 알리고
// 의사표시를 확인하는 방법'입니다. 상담원이 대신 동의하는 것이 아니라 받은 동의를
// 기록하는 자리입니다.
//
// ── 주민등록번호 칸이 없는 이유
// 제24조의2는 주민등록번호를 동의가 아니라 '법령에 구체적 근거가 있을 때'만
// 처리하도록 합니다. 내담자가 동의해도 우리가 보관할 수 없습니다. 초안에서는
// 그 칸에 [직접 기재] 표시가 붙고, 본인 확인을 거쳐 손으로 적습니다.

// 이 동의로 받는 항목. 화면 입력칸과 안내 문구가 이 목록 하나를 같이 보므로,
// 항목을 늘릴 때 한쪽만 고쳐서 어긋나는 일이 없습니다.
//
// "주소·전화번호 등"처럼 뭉뚱그리면 안 됩니다 — 시행령 제17조 제1항은 동의 내용이
// '구체적이고 명확할 것'을 요구하고, 포괄 동의는 무효입니다. 항목을 늘리면 늘어난
// 만큼 여기에 적어야 합니다.
//
// 서식에는 이 밖에도 등록기준지(291개 중 209개)·국적(69개)·직업(16개) 같은 칸이
// 있지만 저장하지 않습니다. 저장하지 않는 항목은 동의 대상이 아닙니다 — 초안에서는
// 빈칸으로 남고 상담원이 증빙을 보며 채웁니다.
// extractedKeys: 분석이 상담에서 뽑아 둔 값을 찾을 키. 프롬프트는 '주소'·'전화번호'로
// 적으라고 하지만 모델이 '연락처'·'거주지'로 흘리는 일이 있어 넓게 잡습니다.
export const DRAFT_CONTACT_FIELDS = [
  {
    key: 'clientAddress',
    label: '주소',
    type: 'text',
    placeholder: '예) 서울특별시 강남구 테헤란로 123, 4층',
    extractedKeys: /주\s*소|거주지/,
  },
  {
    key: 'clientPhone',
    label: '전화번호',
    type: 'tel',
    placeholder: '예) 010-1234-5678',
    extractedKeys: /전\s*화|연락처|휴대폰/,
  },
];

// 상대방·사망자의 것을 상담자 칸에 넣으면 사람이 뒤바뀝니다. 키에 이런 말이 붙어
// 있으면 상담자 본인의 값이 아닙니다.
const NOT_APPLICANT_KEY = /상대방|피신청인|피고|채무자|사망자|피상속인|망인|유언자|등록기준지|최후|본적|법원/;

// 자리표시자가 섞인 값은 버립니다. 분석이 서식 예시(○○시 ○○구)를 그대로 옮겨 적으면
// 채운 것처럼 보이면서 실제로는 빈칸인 상태가 됩니다.
const PLACEHOLDER_CHARS = /[○□◇△▽◎●]/;

// 분석이 상담에서 뽑아 둔 값을 찾습니다. 상담원이 타이핑하는 대신 이 값이 먼저
// 들어가고, 받아쓰기가 틀렸으면 그 자리에서 고칩니다.
function extractedValue(consultation, field) {
  const extracted = consultation?.analysis?.extractedJson;
  if (!extracted || typeof extracted !== 'object') return '';
  for (const [key, value] of Object.entries(extracted)) {
    if (!field.extractedKeys.test(key) || NOT_APPLICANT_KEY.test(key)) continue;
    const text = String(value ?? '').trim();
    if (!text || text === '미상' || PLACEHOLDER_CHARS.test(text)) continue;
    return text;
  }
  return '';
}

// 상담원이 내담자에게 읽어줄 문구. 시행령 제17조가 요구하는 것을 다 담습니다 —
// 하나라도 빠지면 적법한 동의가 아닙니다.
const CONSENT_SCRIPT = [
  '수집 목적 · 법률 서식 작성과 법원 제출',
  `수집 항목 · ${DRAFT_CONTACT_FIELDS.map((item) => item.label).join(', ')}`,
  '보유 기간 · 상담 종결 후 관계 법령이 정한 기간',
  // 상담 원문은 AI 분석을 거칩니다(외부 AI 서비스에 처리를 위탁). 제26조는 위탁
  // 사실의 공개를 요구하므로, 동의를 받는 이 자리에서 함께 알립니다.
  '처리 방식 · 상담 내용은 AI 분석을 거쳐 서식 초안 작성에 이용됩니다',
  '거부 권리 · 동의하지 않아도 상담은 계속됩니다 (다만 서식 초안의 해당 칸이 비어 있게 됩니다)',
];

export function DraftContactConsent({ consultation, onChange, disabled = false }) {
  if (!consultation) return null;

  const consented = Boolean(consultation.privacyConsent);

  // 동의를 켜면 분석이 상담에서 뽑아 둔 값으로 칸을 먼저 채웁니다. 상담원이 구두로
  // 물어본 내용이 받아쓰기를 거쳐 여기까지 온 것이라, 대부분은 확인만 하면 됩니다.
  // 이미 적어 둔 값이 있으면 덮지 않습니다 — 사람이 고친 값이 항상 우선입니다.
  //
  // 동의를 내리면 값도 함께 지웁니다. 서버도 같은 일을 하지만(Consultation.
  // applyDraftContactInfo) 화면에 값이 남아 있으면 상담원은 저장된 줄 압니다.
  const toggleConsent = (next) => {
    if (!next) {
      onChange({ privacyConsent: false, clientAddress: '', clientPhone: '' });
      return;
    }
    const prefilled = {};
    DRAFT_CONTACT_FIELDS.forEach((field) => {
      if (consultation[field.key]) return;
      const found = extractedValue(consultation, field);
      if (found) prefilled[field.key] = found;
    });
    onChange({
      privacyConsent: true,
      // 어느 채널에서 받은 동의인지. 시행령이 인정하는 방법이 채널마다 달라
      // 나중에 입증할 때 필요합니다. 대면 녹음 기록이 있으면 대면으로 봅니다.
      privacyConsentSource: consultation.inpersonMemo ? 'inperson' : 'call',
      ...prefilled,
    });
  };

  return (
    <section className="documentReviewPanel draftConsentPanel">
      <div className="panelTitleRow">
        <h3>
          <ShieldCheck size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" />
          서식에 넣을 주소 · 전화번호
        </h3>
        {consented ? <span className="statusChip tone-ok">동의 기록됨</span> : null}
      </div>

      <label className="draftConsentCheck">
        <input
          type="checkbox"
          checked={consented}
          disabled={disabled}
          onChange={(event) => toggleConsent(event.target.checked)}
        />
        <span>
          <strong>개인정보 수집·이용에 동의받았습니다</strong>
          <small>아래 내용을 내담자에게 안내하고 동의를 받은 뒤 체크하세요. 동의 내용은 상담 녹취에 함께 남습니다.</small>
        </span>
      </label>

      <ul className="draftConsentScript">
        {CONSENT_SCRIPT.map((line) => <li key={line}>{line}</li>)}
      </ul>

      {/* 체크 전에는 입력칸을 아예 그리지 않습니다. 회색으로 잠가두면 상담원이
          먼저 타이핑하려다 막히고, 반대로 열어두면 타이핑한 뒤 체크를 잊어
          서버가 값을 버립니다("입력했는데 왜 안 들어갔지"). */}
      {consented ? (
        <div className="draftConsentFields">
          {/* 안내 문구와 같은 목록으로 그립니다 — 항목을 늘릴 때 한쪽만 고쳐서
              "동의는 두 개 받고 세 개를 저장하는" 상태가 되지 않게 합니다. */}
          {DRAFT_CONTACT_FIELDS.map((item) => {
            const value = consultation[item.key] || '';
            // 받아쓰기에서 온 값 그대로인지. 상담원이 한 글자라도 고치면 표시가
            // 사라져, 어디까지 사람이 확인한 값인지 한눈에 보입니다.
            const fromStt = Boolean(value) && value === extractedValue(consultation, item);
            return (
              <label className="field" key={item.key}>
                <span>
                  {item.label}
                  {fromStt ? <em className="nameSourceAi">받아쓰기에서 가져옴 · 확인해주세요</em> : null}
                </span>
                <input
                  type={item.type}
                  value={value}
                  disabled={disabled}
                  placeholder={item.placeholder}
                  onChange={(event) => onChange({ [item.key]: event.target.value })}
                />
              </label>
            );
          })}
          {/* 숫자는 받아쓰기가 특히 약합니다("011216 삼삼삼삼삼삼삼"처럼 한글로 적힙니다).
              잘못 적힌 주소·전화번호는 송달 실패로 이어지므로 눈으로 한 번 봐야 합니다. */}
          <p className="helperText">
            상담에서 들은 값을 먼저 채워둡니다 · <strong>틀린 곳은 그 자리에서 고쳐주세요</strong> (특히 숫자)
          </p>
          <p className="helperText">
            주민등록번호는 저장하지 않습니다 · 초안의 해당 칸은 <strong>[직접 기재]</strong>로 표시되며 본인 확인 후 손으로 적습니다
          </p>
        </div>
      ) : (
        <p className="helperText">
          동의를 받지 않아도 초안은 만들 수 있습니다 · 주소·전화칸이 빈 채로 생성되어 상담원이 직접 채우게 됩니다
        </p>
      )}
    </section>
  );
}
