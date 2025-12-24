import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
    // Za sada stalno koristimo demo tenant.
    "X-Tenant-Code": "t-demo",
  },
});

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}
