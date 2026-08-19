import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import ToggleSwitch from '../components/common/ToggleSwitch';
import { UpdateEmailModal, DeleteWorkspaceModal } from '../components/modals/SettingsModals';

export default function SettingsPage() {
  const navigate = useNavigate();
  const {
    userSettings,
    setIsAvatarModalOpen,
    toggleNotification,
    togglePrivacy,
    addToast
  } = useApp();

  const [isEmailModalOpen, setIsEmailModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const handleManagePlan = () => {
    addToast("Subscription tier: Premium (Annual). Enterprise invoice downloaded.", "info");
  };

  return (
    <div className="flex-1 px-margin-mobile md:px-margin-desktop py-10 max-w-content-max-width mx-auto w-full flex flex-col min-h-[calc(100vh-4rem)]">
      {/* Header */}
      <header className="mb-10">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 text-muted-text hover:text-on-surface transition-colors mb-4 group font-label-md text-sm"
        >
          <span className="material-symbols-outlined text-[20px] transition-transform group-hover:-translate-x-1">
            arrow_back
          </span>
          <span>Back</span>
        </button>
        <h1 className="font-headline-lg text-headline-lg text-on-surface mb-2 font-semibold tracking-tight">
          Workspace Settings
        </h1>
        <p className="font-body-lg text-body-lg text-muted-text max-w-2xl">
          Manage your preferences, account details, and notification settings for your premium workspace.
        </p>
      </header>

      {/* Settings Sections */}
      <div className="space-y-10">
        {/* Account Section */}
        <section>
          <h2 className="font-headline-md text-headline-md text-on-surface mb-4 border-b border-outline-variant/30 pb-2 flex items-center gap-2.5 font-medium">
            <span className="material-symbols-outlined text-coral-accent">account_circle</span>
            <span>Account</span>
          </h2>
          <div className="bg-card-surface rounded-2xl border border-outline-variant/30 overflow-hidden divide-y divide-outline-variant/20 shadow-xs">
            {/* Profile Setting */}
            <div className="p-6 flex flex-col sm:flex-row gap-6 items-start sm:items-center justify-between hover:bg-surface-container-highest/60 transition-colors">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-full bg-surface-container border border-outline-variant overflow-hidden shrink-0 shadow-xs">
                  <img
                    src={userSettings.avatarUrl}
                    alt="Profile"
                    className="w-full h-full object-cover"
                    style={{
                      transform: `scale(${userSettings.avatarZoom / 100})`,
                    }}
                  />
                </div>
                <div>
                  <h3 className="font-label-md text-label-md text-on-surface font-semibold">
                    Profile Photo
                  </h3>
                  <p className="font-body-md text-muted-text text-sm mt-0.5">
                    Update your public workspace identity image.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsAvatarModalOpen(true)}
                className="px-4 py-2 bg-surface text-on-surface font-label-md text-sm border border-outline/30 rounded-xl hover:bg-surface-variant hover:border-coral-accent/50 transition-colors cursor-pointer"
              >
                Change Photo
              </button>
            </div>

            {/* Email Setting */}
            <div className="p-6 flex flex-col sm:flex-row gap-6 items-start sm:items-center justify-between hover:bg-surface-container-highest/60 transition-colors">
              <div>
                <h3 className="font-label-md text-label-md text-on-surface font-semibold">
                  Email Address
                </h3>
                <p className="font-body-md text-muted-text text-sm mb-1 mt-0.5">
                  Your current active email is <strong className="text-on-surface">{userSettings.email}</strong>
                </p>
              </div>
              <button
                onClick={() => setIsEmailModalOpen(true)}
                className="px-4 py-2 bg-surface text-on-surface font-label-md text-sm border border-outline/30 rounded-xl hover:bg-surface-variant hover:border-coral-accent/50 transition-colors whitespace-nowrap cursor-pointer"
              >
                Update Email
              </button>
            </div>

            {/* Subscription */}
            <div className="p-6 flex flex-col sm:flex-row gap-6 items-start sm:items-center justify-between hover:bg-surface-container-highest/60 transition-colors">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-label-md text-label-md text-on-surface font-semibold">
                    Subscription Plan
                  </h3>
                  <span className="bg-coral-accent/15 text-coral-accent px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider">
                    {userSettings.plan}
                  </span>
                </div>
                <p className="font-body-md text-muted-text text-sm">
                  Billed annually. Next billing date is <strong className="text-on-surface">{userSettings.nextBilling}</strong>.
                </p>
              </div>
              <button
                onClick={handleManagePlan}
                className="px-4 py-2 text-coral-accent font-label-md text-sm hover:underline transition-all cursor-pointer"
              >
                Manage Plan
              </button>
            </div>
          </div>
        </section>

        {/* Notifications Section */}
        <section>
          <h2 className="font-headline-md text-headline-md text-on-surface mb-4 border-b border-outline-variant/30 pb-2 flex items-center gap-2.5 font-medium">
            <span className="material-symbols-outlined text-coral-accent">notifications</span>
            <span>Notifications</span>
          </h2>
          <div className="bg-card-surface rounded-2xl border border-outline-variant/30 overflow-hidden divide-y divide-outline-variant/20 shadow-xs">
            {/* Email Alerts */}
            <div className="p-6 flex flex-col sm:flex-row gap-6 items-start sm:items-center justify-between hover:bg-surface-container-highest/60 transition-colors">
              <div>
                <h3 className="font-label-md text-label-md text-on-surface font-semibold">
                  Document Summaries
                </h3>
                <p className="font-body-md text-muted-text text-sm mt-0.5">
                  Receive email digests when large documents finish processing.
                </p>
              </div>
              <ToggleSwitch
                id="toggle-doc-summaries"
                checked={userSettings.notifications.documentSummaries}
                onChange={() => toggleNotification('documentSummaries')}
                ariaLabel="Toggle document summaries notifications"
              />
            </div>

            {/* Product Updates */}
            <div className="p-6 flex flex-col sm:flex-row gap-6 items-start sm:items-center justify-between hover:bg-surface-container-highest/60 transition-colors">
              <div>
                <h3 className="font-label-md text-label-md text-on-surface font-semibold">
                  Product Updates
                </h3>
                <p className="font-body-md text-muted-text text-sm mt-0.5">
                  Occasional news about new AI models and feature releases.
                </p>
              </div>
              <ToggleSwitch
                id="toggle-product-updates"
                checked={userSettings.notifications.productUpdates}
                onChange={() => toggleNotification('productUpdates')}
                ariaLabel="Toggle product updates notifications"
              />
            </div>
          </div>
        </section>

        {/* Privacy & Data Section */}
        <section>
          <h2 className="font-headline-md text-headline-md text-on-surface mb-4 border-b border-outline-variant/30 pb-2 flex items-center gap-2.5 font-medium">
            <span className="material-symbols-outlined text-coral-accent">lock</span>
            <span>Privacy & Data</span>
          </h2>
          <div className="bg-card-surface rounded-2xl border border-outline-variant/30 overflow-hidden divide-y divide-outline-variant/20 shadow-xs">
            {/* AI Training */}
            <div className="p-6 flex flex-col sm:flex-row gap-6 items-start sm:items-center justify-between hover:bg-surface-container-highest/60 transition-colors">
              <div className="max-w-xl">
                <h3 className="font-label-md text-label-md text-on-surface font-semibold">
                  Model Improvement
                </h3>
                <p className="font-body-md text-muted-text text-sm mt-0.5">
                  Allow DocuMind to use anonymized document snippets to improve general AI capabilities. <em>Premium workspaces are opted-out by default.</em>
                </p>
              </div>
              <ToggleSwitch
                id="toggle-ai-training"
                checked={userSettings.privacy.aiTraining}
                onChange={() => togglePrivacy('aiTraining')}
                ariaLabel="Toggle AI training permission"
              />
            </div>

            {/* Delete Account */}
            <div className="p-6 flex flex-col sm:flex-row gap-6 items-start sm:items-center justify-between hover:bg-error-container/20 transition-colors">
              <div>
                <h3 className="font-label-md text-label-md text-error font-semibold">
                  Delete Workspace
                </h3>
                <p className="font-body-md text-muted-text text-sm mt-0.5">
                  Permanently remove your account and all indexed documents.
                </p>
              </div>
              <button
                onClick={() => setIsDeleteModalOpen(true)}
                className="px-4 py-2 text-error font-label-md text-sm border border-error/30 rounded-xl hover:bg-error/10 transition-colors whitespace-nowrap cursor-pointer"
              >
                Delete Workspace...
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* Sub-modals for Settings */}
      <UpdateEmailModal
        isOpen={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
      />
      <DeleteWorkspaceModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
      />
    </div>
  );
}
