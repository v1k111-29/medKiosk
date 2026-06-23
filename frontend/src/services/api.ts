import axios from 'axios';

/**
 * Unified API client for all backend requests.
 *
 * Uses relative base URL so it works on localhost, LAN, and production
 * without hardcoding. Set VITE_API_URL in .env for custom deployments.
 */
const BASE_URL = import.meta.env.VITE_API_URL ?? '';

export const faceApi = axios.create({
  baseURL: BASE_URL,
  timeout: 60000, // 60s — generous for Whisper + Ollama on CPU
});

// Alias for backward compat
export const whisperApi = faceApi;
