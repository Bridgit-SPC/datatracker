export function formatWalletAddress(address: string | null): string {
  if (!address) return 'No wallet';
  if (address.length <= 10) return address;
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

export function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text).then(() => true).catch(() => false);
  }
  // Fallback for older browsers
  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.style.position = 'fixed';
  textArea.style.opacity = '0';
  document.body.appendChild(textArea);
  textArea.select();
  try {
    document.execCommand('copy');
    document.body.removeChild(textArea);
    return Promise.resolve(true);
  } catch (err) {
    document.body.removeChild(textArea);
    return Promise.resolve(false);
  }
}