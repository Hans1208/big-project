import React, { useState } from 'react';
import { ChevronDown, Search } from 'lucide-react';

function normalizeChoiceOptions(options) {
  return options.map((option) => (typeof option === 'string' ? { value: option, label: option } : option));
}

function matchesChoiceQuery(option, query) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return true;
  return [option.label, option.description].filter(Boolean).some((field) => String(field).toLowerCase().includes(normalizedQuery));
}

export function ChoicePicker({ options, value, onChange, placeholder = '선택하세요', disabled = false }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const normalizedOptions = normalizeChoiceOptions(options);
  const selected = normalizedOptions.find((option) => String(option.value) === String(value));
  const filteredOptions = normalizedOptions.filter((option) => matchesChoiceQuery(option, query));

  const selectOption = (option) => {
    onChange(option.value);
    setQuery('');
    setOpen(false);
  };

  return (
    <div className="choicePicker">
      <button
        className="choicePickerButton"
        type="button"
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <span className="choicePickerText">
          <strong>{selected?.label || placeholder}</strong>
          {selected?.description ? <small>{selected.description}</small> : null}
        </span>
        <ChevronDown size={18} strokeWidth={2.2} aria-hidden="true" />
      </button>
      {open && !disabled ? (
        <div className="choicePickerPopover">
          <label className="choicePickerSearch">
            <Search size={15} strokeWidth={2.2} aria-hidden="true" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="항목 검색"
            />
          </label>
          <div className="choicePickerList">
            {filteredOptions.length ? filteredOptions.map((option) => (
              <button
                className={String(option.value) === String(value) ? 'choicePickerItem active' : 'choicePickerItem'}
                type="button"
                key={option.value}
                onClick={() => selectOption(option)}
              >
                <strong>{option.label}</strong>
                {option.description ? <small>{option.description}</small> : null}
              </button>
            )) : (
              <p className="choicePickerEmpty">검색 결과 없음</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
