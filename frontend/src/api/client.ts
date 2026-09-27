import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
} from "axios";

/**
 * Base URL of the FastAPI backend.
 *
 * Example .env:
 * VITE_API_BASE_URL=http://localhost:8000
 */
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") ||
  "http://localhost:8000";

export interface ApiErrorPayload {
  detail?: unknown;
  message?: string;
}

export class ApiError extends Error {
  status?: number;
  data?: unknown;

  constructor(
    message: string,
    options?: {
      status?: number;
      data?: unknown;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options?.status;
    this.data = options?.data;
  }
}

function extractErrorMessage(error: AxiosError<ApiErrorPayload>): string {
  const data = error.response?.data;

  if (typeof data?.detail === "string") {
    return data.detail;
  }

  if (
    data?.detail &&
    typeof data.detail === "object"
  ) {
    try {
      return JSON.stringify(data.detail);
    } catch {
      return "The backend returned an error.";
    }
  }

  if (data?.message) {
    return data.message;
  }

  return error.message || "Unexpected API error.";
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15_000,
});

apiClient.interceptors.response.use(
  (response) => response,

  (error: AxiosError<ApiErrorPayload>) => {
    throw new ApiError(
      extractErrorMessage(error),
      {
        status: error.response?.status,
        data: error.response?.data,
      },
    );
  },
);

/**
 * Small generic helper for endpoints that do not need a dedicated function.
 */
export async function apiRequest<T>(
  config: AxiosRequestConfig,
): Promise<T> {
  const response = await apiClient.request<T>(config);
  return response.data;
}
