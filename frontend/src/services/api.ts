import axios from 'axios';

// Unified Backend Service (Port 8000)
export const faceApi = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000, // Increased for AI processing
});

export const whisperApi = faceApi; // They share the same base now

