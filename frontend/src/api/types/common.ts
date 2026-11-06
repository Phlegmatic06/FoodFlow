/**
 * Shared API Types and Error Interfaces conforming to FoodFlow OpenAPI specifications.
 */

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown> | Array<unknown> | null;
  request_id?: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export class ApiError extends Error {
  public readonly code: string;
  public readonly statusCode: number;
  public readonly details?: Record<string, unknown> | Array<unknown> | null;
  public readonly requestId?: string;

  constructor(
    message: string,
    statusCode: number,
    code: string = 'API_ERROR',
    details?: Record<string, unknown> | Array<unknown> | null,
    requestId?: string
  ) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

export interface ServiceHealthStatus {
  status: 'healthy' | 'unhealthy' | 'degraded';
  service: string;
  timestamp: string;
  version?: string;
}

export interface DatabaseReadinessInfo {
  connected: boolean;
  role: string;
  database: string;
  server_version: string;
  pool_min: number;
  pool_max: number;
  response_time_ms: number;
}

export interface ServiceReadinessStatus {
  status: 'ready' | 'not_ready';
  service: string;
  timestamp: string;
  database?: DatabaseReadinessInfo;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

