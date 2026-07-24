import { today } from '../constants.jsx';

export const months = Array.from({ length: 12 }, (_, index) => `${index + 1}월`);
export const weekDays = ['일', '월', '화', '수', '목', '금', '토'];

export function toIsoDate(year, month, day) {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

export function getRecentYears() {
  const currentYear = new Date(today).getFullYear();
  return Array.from({ length: 6 }, (_, index) => currentYear - index);
}

export function getDaysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}
