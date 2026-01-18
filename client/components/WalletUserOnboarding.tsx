import { useState } from 'react';
import { formatWalletAddress, copyToClipboard } from '@/utils/wallet';

interface WalletUserOnboardingProps {
  user: {
    evmAddress: string | null;
    displayName: string | null;
  };
  onComplete: () => void;
}

export function WalletUserOnboarding({ user, onComplete }: WalletUserOnboardingProps) {
  const [displayName, setDisplayName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  // Only show if wallet user and no display name
  if (!user.evmAddress || user.displayName) {
    return null;
  }

  async function handleContinue() {
    const trimmed = displayName.trim();

    if (trimmed.length === 0) {
      setError('Display name is required');
      return;
    }

    if (trimmed.length > 50) {
      setError('Display name must be 50 characters or less');
      return;
    }

    setIsSaving(true);
    setError('');

    try {
      const response = await fetch('/api/user/display-name', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ displayName: trimmed }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to set display name');
      }

      onComplete();
    } catch (err) {
      setError(err.message || 'Failed to set display name');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSkip() {
    // Allow skipping, but show wallet address as display name
    onComplete();
  }

  async function handleCopyWallet() {
    if (!user.evmAddress) return;
    await copyToClipboard(user.evmAddress);
  }

  return (
    <div className="onboarding-modal-overlay">
      <div className="onboarding-modal">
        <h2>Welcome! 👋</h2>
        <p>Set your display name to personalize your profile</p>

        <div className="wallet-info">
          <span className="wallet-label">Your wallet:</span>
          <span
            className="wallet-address"
            onClick={handleCopyWallet}
            title="Click to copy full address"
          >
            {formatWalletAddress(user.evmAddress)}
          </span>
        </div>

        <div className="input-group">
          <label htmlFor="display-name">Display Name</label>
          <input
            id="display-name"
            type="text"
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
              setError('');
            }}
            placeholder="Enter your display name"
            maxLength={50}
            autoFocus
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleContinue();
              }
            }}
          />
          <div className="input-hint">
            1-50 characters (letters, numbers, spaces, hyphens, underscores)
          </div>
          {error && <div className="error-message">{error}</div>}
        </div>

        <div className="modal-actions">
          <button
            onClick={handleContinue}
            disabled={isSaving || displayName.trim().length === 0}
            className="btn-primary"
          >
            {isSaving ? 'Saving...' : 'Continue'}
          </button>
          <button
            onClick={handleSkip}
            className="btn-secondary"
          >
            Skip for now
          </button>
        </div>
      </div>
    </div>
  );
}