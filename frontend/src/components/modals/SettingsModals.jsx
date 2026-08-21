import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';

export function UpdateEmailModal({ isOpen, onClose }) {
  const { userSettings, updateUserSettings, addToast } = useApp();
  const [email, setEmail] = useState(userSettings.email);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = email.trim();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
    if (!emailRegex.test(trimmed)) {
      addToast("Please enter a valid email address.", "error");
      return;
    }
    try {
      await updateUserSettings({ email: trimmed });
      onClose();
    } catch {
      // Toast is emitted by updateUserSettings.
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-canvas/70 backdrop-blur-sm animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-card-surface border border-outline/20 rounded-2xl w-full max-w-md modal-shadow p-6 shadow-2xl animate-in zoom-in-95 duration-200">
        <h3 className="font-headline-md text-headline-md text-on-surface mb-2">Update Email Address</h3>
        <p className="text-body-md text-muted-text text-sm mb-4">
          All workspace notifications and security alerts will be directed to this address.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full h-11 px-3.5 bg-canvas border border-outline/20 rounded-lg text-body-md text-on-surface focus:outline-none focus:border-coral-accent focus:ring-1 focus:ring-coral-accent/50"
            placeholder="name@domain.com"
          />
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-secondary font-label-md hover:bg-outline/10 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-lg bg-coral-accent text-white font-label-md hover:bg-primary transition-colors shadow-sm"
            >
              Save Email
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function DeleteWorkspaceModal({ isOpen, onClose }) {
  const { addToast } = useApp();
  const [confirmationText, setConfirmationText] = useState('');

  if (!isOpen) return null;

  const handleDelete = () => {
    if (confirmationText.toLowerCase() !== 'delete') {
      addToast('Please type "DELETE" to confirm.', 'error');
      return;
    }
    addToast('Workspace deletion is not enabled in this deployment. No backend deletion request was sent.', 'info');
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-canvas/70 backdrop-blur-sm animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-card-surface border border-error/30 rounded-2xl w-full max-w-md modal-shadow p-6 shadow-2xl animate-in zoom-in-95 duration-200">
        <div className="flex items-center gap-2 text-error mb-2">
          <span className="material-symbols-outlined">warning</span>
          <h3 className="font-headline-md text-headline-md">Delete Workspace</h3>
        </div>
        <p className="text-body-md text-muted-text text-sm mb-4">
          This will permanently remove all indexed files, embeddings, and chat history. Type <strong className="text-error">DELETE</strong> below to proceed:
        </p>
        <input
          type="text"
          value={confirmationText}
          onChange={(e) => setConfirmationText(e.target.value)}
          className="w-full h-11 px-3.5 bg-canvas border border-outline/20 rounded-lg text-body-md text-on-surface focus:outline-none focus:border-error focus:ring-1 focus:ring-error/50 mb-4"
          placeholder="Type DELETE"
        />
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-secondary font-label-md hover:bg-outline/10 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDelete}
            className="px-5 py-2 rounded-lg bg-error text-white font-label-md hover:opacity-90 transition-opacity shadow-sm"
          >
            Permanently Delete
          </button>
        </div>
      </div>
    </div>
  );
}
