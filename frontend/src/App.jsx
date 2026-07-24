import React, { useEffect, useState } from 'react';

// 화면 전환과 전역 상태를 관리하는 프론트엔드 최상위 컴포넌트입니다.
import { Header, Footer, DashboardHeader } from './components/layout.jsx';
import { initialConsultations, initialReviews, today } from './constants.jsx';
import { LoginPage, RegisterPage, PasswordFindPage } from './pages/auth.jsx';
import { CounselorDashboard, LawyerDashboard, AdminDashboard } from './pages/dashboards.jsx';
import { appendAuditLog, readStorage, storageKeys, writeStorage } from './services/storage.js';
import { LoadingProvider } from './components/loading.jsx';
import { FeedbackProvider } from './components/feedback.jsx';
import { createCoreAnalysis, createCoreConsultation, updateCoreConsultation } from './services/coreApiClient.js';

// 로그인한 역할에 따라 상담원/변호사/관리자 대시보드를 분기합니다.
function DashboardPage({ role, currentUser, onUpdateProfile, onLogout, users, onUpdateUserStatus }) {
  const defaultView = '대시보드';
  const [activeView, setActiveView] = useState(defaultView);
  const [focusedConsultationId, setFocusedConsultationId] = useState(null);
  const [focusedReviewCaseNo, setFocusedReviewCaseNo] = useState(null);
  const [consultations, setConsultations] = useState(() => readStorage(storageKeys.consultations, initialConsultations));
  const [reviews, setReviews] = useState(() => readStorage(storageKeys.reviews, initialReviews));
  const [notifications, setNotifications] = useState(() => readStorage(storageKeys.notifications, []));

  useEffect(() => {
    writeStorage(storageKeys.consultations, consultations);
  }, [consultations]);

  useEffect(() => {
    writeStorage(storageKeys.reviews, reviews);
  }, [reviews]);

  useEffect(() => {
    writeStorage(storageKeys.notifications, notifications);
  }, [notifications]);

  const notificationUserKey = (targetRole = role, targetEmail = currentUser?.email) => `${targetRole}:${targetEmail || 'all'}`;
  const isNotificationVisible = (item, targetRole = role, targetEmail = currentUser?.email) => {
    if (!item.roles?.includes(targetRole)) return false;
    if (item.recipientEmail && item.recipientEmail !== targetEmail) return false;
    const personalKey = notificationUserKey(targetRole, targetEmail);
    return !item.deletedBy?.includes(targetRole) && !item.deletedBy?.includes(personalKey);
  };
  const isNotificationUnread = (item, targetRole = role, targetEmail = currentUser?.email) => {
    const personalKey = notificationUserKey(targetRole, targetEmail);
    return !item.readBy?.includes(targetRole) && !item.readBy?.includes(personalKey);
  };

  const addNotification = ({ roles, title, message, target, recipientEmail }) => {
    const roleList = Array.isArray(roles) ? roles : [roles];
    setNotifications((items) => [{
      id: Date.now() + Math.random(),
      roles: roleList,
      title,
      message,
      target: target || '',
      recipientEmail: recipientEmail || '',
      createdAt: new Date().toISOString(),
      readBy: [],
    }, ...items]);
  };

  const markNotificationsRead = (targetRole, targetEmail) => {
    const personalKey = notificationUserKey(targetRole, targetEmail);
    setNotifications((items) => items.map((item) => isNotificationVisible(item, targetRole, targetEmail) ? {
      ...item,
      readBy: item.readBy?.includes(personalKey) ? item.readBy : [...(item.readBy || []), personalKey],
    } : item));
  };

  const markNotificationRead = (notificationId, targetRole, targetEmail) => {
    const personalKey = notificationUserKey(targetRole, targetEmail);
    setNotifications((items) => items.map((item) => item.id === notificationId && item.roles.includes(targetRole) ? {
      ...item,
      readBy: item.readBy?.includes(personalKey) ? item.readBy : [...(item.readBy || []), personalKey],
    } : item));
  };

  const deleteNotification = (notificationId, targetRole, targetEmail) => {
    const personalKey = notificationUserKey(targetRole, targetEmail);
    setNotifications((items) => items.map((item) => item.id === notificationId && item.roles.includes(targetRole) ? {
      ...item,
      deletedBy: item.deletedBy?.includes(personalKey) ? item.deletedBy : [...(item.deletedBy || []), personalKey],
    } : item));
  };

  const openNotification = (notification) => {
    markNotificationRead(notification.id, role, currentUser?.email);
    if (role === 'counselor') {
      const target = consultations.find((item) => item.caseNo === notification.target);
      if (target) {
        setFocusedConsultationId(target.id);
        setActiveView('기타');
        return;
      }
    }
    if (role === 'lawyer') {
      setFocusedReviewCaseNo(notification.target || null);
      setActiveView('대시보드');
      return;
    }
    setActiveView('대시보드');
  };

  const unreadCount = notifications.filter((item) => isNotificationVisible(item) && isNotificationUnread(item)).length;

  // 백엔드 상담 등록 API가 연결되기 전까지 로컬 상태에 상담을 생성합니다.
  // 변호사 검토 요청은 상담 분석 저장 이후 상담원이 명시적으로 요청할 때 생성합니다.
  const createConsultation = async (form) => {
    const id = consultations.length ? Math.max(...consultations.map((item) => item.id)) + 1 : 1;
    const caseNo = `C-2026-${String(id).padStart(3, '0')}`;
    const now = new Date();
    const registeredTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    let coreSync = null;
    let coreSyncError = '';
    try {
      coreSync = await createCoreConsultation({ currentUser: { ...currentUser, role }, consultation: form });
    } catch (error) {
      coreSyncError = error.message;
    }

    const nextConsultation = {
      id,
      caseNo,
      ...(coreSync || {}),
      date: today,
      registeredTime,
      workflowStatus: '상담 완료',
      counselor: {
        name: currentUser?.name || '상담원',
        email: currentUser?.email || '',
        organization: currentUser?.organization || '',
      },
      logs: [{ status: '상담 접수', createdAt: today }],
      analysis: null,
      ...form,
    };
    setConsultations((items) => [nextConsultation, ...items]);
    appendAuditLog({
      actor: currentUser?.email || '상담원',
      action: '상담 등록',
      target: caseNo,
      metadata: {
        title: form.title,
        type: form.type,
        counselor: currentUser?.name || '상담원',
        client: form.name,
        legalAidType: form.eligibilityCheck?.applicantType || '',
        coreId: coreSync?.coreId || '',
        coreSyncError,
      },
    });
    setActiveView('대시보드');
    return {
      ok: true,
      coreSynced: Boolean(coreSync),
      message: coreSync
        ? '상담이 등록되었고 Core API에도 저장되었습니다.'
        : '상담이 등록되었습니다. Core API는 나중에 다시 동기화할 수 있습니다.',
    };
  };

  const notifyAnalysisSaved = async (consultation, analysis) => {
    if (!consultation) return { ok: false, message: '상담 정보를 찾을 수 없습니다.' };
    if (!consultation.coreId) return { ok: true, synced: false, message: '로컬 저장 완료' };
    try {
      await createCoreAnalysis({ consultation, analysis });
      await updateCoreConsultation(consultation.coreId, {
        status: 'ANALYZING',
        title: consultation.title,
        inputText: consultation.memo || consultation.title || '',
        opponentName: consultation.opponentName || consultation.name || '',
      });
      return { ok: true, synced: true, message: 'Core API 분석 저장까지 완료되었습니다.' };
    } catch {
      return { ok: true, synced: false, message: '로컬 저장 완료' };
    }
  };

  const requestLegalReview = (consultationId, analysis) => {
    const target = consultations.find((item) => item.id === consultationId);
    if (!target) return { ok: false, message: '검토 요청할 상담을 찾을 수 없습니다.' };

    const nextReview = {
      id: target.id,
      caseNo: target.caseNo,
      type: analysis?.caseType || target.type,
      title: target.title,
      status: '검토 대기',
      requestedAt: today,
      summary: analysis?.summary || '',
      urgency: analysis?.urgency || '',
      eligibility: analysis?.eligibility || '',
      analysis,
      counselor: target.counselor || null,
      lawyer: null,
    };

    setReviews((items) => {
      const exists = items.some((item) => item.id === target.id);
      if (exists) return items.map((item) => item.id === target.id ? { ...item, ...nextReview } : item);
      return [nextReview, ...items];
    });
    setConsultations((items) => items.map((item) => item.id === target.id ? {
      ...item,
      workflowStatus: '법률 검토',
      reviewAction: null,
      logs: [...(item.logs || []), { status: '변호사 검토 요청', createdAt: today }],
    } : item));
    appendAuditLog({ actor: currentUser?.email || '상담원', action: '변호사 검토 요청', target: target.caseNo, metadata: { title: target.title, type: nextReview.type, counselor: target.counselor?.name || currentUser?.name || '상담원', caseType: nextReview.type, eligibility: nextReview.eligibility } });
    addNotification({ roles: 'lawyer', title: '새 검토 요청', message: `${target.caseNo} ${target.title}`, target: target.caseNo });
    return { ok: true, message: '변호사 검토 요청이 등록되었습니다.' };
  };

  const applyReviewDecision = ({ id, status, reason, reviewer, recipientEmail }) => {
    const needsCounselorWork = ['수정 요청', '추가자료 요청', '반려', '보류'].includes(status);
    setFocusedReviewCaseNo(null);
    setConsultations((items) => items.map((item) => {
      if (item.id !== id) return item;
      return {
        ...item,
        status: status === '승인' ? '완료' : status === '반려' || status === '보류' ? '보류' : '진행 중',
        workflowStatus: needsCounselorWork ? status : '승인 완료',
        lawyer: reviewer || null,
        reviewAction: needsCounselorWork ? { status, reason: reason || '', reviewer: reviewer || null, recipientEmail: recipientEmail || item.counselor?.email || '', requestedAt: today, resolved: false } : null,
        logs: [...(item.logs || []), { status: `변호사 검토 결과: ${status}`, reason: reason || '', createdAt: today }],
      };
    }));
  };

  // 상담 삭제 시 연결된 검토 요청도 함께 정리합니다.
  const deleteConsultation = (id) => {
    const target = consultations.find((item) => item.id === id);
    setConsultations((items) => items.filter((item) => item.id !== id));
    setReviews((items) => items.filter((item) => item.id !== id));
    appendAuditLog({ actor: currentUser?.email || '상담원', action: '상담 삭제', target: target?.caseNo || String(id) });
  };

  return (
    <div className="dashboardScreen">
      <DashboardHeader role={role} activeView={activeView} onViewChange={setActiveView} onLogout={onLogout} currentUser={currentUser} unreadCount={unreadCount} />
      {role === 'counselor' ? <CounselorDashboard consultations={consultations} setConsultations={setConsultations} onCreateConsultation={createConsultation} onRequestLegalReview={requestLegalReview} onAnalysisSaved={notifyAnalysisSaved} onDeleteConsultation={deleteConsultation} onOpenConsultationForm={() => setActiveView('상담 등록')} onOpenAnalysis={(id) => { setFocusedConsultationId(id); setActiveView('기타'); }} onGoToDashboard={() => setActiveView('대시보드')} activeView={activeView} currentUser={currentUser} onUpdateProfile={onUpdateProfile} notifications={notifications} onReadNotifications={markNotificationsRead} onDeleteNotification={deleteNotification} onOpenNotification={openNotification} focusedConsultationId={focusedConsultationId} /> : null}
      {role === 'lawyer' ? <LawyerDashboard reviews={reviews} setReviews={setReviews} onReviewDecision={applyReviewDecision} onGoToDashboard={() => setActiveView('대시보드')} activeView={activeView} currentUser={currentUser} onUpdateProfile={onUpdateProfile} notifications={notifications} onReadNotifications={markNotificationsRead} onDeleteNotification={deleteNotification} onOpenNotification={openNotification} onNotify={addNotification} focusedReviewCaseNo={focusedReviewCaseNo} /> : null}
      {role === 'admin' ? <AdminDashboard users={users} onUpdateUserStatus={onUpdateUserStatus} consultations={consultations} reviews={reviews} activeView={activeView} currentUser={currentUser} onUpdateProfile={onUpdateProfile} notifications={notifications} onReadNotifications={markNotificationsRead} onDeleteNotification={deleteNotification} onOpenNotification={openNotification} /> : null}
    </div>
  );
}
function App() {
  const [page, setPage] = useState('login');
  const [rememberId, setRememberId] = useState(() => Boolean(window.localStorage.getItem('rememberedEmail')));
  const [loginForm, setLoginForm] = useState(() => ({
    email: window.localStorage.getItem('rememberedEmail') || '',
    password: '',
  }));
  const [loginError, setLoginError] = useState('');
  const [registeredRole, setRegisteredRole] = useState(() => {
    const savedRole = window.localStorage.getItem('registeredRole');
    return ['counselor', 'lawyer', 'admin'].includes(savedRole) ? savedRole : 'counselor';
  });
  const [users, setUsers] = useState(() => readStorage(storageKeys.users, JSON.parse(window.localStorage.getItem('registeredUsers') || '[]')));
  const [currentUserEmail, setCurrentUserEmail] = useState('');
  const handleLogin = (event) => {
    event.preventDefault();
    const matchedUser = users.find((user) => user.email === loginForm.email && user.password === loginForm.password);
    if (!matchedUser) {
      setLoginError('회원가입한 이메일과 비밀번호가 일치해야 로그인할 수 있습니다.');
      return;
    }
    // 상담원/변호사는 관리자 승인이 완료된 계정만 로그인할 수 있습니다. (관리자 계정은 가입과 동시에 자동 승인)
    if (matchedUser.status === '대기') {
      setLoginError('관리자 승인 대기 중인 계정입니다. 승인이 완료된 후 로그인할 수 있습니다.');
      return;
    }
    if (matchedUser.status === '거절') {
      setLoginError('가입이 거절된 계정입니다. 관리자에게 문의해주세요.');
      return;
    }
    setLoginError('');
    setRegisteredRole(matchedUser.role);
    setCurrentUserEmail(matchedUser.email);
    appendAuditLog({ actor: matchedUser.email, action: '로그인', target: matchedUser.role });
    if (rememberId) {
      window.localStorage.setItem('rememberedEmail', matchedUser.email);
    } else {
      window.localStorage.removeItem('rememberedEmail');
    }
    window.localStorage.setItem('registeredRole', matchedUser.role);
    setPage('dashboard');
  };

  const handleQuickLogin = (role) => {
    // 가입 신청일이 없는 데모 계정도 실제 가입자와 동일하게 오늘 날짜로 채워, 관리자 화면에서 '-'로 비어 보이지 않게 합니다.
    const demoAccounts = {
      counselor: { name: '테스트', organization: '서울중앙지부 / 법률구조1부', branch: '서울중앙지부', department: '법률구조1부', phone: '010-1234-5601', email: 'demo.counselor@test.local', password: 'demo1234', role: 'counselor', status: '승인', requestedAt: today },
      lawyer: { name: '테스트', organization: '서울중앙지부 / 송무부', branch: '서울중앙지부', department: '송무부', phone: '010-1234-5602', email: 'demo.lawyer@test.local', password: 'demo1234', role: 'lawyer', status: '승인', requestedAt: today },
      admin: { name: '테스트', organization: '대한법률구조공단 / 운영팀', phone: '010-1234-5603', email: 'demo.admin@test.local', password: 'demo1234', role: 'admin', status: '승인', requestedAt: today },
    };
    const demoUser = demoAccounts[role];
    if (!demoUser) return;
    const nextUsers = [demoUser, ...users.filter((user) => user.email !== demoUser.email)];
    setUsers(nextUsers);
    writeStorage(storageKeys.users, nextUsers);
    window.localStorage.setItem('registeredUsers', JSON.stringify(nextUsers));
    setLoginError('');
    setRegisteredRole(demoUser.role);
    setCurrentUserEmail(demoUser.email);
    appendAuditLog({ actor: demoUser.email, action: '테스트 빠른 로그인', target: demoUser.role });
    window.localStorage.setItem('registeredRole', demoUser.role);
    setPage('dashboard');
  };

  const currentUser = users.find((user) => user.email === currentUserEmail) || null;
  const updateProfile = ({ email, password, organization, phone }) => {
    if (!currentUser) return;
    const updatedUser = { ...currentUser, email, password, organization: organization ?? currentUser.organization, phone: phone ?? currentUser.phone };
    const nextUsers = users.map((user) => user.email === currentUser.email ? updatedUser : user);
    setUsers(nextUsers);
    setCurrentUserEmail(email);
    setLoginForm({ email, password: '' });
    writeStorage(storageKeys.users, nextUsers);
    window.localStorage.setItem('registeredUsers', JSON.stringify(nextUsers));
    if (rememberId) window.localStorage.setItem('rememberedEmail', email);
    appendAuditLog({
      actor: email,
      action: '프로필 수정',
      target: currentUser.role,
      metadata: {
        emailChanged: currentUser.email !== email,
        emailBefore: currentUser.email,
        emailAfter: email,
        organizationChanged: currentUser.organization !== organization,
        organizationBefore: currentUser.organization || '',
        organizationAfter: organization || '',
        phoneChanged: (currentUser.phone || '') !== (phone || ''),
        phoneBefore: currentUser.phone || '',
        phoneAfter: phone || '',
        passwordChanged: Boolean(password),
      },
    });
  };

  // 관리자가 상담원/변호사 가입 신청을 승인·거절합니다. 승인 전에는 handleLogin에서 로그인이 막힙니다.
  const updateUserStatus = (email, status) => {
    const nextUsers = users.map((user) => user.email === email ? { ...user, status } : user);
    setUsers(nextUsers);
    writeStorage(storageKeys.users, nextUsers);
    window.localStorage.setItem('registeredUsers', JSON.stringify(nextUsers));
    appendAuditLog({ actor: currentUser?.email || '관리자', action: `계정 ${status}`, target: email });
  };

  const notifyAdminRegistrationRequest = (user) => {
    if (user.role === 'admin') return;
    const currentNotifications = readStorage(storageKeys.notifications, []);
    writeStorage(storageKeys.notifications, [{
      id: Date.now() + Math.random(),
      roles: ['admin'],
      title: '회원가입 승인 요청',
      message: `${user.name} · ${user.role === 'lawyer' ? '변호사' : '상담원'} · ${user.email}`,
      target: user.email,
      createdAt: new Date().toISOString(),
      readBy: [],
    }, ...currentNotifications]);
  };

  return (
    <LoadingProvider>
    <FeedbackProvider>
    <div className="app">
      {page === 'dashboard' ? null : <Header onLogin={() => setPage('login')} onRegister={() => setPage('register')} onHome={() => setPage('login')} hideLogin={page === 'login'} />}
      {page === 'login' ? (
        <form id="login-form" onSubmit={handleLogin}>
          <LoginPage
            loginForm={loginForm}
            loginError={loginError}
            rememberId={rememberId}
            onRememberChange={setRememberId}
            onLoginChange={(key, value) => {
              setLoginForm((current) => ({ ...current, [key]: value }));
              setLoginError('');
            }}
            onRegister={() => setPage('register')}
            onForgotPassword={() => setPage('password')}
            onQuickLogin={handleQuickLogin}
            consultations={readStorage(storageKeys.consultations, initialConsultations)}
          />
        </form>
      ) : null}
      {page === 'register' ? (
        <RegisterPage
          onBack={() => setPage('login')}
          onComplete={(user) => {
          // 상담원/변호사는 '대기' 상태로 가입되어 관리자 승인 전까지 로그인할 수 없고,
          // 관리자는 승인 절차 없이 즉시 사용 가능하도록(초기 관리자 부트스트랩 문제 방지) '승인'으로 등록합니다.
          const registeredUser = { ...user, status: user.role === 'admin' ? '승인' : '대기', requestedAt: today };
          const nextUsers = [registeredUser, ...users.filter((item) => item.email !== user.email)];
          setUsers(nextUsers);
          setRegisteredRole(user.role);
          setLoginForm({ email: user.email, password: '' });
          setLoginError('');
          writeStorage(storageKeys.users, nextUsers);
          window.localStorage.setItem('registeredUsers', JSON.stringify(nextUsers));
          window.localStorage.setItem('registeredRole', user.role);
          appendAuditLog({ actor: user.email, action: '회원가입 신청', target: user.role, metadata: { name: user.name, email: user.email, organization: user.organization, role: user.role } });
          notifyAdminRegistrationRequest(registeredUser);
          setPage('login');
        }} />
      ) : null}
      {page === 'password' ? <PasswordFindPage users={users} onBack={() => setPage('login')} /> : null}
      {page === 'dashboard' ? <DashboardPage role={registeredRole} currentUser={currentUser} onUpdateProfile={updateProfile} onLogout={() => { appendAuditLog({ actor: currentUser?.email || '사용자', action: '로그아웃', target: registeredRole }); setPage('login'); }} users={users} onUpdateUserStatus={updateUserStatus} /> : null}
      {page === 'dashboard' ? null : <Footer />}
    </div>
    </FeedbackProvider>
    </LoadingProvider>
  );
}

export default App;
