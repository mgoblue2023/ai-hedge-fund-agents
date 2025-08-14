// app/frontend/src/lib/api.ts
export const API_BASE =
  (import.meta as any)?.env?.VITE_API_BASE ||
  (window as any)?.VITE_API_BASE ||
  'https://ai-hedge-fund-agents-1.onrender.com'; // fallback; change if needed

export function apiUrl(path: string) {
  return `${API_BASE}${path}`;
}
