import React, { useState } from 'react';
import { User, Lock } from 'lucide-react';
import { WorkPageHeader } from '../../../components/common.jsx';
import { changeCorePassword } from '../../../services/coreApiClientV2.js';
import { validatePassword, PASSWORD_RULE_TEXT } from '../../auth.jsx';

export function ProfilePanel({ role, currentUser, onUpdateProfile }) {
  const [form, setForm] = useState({
    email: currentUser?.email || '',
    organization: currentUser?.organization || '',
    phone: currentUser?.phone || '',
    currentPassword: '',
    password: '',
    confirmPassword: '',
  });
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const mismatch = form.confirmPassword && form.password !== form.confirmPassword;
  const roleLabel = role === 'counselor' ? '상담원' : role === 'lawyer' ? '변호사' : '관리자';
  // 상담원/변호사는 가입 시 등록된 이메일·소속기관이 계정 식별/조직 배정 기준이라
  // 본인이 임의로 바꾸지 못하도록 막습니다. (변경이 필요하면 관리자에게 문의)
  const lockContactFields = role === 'counselor' || role === 'lawyer';
  // 소속은 '지부 / 부서' 한 문자열로 저장되어 있어, 화면에서는 두 칸으로 나눠 보여줍니다.
  // 부서 없이 가입한 예전 계정도 있으므로 branch 필드를 우선 쓰고 없으면 앞부분을 사용합니다.
  const [savedBranch, ...savedDepartmentParts] = (currentUser?.organization || '').split(' / ');
  const branchValue = currentUser?.branch || savedBranch || '';
  const departmentValue = currentUser?.department || savedDepartmentParts.join(' / ');

  const save = async () => {
    if (!form.email) {
      setMessage('이메일을 입력해주세요.');
      return;
    }
    // 관리자만 이메일을 직접 고칠 수 있는데(상담원·변호사는 잠긴 필드), 회원가입 화면의
    // emailInvalid 검사가 여기엔 없어서 '@' 없는 값도 그대로 저장되던 문제가 있었습니다.
    if (!lockContactFields && !form.email.includes('@')) {
      setMessage('올바른 이메일 형식이 아닙니다.');
      return;
    }
    if (mismatch) {
      setMessage('비밀번호와 비밀번호 확인이 일치하지 않습니다.');
      return;
    }
    // 비밀번호는 core-api로 따로 보냅니다.
    //
    // 예전에는 이 값을 onUpdateProfile에 함께 넘겼는데, 받는 쪽(App.updateProfile)이
    // 실제로는 저장하지 않으면서 감사 로그에는 '비밀번호 변경'으로 남겼습니다. 그래서
    // 어떤 값을 넣어도 바뀌지 않는데 화면에는 저장됐다고 뜨는 상태였습니다.
    const wantsPasswordChange = Boolean(form.password);
    if (wantsPasswordChange && !form.currentPassword) {
      setMessage('비밀번호를 바꾸려면 현재 비밀번호를 입력해주세요.');
      return;
    }

    const effectiveEmail = lockContactFields ? (currentUser?.email || '') : form.email;
    // 가입 화면과 동일한 비밀번호 규칙을 프로필 변경에도 적용합니다.
    if (wantsPasswordChange) {
      const passwordRuleError = validatePassword(form.password, effectiveEmail);
      if (passwordRuleError) {
        setMessage(passwordRuleError);
        return;
      }
    }

    setSaving(true);
    try {
      if (wantsPasswordChange) {
        // 서버가 현재 비밀번호 확인·동일 비밀번호 차단·작성규칙 검사를 모두 담당합니다.
        // 실패하면 여기서 멈춰, 연락처만 저장되고 비밀번호는 안 바뀐 채 성공 메시지가
        // 뜨는 일이 없게 합니다.
        await changeCorePassword({ currentPassword: form.currentPassword, newPassword: form.password });
      }
      onUpdateProfile({
        // 잠긴 필드는 화면에서 수정이 막혀 있지만, 혹시 모를 우회를 방지하고자 저장 시에도
        // 원래 계정 값(currentUser)을 그대로 사용하고 form 값은 무시합니다.
        email: lockContactFields ? (currentUser?.email || '') : form.email,
        organization: lockContactFields ? (currentUser?.organization || '') : form.organization,
        // 연락처는 신원·소속 확인용 정보가 아니라 실무 연락 목적이라 역할과 무관하게 본인이 직접 수정할 수 있습니다.
        phone: form.phone,
        passwordChanged: wantsPasswordChange,
      });
      setMessage(wantsPasswordChange ? '프로필과 비밀번호가 저장되었습니다.' : '프로필이 저장되었습니다.');
      setForm((current) => ({ ...current, currentPassword: '', password: '', confirmPassword: '' }));
    } catch (error) {
      setMessage(error.message || '비밀번호를 변경하지 못했습니다.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="workPanel profilePanel">
      <WorkPageHeader
        title="내 정보"
        description={`${roleLabel} 계정의 연락처와 비밀번호를 관리하세요.`}
      />
      <div className="utilityContentCard profileContentCard">
      <div className="profileFormCard">
      <label className="field">
        <span><span className="fieldLabelWithIcon"><User size={14} strokeWidth={2.4} aria-hidden="true" /> 이메일</span></span>
        <input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} type="email" placeholder="이메일 입력" readOnly={lockContactFields} disabled={lockContactFields} />
      </label>
      {/* 상담원·변호사는 가입 시 고른 지부와 입력한 부서를 각각 보여줍니다.
        * 둘 다 조직 배정 기준이라 이메일과 마찬가지로 본인이 고칠 수 없습니다. */}
      {lockContactFields ? (
        <div className="formGrid">
          <label className="field">
            <span>소속기관 (지부)</span>
            <input value={branchValue} placeholder="가입 시 선택한 소속 지부" readOnly disabled />
          </label>
          <label className="field">
            <span>부서</span>
            <input value={departmentValue} placeholder="가입 시 입력한 부서" readOnly disabled />
          </label>
        </div>
      ) : (
        <label className="field">
          <span>소속지부 / 부서</span>
          <input value={form.organization} onChange={(event) => setForm({ ...form, organization: event.target.value })} placeholder="대한법률구조공단 / 전산" />
        </label>
      )}
      {lockContactFields ? <p className="helperText">이메일·소속은 관리자에게 변경 요청</p> : null}
      <label className="field">
        <span>연락처</span>
        <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} type="tel" placeholder="010-0000-0000" />
      </label>
      <div className="formGrid">
        <label className="field">
          <span><span className="fieldLabelWithIcon"><Lock size={14} strokeWidth={2.4} aria-hidden="true" /> 현재 비밀번호</span></span>
          <input value={form.currentPassword} onChange={(event) => setForm({ ...form, currentPassword: event.target.value })} type="password" placeholder="비밀번호를 바꿀 때만 입력" autoComplete="current-password" />
        </label>
      </div>
      <div className="formGrid">
        <label className="field">
          <span><span className="fieldLabelWithIcon"><Lock size={14} strokeWidth={2.4} aria-hidden="true" /> 새 비밀번호</span></span>
          <input value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} type="password" placeholder="변경할 때만 입력" autoComplete="new-password" />
        </label>
        <label className="field">
          <span><span className="fieldLabelWithIcon"><Lock size={14} strokeWidth={2.4} aria-hidden="true" /> 새 비밀번호 확인</span></span>
          <input value={form.confirmPassword} onChange={(event) => setForm({ ...form, confirmPassword: event.target.value })} type="password" placeholder="비밀번호 확인" />
        </label>
      </div>
      <p className="helperText">{PASSWORD_RULE_TEXT}</p>
      {mismatch ? <p className="formError">비밀번호와 비밀번호 확인이 일치하지 않습니다.</p> : null}
      {message ? <p className={message.includes('저장') ? 'helperText success' : 'formError'}>{message}</p> : null}
      <button className="primaryButton" type="button" onClick={save} disabled={saving}>{saving ? '저장 중...' : '프로필 수정 저장'}</button>
      </div>
      </div>
    </section>
  );
}
