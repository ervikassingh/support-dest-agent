import { HttpException, Injectable, Logger, ServiceUnavailableException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

export type ChatRequest = {
  message: string;
  threadId?: string | null;
};

export type ChatResponse = {
  reply: string;
  threadId: string;
  status: string;
};

export type ApprovalRequest = {
  decision: 'approve' | 'edit' | 'reject';
  amount?: number;
  note?: string;
};

@Injectable()
export class AgentClientService {
  private readonly logger = new Logger(AgentClientService.name);

  constructor(private readonly config: ConfigService) {}

  private get baseUrl(): string {
    return this.config.get<string>('AGENT_URL') ?? 'http://localhost:8000';
  }

  async chat(body: ChatRequest): Promise<ChatResponse> {
    return this.postJson<ChatResponse>('/chat', body);
  }

  async resume(threadId: string, body: ApprovalRequest) {
    return this.postJson(`/threads/${encodeURIComponent(threadId)}/resume`, body);
  }

  async getJson<T>(path: string): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    let res: Response;
    try {
      res = await fetch(url);
    } catch (error) {
      this.logger.error(`Agent unreachable at ${url}`, error instanceof Error ? error.stack : undefined);
      throw new ServiceUnavailableException(
        `Agent unreachable at ${this.baseUrl}. Start apps/agent on :8000.`,
      );
    }
    if (!res.ok) {
      throw new HttpException(this.detail(await res.text()) || `Agent error ${res.status}`, res.status);
    }
    return (await res.json()) as T;
  }

  private detail(text: string): string {
    try {
      const detail = (JSON.parse(text) as { detail?: unknown }).detail ?? text;
      return typeof detail === 'string' ? detail : JSON.stringify(detail);
    } catch {
      return text;
    }
  }

  private async postJson<T>(path: string, body: unknown): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const text = await res.text();
        this.logger.warn(`Agent ${path} failed: ${res.status} ${text}`);
        if (res.status >= 400 && res.status < 500) {
          throw new HttpException(this.detail(text) || `Agent error ${res.status}`, res.status);
        }
        throw new ServiceUnavailableException(`Agent error ${res.status}`);
      }

      return (await res.json()) as T;
    } catch (error) {
      if (error instanceof HttpException) {
        throw error;
      }
      this.logger.error(`Agent unreachable at ${url}`, error instanceof Error ? error.stack : undefined);
      throw new ServiceUnavailableException(
        `Agent unreachable at ${this.baseUrl}. Start apps/agent on :8000.`,
      );
    }
  }
}
