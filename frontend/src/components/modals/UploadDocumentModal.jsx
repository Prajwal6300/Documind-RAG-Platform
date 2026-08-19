import React, { useState, useRef } from 'react';
import { useApp } from '../../context/AppContext';

export default function UploadDocumentModal() {
  const { isUploadModalOpen, setIsUploadModalOpen, uploadDocument, addToast } = useApp();
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [docTitle, setDocTitle] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);

  if (!isUploadModalOpen) return null;

  const handleClose = () => {
    if (isUploading) return;
    setIsUploadModalOpen(false);
    setSelectedFile(null);
    setDocTitle('');
  };

  const handleFile = (file) => {
    if (!file) return;
    const name = file.name;
    const ext = name.split('.').pop()?.toLowerCase();
    const allowed = ['pdf', 'docx', 'xlsx', 'txt', 'csv', 'pptx', 'md'];
    if (!allowed.includes(ext)) {
      addToast(`Unsupported file format .${ext}. Please select a PDF, DOCX, XLSX, TXT, CSV, or PPTX file.`, 'error');
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      addToast(`File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds 25MB limit.`, 'error');
      return;
    }
    setSelectedFile(file);
    setDocTitle(name.replace(/\.[^/.]+$/, ''));
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      addToast('Please select a file to upload.', 'error');
      return;
    }

    setIsUploading(true);
    try {
      await uploadDocument(selectedFile, docTitle.trim());
      handleClose();
    } catch (err) {
      addToast(`Upload failed: ${err.message}`, 'error');
    } finally {
      setIsUploading(false);
    }
  };

  const fileExt = selectedFile?.name.split('.').pop()?.toUpperCase() || 'PDF';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-margin-mobile md:p-margin-desktop bg-canvas/70 backdrop-blur-sm animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      <div className="bg-card-surface border border-outline/20 rounded-2xl w-full max-w-lg modal-shadow relative overflow-hidden flex flex-col shadow-2xl animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-5 border-b border-outline/10 flex justify-between items-center bg-card-surface">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-coral-accent">upload_file</span>
            <h2 id="upload-modal-title" className="text-on-surface font-headline-md text-headline-md font-semibold">
              Upload Document
            </h2>
          </div>
          <button
            onClick={handleClose}
            disabled={isUploading}
            className="text-secondary hover:text-coral-accent transition-colors p-1 rounded-full hover:bg-surface-variant/50 disabled:opacity-40"
            aria-label="Close modal"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-5">
          {/* Dropzone Area */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center gap-2 cursor-pointer transition-all duration-200 text-center ${
              dragActive
                ? 'border-coral-accent bg-coral-accent/5 scale-[1.01]'
                : selectedFile
                ? 'border-emerald-500/50 bg-surface/80'
                : 'border-outline/30 bg-surface/50 hover:bg-surface hover:border-outline/50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              onChange={(e) => handleFile(e.target.files?.[0])}
              accept=".pdf,.docx,.xlsx,.txt,.csv,.pptx,.md"
              className="hidden"
            />
            <span
              className={`material-symbols-outlined text-[36px] ${
                selectedFile ? 'text-emerald-600' : 'text-muted-text'
              }`}
            >
              {selectedFile ? 'check_circle' : 'cloud_upload'}
            </span>
            <p className="font-label-md text-on-surface">
              {selectedFile ? (
                <span className="text-coral-accent font-semibold">{selectedFile.name}</span>
              ) : (
                'Drop your PDF, DOCX, XLSX, TXT, or PPTX file here'
              )}
            </p>
            <p className="text-label-sm text-muted-text">
              {selectedFile
                ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • ${fileExt}`
                : 'Files up to 25MB will be indexed into your persistent vector corpus'}
            </p>
          </div>

          {/* Document Title Field */}
          <div>
            <label className="block text-label-sm font-semibold text-on-surface mb-1.5 uppercase tracking-wider">
              Document Display Name
            </label>
            <input
              type="text"
              value={docTitle}
              onChange={(e) => setDocTitle(e.target.value)}
              placeholder="e.g. Q3 Strategic Financial Plan"
              disabled={isUploading}
              className="w-full h-11 px-3.5 bg-canvas border border-outline/20 rounded-lg text-body-md text-on-surface placeholder:text-muted-text focus:outline-none focus:border-coral-accent focus:ring-1 focus:ring-coral-accent/50 disabled:opacity-60"
            />
          </div>

          {/* Footer Actions */}
          <div className="mt-4 pt-4 border-t border-outline/10 flex justify-end items-center gap-3">
            <button
              type="button"
              onClick={handleClose}
              disabled={isUploading}
              className="px-4 py-2 rounded-lg text-secondary font-label-md hover:bg-outline/10 transition-colors disabled:opacity-40"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!selectedFile || isUploading}
              className="px-5 py-2 rounded-lg bg-coral-accent text-white font-label-md hover:bg-primary transition-colors shadow-sm flex items-center gap-2 disabled:opacity-40 disabled:hover:bg-coral-accent cursor-pointer"
            >
              {isUploading ? (
                <>
                  <span className="material-symbols-outlined text-[18px] animate-spin">sync</span>
                  <span>Uploading & Indexing...</span>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-[18px]">add_box</span>
                  <span>Index Document</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
