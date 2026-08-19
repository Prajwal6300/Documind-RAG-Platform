import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';

export default function ContactSupportModal() {
  const { isSupportModalOpen, setIsSupportModalOpen, userSettings, addToast } = useApp();
  const [subject, setSubject] = useState('');
  const [category, setCategory] = useState('Workspace Architecture');
  const [message, setMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isSupportModalOpen) return null;

  const handleClose = () => {
    setIsSupportModalOpen(false);
    setSubject('');
    setMessage('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!subject.trim() || !message.trim()) {
      addToast("Please provide both a subject and an inquiry message.", "error");
      return;
    }

    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      addToast("Support ticket dispatched. A specialist will reply within 24 hours.", "success");
      handleClose();
    }, 600);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-margin-mobile md:p-margin-desktop bg-canvas/70 backdrop-blur-sm animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="support-modal-title"
    >
      <div className="bg-card-surface border border-outline/20 rounded-2xl w-full max-w-lg modal-shadow relative overflow-hidden flex flex-col shadow-2xl animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-5 border-b border-outline/10 flex justify-between items-center bg-card-surface">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-coral-accent">forum</span>
            <h2 id="support-modal-title" className="text-on-surface font-headline-md text-headline-md font-semibold">
              Contact Technical Support
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="text-secondary hover:text-coral-accent transition-colors p-1 rounded-full hover:bg-surface-variant/50"
            aria-label="Close modal"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-4">
          <p className="text-body-md text-muted-text text-sm">
            Need guidance regarding document chunking, prompt engineering, or vector indexing limits? Submit your request below.
          </p>

          <div>
            <label className="block text-label-sm font-semibold text-on-surface mb-1 uppercase tracking-wider">
              Topic / Category
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full h-11 px-3.5 bg-canvas border border-outline/20 rounded-lg text-body-md text-on-surface focus:outline-none focus:border-coral-accent focus:ring-1 focus:ring-coral-accent/50"
            >
              <option value="Workspace Architecture">Workspace Architecture</option>
              <option value="RAG Embedding & Retrieval">RAG Embedding & Retrieval</option>
              <option value="Billing & Premium Plan">Billing & Premium Plan</option>
              <option value="API & Integration">API & Custom Integrations</option>
            </select>
          </div>

          <div>
            <label className="block text-label-sm font-semibold text-on-surface mb-1 uppercase tracking-wider">
              Subject
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Inquiring about custom vector dimensions"
              className="w-full h-11 px-3.5 bg-canvas border border-outline/20 rounded-lg text-body-md text-on-surface placeholder:text-muted-text focus:outline-none focus:border-coral-accent focus:ring-1 focus:ring-coral-accent/50"
            />
          </div>

          <div>
            <label className="block text-label-sm font-semibold text-on-surface mb-1 uppercase tracking-wider">
              Inquiry Message
            </label>
            <textarea
              rows={4}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe the issue or architectural requirement..."
              className="w-full p-3.5 bg-canvas border border-outline/20 rounded-lg text-body-md text-on-surface placeholder:text-muted-text focus:outline-none focus:border-coral-accent focus:ring-1 focus:ring-coral-accent/50 resize-none"
            />
          </div>

          {/* Footer Actions */}
          <div className="mt-2 pt-4 border-t border-outline/10 flex justify-end items-center gap-3">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 rounded-lg text-secondary font-label-md hover:bg-outline/10 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 rounded-lg bg-coral-accent text-white font-label-md hover:bg-primary transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[18px]">send</span>
              <span>{isSubmitting ? 'Sending...' : 'Send Message'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
