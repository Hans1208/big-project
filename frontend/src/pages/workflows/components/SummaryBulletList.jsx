import React from 'react';
import { splitSummaryIntoBullets } from '../shared/analysisHelpers.js';

export function SummaryBulletList({ text, emptyText = '요약 없음', maxItems }) {
  const bullets = splitSummaryIntoBullets(text);
  if (!bullets.length) return <p>{emptyText}</p>;
  const visibleBullets = maxItems ? bullets.slice(0, maxItems) : bullets;
  // 문장이 하나뿐이면 목록으로 쪼갤 이유가 없어(오히려 산만해 보임) 마커 없는 한 줄로 둡니다.
  const isSingleLine = visibleBullets.length === 1;
  return (
    <ul className={`summaryBulletList${isSingleLine ? ' singleLine' : ''}`}>
      {visibleBullets.map((sentence, index) => <li key={`${index}-${sentence.slice(0, 12)}`}>{sentence}</li>)}
    </ul>
  );
}
