import React from 'react';
import { Trash2, Bell, BellOff } from 'lucide-react';
import { useConfirm } from '../../../components/feedback.jsx';
import { WorkPageHeader, InlineEmptyNotice } from '../../../components/common.jsx';
import { formatDateTimeLabel } from '../../../utils/date.js';

export function NotificationPanel({ role, currentUser, notifications = [], onReadNotifications, onDeleteNotification, onOpenNotification }) {
  const confirm = useConfirm();
  const notificationKey = `${role}:${currentUser?.email || 'all'}`;
  const roleNotifications = notifications.filter((item) => {
    if (!item.roles?.includes(role)) return false;
    if (item.recipientEmail && item.recipientEmail !== currentUser?.email) return false;
    return !item.deletedBy?.includes(role) && !item.deletedBy?.includes(notificationKey);
  });
  const unreadCount = roleNotifications.filter((item) => !item.readBy?.includes(role) && !item.readBy?.includes(notificationKey)).length;
  const handleDelete = async (event, item, unread) => {
    event.stopPropagation();
    if (unread) {
      const accepted = await confirm({
        title: '읽지 않은 알림을 삭제할까요?',
        message: `「${item.title}」\n읽지 않은 알림이 삭제됩니다.`,
        confirmLabel: '삭제',
        tone: 'danger',
      });
      if (!accepted) return;
    }
    onDeleteNotification?.(item.id, role, currentUser?.email);
  };
  return (
    <section className="workPanel notificationPanel">
      <WorkPageHeader
        title="알림"
        description="새 알림을 확인하고 해당 업무로 바로 이동하세요."
        meta={(
          <span className="notificationHeaderMeta">
            <span className="notificationCount">새 알림 {unreadCount}건</span>
            {/* 알림이 쌓일수록 이 버튼을 찾아 목록 맨 아래까지 내려야 했던 문제를 없애기 위해
                목록 위(헤더 옆)로 옮겼습니다. */}
            <button className="ghostActionButton compactAction" type="button" onClick={() => onReadNotifications?.(role, currentUser?.email)} disabled={!unreadCount}><BellOff size={13} strokeWidth={2.4} aria-hidden="true" /> 전체 읽음 처리</button>
          </span>
        )}
      />
      <div className="utilityContentCard notificationContentCard">
        {roleNotifications.length ? (
          <div className="notificationList">
            {roleNotifications.map((item) => {
              const unread = !item.readBy?.includes(role) && !item.readBy?.includes(notificationKey);
              return (
                <article
                  className={unread ? 'notificationItem unread' : 'notificationItem read'}
                  key={item.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onOpenNotification?.(item)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') onOpenNotification?.(item);
                  }}
                >
                  <div className="notificationItemTop">
                    <strong className="notificationItemTitle">
                      <i className="notificationDot" aria-hidden="true" />
                      {unread ? <Bell size={13} strokeWidth={2.4} aria-hidden="true" /> : <BellOff size={13} strokeWidth={2.2} aria-hidden="true" />}
                      {item.title}
                    </strong>
                    <span className="notificationItemTime">{formatDateTimeLabel(item.createdAt)}</span>
                  </div>
                  <p className="notificationItemMessage">{item.message}</p>
                  <div className="notificationActions">
                    <span className="notificationState">{unread ? '바로 처리 ›' : '내용 보기'}</span>
                    <button className="notificationDelete" type="button" onClick={(event) => handleDelete(event, item, unread)}><Trash2 size={12} strokeWidth={2.4} aria-hidden="true" /> 삭제</button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="notificationEmptyState" role="status">
            <InlineEmptyNotice>새 알림이 없습니다.</InlineEmptyNotice>
            <p>새로운 업무 알림이 도착하면 이곳에서 확인할 수 있습니다.</p>
          </div>
        )}
      </div>
    </section>
  );
}
