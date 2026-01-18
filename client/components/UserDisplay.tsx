import { useState } from 'react';
import { formatWalletAddress, copyToClipboard } from '@/utils/wallet';

interface UserDisplayProps {
  user: {
    displayName: string | null;
    oauthName: string | null;
    evmAddress: string | null;
    typeOfLogin: string;
  };
  editable?: boolean;
  onUpdate?: () => void;
}

export function UserDisplay({ user, editable = false, onUpdate }: UserDisplayProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [displayName, setDisplayName] = useState(user.displayName || '');
  const [isSaving, setIsSaving] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');

  // Determine display text (priority: displayName > oauthName > wallet address)
  const displayText = user.displayName || user.oauthName || formatWalletAddress(user.evmAddress);
  const showWallet = user.evmAddress;
  const needsDisplayName = !user.displayName && user.typeOfLogin === 'wallet';

  async function handleSave() {
    const trimmed = displayName.trim();

    if (trimmed.length === 0) {
      setToastMessage('Display name cannot be empty');
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
      return;
    }

    if (trimmed.length > 50) {
      setToastMessage('Display name must be 50 characters or less');
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
      return;
    }

    setIsSaving(true);

    try {
      const response = await fetch('/api/user/display-name', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ displayName: trimmed }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to update display name');
      }

      setIsEditing(false);
      if (onUpdate) onUpdate();
      setToastMessage('Display name updated!');
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
    } catch (error) {
      setToastMessage(error.message || 'Failed to update display name');
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCopyWallet() {
    if (!user.evmAddress) return;

    const copied = await copyToClipboard(user.evmAddress);
    if (copied) {
      setToastMessage('Wallet address copied!');
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
    }
  }

  if (isEditing && editable) {
    return (
      <div className="user-display-edit">
        <input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Enter display name"
          maxLength={50}
          className="display-name-input"
          autoFocus
        />
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="btn-save"
        >
          {isSaving ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={() => {
            setIsEditing(false);
            setDisplayName(user.displayName || '');
          }}
          className="btn-cancel"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="user-display">
      <span className="display-name">{displayText}</span>
      {showWallet && (
        <span
          className="wallet-badge"
          onClick={handleCopyWallet}
          title={`Click to copy: ${user.evmAddress}`}
        >
          {formatWalletAddress(user.evmAddress)}
        </span>
      )}
      {editable && (
        <button
          onClick={() => setIsEditing(true)}
          className="btn-edit"
          aria-label="Edit display name"
        >
          Edit
        </button>
      )}
      {showToast && (
        <div className="toast">
          {toastMessage}
        </div>
      )}
    </div>
  );
}