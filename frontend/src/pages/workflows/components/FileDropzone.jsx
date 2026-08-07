import React, { useState } from 'react';
import { FileCheck2, IdCard, Mic } from 'lucide-react';
import { useToast } from '../../../components/feedback.jsx';
import { uploadCategoryOptions, uploadCategoryAccept, fileMatchesCategory } from '../shared/attachmentHelpers.js';

const uploadCategoryIcons = {
  '녹취록': Mic,
  '신분증': IdCard,
  '증빙자료': FileCheck2,
};

export function FileDropzone({ category, onCategoryChange, onAddFiles }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [fileError, setFileError] = useState('');
  const inputId = React.useId();
  const showToast = useToast();
  const handleFiles = (fileList) => {
    if (!fileList || !fileList.length) return;
    // accept 속성은 파일 선택창만 걸러줍니다. 드래그앤드롭으로 들어온 파일은 그대로 통과하므로
    // 여기서 한 번 더 확인합니다.
    const files = Array.from(fileList);
    const accepted = files.filter((file) => fileMatchesCategory(file, category));
    const rejected = files.filter((file) => !fileMatchesCategory(file, category));
    if (rejected.length) {
      showToast(
        `${category}에는 ${uploadCategoryAccept[category]} 파일만 올릴 수 있습니다 (제외: ${rejected.map((file) => file.name).join(', ')})`,
        'warn',
      );
      setFileError(`${category}에는 허용된 파일 형식만 추가할 수 있습니다.`);
    }
    if (accepted.length) onAddFiles(category, accepted);
  };
  return (
    <div
      className={isDragOver ? 'fileDropzone dragOver' : 'fileDropzone'}
      onDragOver={(event) => { event.preventDefault(); setIsDragOver(true); }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragOver(false);
        handleFiles(event.dataTransfer.files);
      }}
      >
      <div className="fileDropzoneCopy">
        <strong>자료 유형을 선택한 뒤 파일을 추가하세요.</strong>
      </div>
      <div className="fileDropzoneControls">
        <div className="fileDropzoneStep">
          <div className="fileCategoryChoices" role="group" aria-label="자료 유형 선택">
            {uploadCategoryOptions.map((option) => (
              (() => {
                const CategoryIcon = uploadCategoryIcons[option] || FileCheck2;
                return (
                  <button
                    className={category === option ? 'active' : ''}
                    type="button"
                    key={option}
                    aria-pressed={category === option}
                    onClick={() => { onCategoryChange(option); setFileError(''); }}
                  >
                    <CategoryIcon size={14} strokeWidth={2.2} aria-hidden="true" />
                    {option}
                  </button>
                );
              })()
            ))}
          </div>
        </div>
        <div className="fileDropzoneStep fileDropzonePickStep">
          <label className="fileBtn" htmlFor={inputId}>
            파일 선택
            <input
              id={inputId}
              type="file"
              multiple
              accept={uploadCategoryAccept[category] || ''}
              onChange={(event) => {
                handleFiles(event.target.files);
                event.target.value = '';
              }}
            />
          </label>
        </div>
      </div>
      {fileError ? <p className="fileDropzoneError" role="alert">{fileError}</p> : null}
    </div>
  );
}
