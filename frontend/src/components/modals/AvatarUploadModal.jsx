import React, { useState, useRef } from 'react';
import { useApp } from '../../context/AppContext';

export default function AvatarUploadModal() {
  const {
    isAvatarModalOpen,
    setIsAvatarModalOpen,
    userSettings,
    updateUserSettings,
    addToast
  } = useApp();

  const [zoom, setZoom] = useState(userSettings.avatarZoom || 110);
  const [previewUrl, setPreviewUrl] = useState(userSettings.avatarUrl);
  const [position, setPosition] = useState(userSettings.avatarPos || { x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const fileInputRef = useRef(null);

  if (!isAvatarModalOpen) return null;

  const handleClose = () => {
    setIsAvatarModalOpen(false);
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        addToast("Image exceeds 5MB limit. Please choose a smaller photo.", "error");
        return;
      }
      const reader = new FileReader();
      reader.onload = (uploadEvent) => {
        setPreviewUrl(uploadEvent.target.result);
        addToast("New photo loaded. Adjust zoom and position.", "info");
      };
      reader.readAsDataURL(file);
    }
  };

  const handleMouseDown = (e) => {
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX - position.x,
      y: e.clientY - position.y
    };
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleSave = async () => {
    try {
      await updateUserSettings({
        avatarUrl: previewUrl,
        avatarZoom: zoom,
        avatarPos: position
      });
      handleClose();
    } catch {
      // Toast is emitted by updateUserSettings.
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-margin-mobile md:p-margin-desktop bg-canvas/70 backdrop-blur-sm animate-in fade-in duration-200"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="bg-card-surface border border-outline/20 rounded-2xl w-full max-w-lg modal-shadow relative overflow-hidden flex flex-col shadow-2xl animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-5 border-b border-outline/10 flex justify-between items-center bg-card-surface">
          <button
            onClick={handleClose}
            className="text-secondary hover:text-coral-accent transition-colors flex items-center gap-1 p-1 -ml-1 rounded-lg hover:bg-surface-variant/50 group text-sm font-label-md"
            aria-label="Cancel and close modal"
          >
            <span className="material-symbols-outlined text-[20px]">arrow_back</span>
            <span>Back</span>
          </button>

          <h2
            id="modal-title"
            className="text-on-surface font-headline-md text-headline-md font-cormorant font-semibold tracking-tight"
          >
            Update Profile Photo
          </h2>

          <button
            onClick={handleClose}
            className="text-secondary hover:text-coral-accent transition-colors flex items-center justify-center p-1 rounded-full hover:bg-surface-variant/50"
            aria-label="Close modal"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 flex flex-col gap-6 items-center">
          {/* Circular Cropper Viewport */}
          <div
            className="relative w-48 h-48 rounded-full overflow-hidden border-2 border-dashed border-outline/40 shadow-inner group cursor-grab active:cursor-grabbing bg-surface select-none"
            onMouseDown={handleMouseDown}
          >
            {/* Image Container with live scaling & dragging */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <img
                src={previewUrl || '/DocuMind_Logo_4K.png'}
                alt="Avatar preview"
                className="w-full h-full object-cover transition-transform duration-75 select-none"
                style={{
                  transform: `scale(${zoom / 100}) translate(${position.x}px, ${position.y}px)`,
                }}
                draggable={false}
              />
            </div>

            {/* 3x3 Overlay Grid for Alignment */}
            <div className="absolute inset-0 grid grid-cols-3 grid-rows-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
              <div className="border-b border-r border-on-surface/20"></div>
              <div className="border-b border-r border-on-surface/20"></div>
              <div className="border-b border-on-surface/20"></div>
              <div className="border-b border-r border-on-surface/20"></div>
              <div className="border-b border-r border-on-surface/20"></div>
              <div className="border-b border-on-surface/20"></div>
              <div className="border-r border-on-surface/20"></div>
              <div className="border-r border-on-surface/20"></div>
              <div></div>
            </div>
          </div>

          <p className="text-muted-text text-body-md font-body-md text-center max-w-[280px]">
            Drag inside the frame to reposition or adjust the zoom slider below.
          </p>

          {/* Zoom Slider Control */}
          <div className="flex items-center w-full max-w-[260px] gap-3">
            <span className="material-symbols-outlined text-muted-text text-[18px]">
              image
            </span>
            <input
              type="range"
              min="100"
              max="200"
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
              aria-label="Image zoom level"
              className="w-full h-1.5 bg-outline/20 rounded-lg appearance-none cursor-pointer accent-coral-accent focus:outline-none focus:ring-2 focus:ring-coral-accent/30"
            />
            <span className="material-symbols-outlined text-muted-text text-[24px]">
              image
            </span>
            <span className="text-xs font-mono text-muted-text w-10 text-right">
              {zoom}%
            </span>
          </div>

          {/* Upload New Image File Dropzone Button */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="image/png, image/jpeg, image/gif, image/webp"
            className="hidden"
            id="avatar-file-input"
          />

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-full py-4 px-6 rounded-xl border border-dashed border-outline/40 
                       bg-surface/50 hover:bg-surface text-secondary hover:text-on-surface 
                       transition-colors flex flex-col items-center justify-center gap-1.5 group cursor-pointer"
          >
            <span className="material-symbols-outlined text-muted-text group-hover:text-coral-accent text-[26px] transition-colors">
              cloud_upload
            </span>
            <span className="font-label-md text-label-md text-on-surface">
              Upload a different image
            </span>
            <span className="text-label-sm font-label-sm text-muted-text">
              PNG, JPG or GIF (max. 5MB)
            </span>
          </button>
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 bg-surface-container-low border-t border-outline/10 flex justify-end items-center gap-3">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 rounded-lg text-secondary font-label-md text-label-md hover:bg-outline/10 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="px-5 py-2 rounded-lg bg-coral-accent text-on-primary font-label-md text-label-md hover:bg-primary transition-colors shadow-sm flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-[18px]">check</span>
            <span>Save Photo</span>
          </button>
        </div>
      </div>
    </div>
  );
}
