import {
  BadRequestException,
  HttpException,
  Injectable,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

export const SUITES = ['rag', 'agent_tools', 'agent_safety'] as const;
export type Suite = (typeof SUITES)[number];

export type StartRunBody = {
  answer?: boolean;
  judge?: boolean;
  limit?: number | null;
  n?: number;
  k?: number;
};

@Injectable()
export class EvalsService {
  constructor(private readonly config: ConfigService) {}

  parseSuite(value: string): Suite {
    if (!(SUITES as readonly string[]).includes(value)) {
      throw new BadRequestException(`Unknown suite ${value}. Use one of ${SUITES.join(', ')}`);
    }
    return value as Suite;
  }

  list(suite: Suite, limit?: string) {
    const query = new URLSearchParams();
    if (suite !== 'rag') query.set('suite', suite);
    if (limit) query.set('limit', limit);
    const qs = query.toString();
    return this.call(suite, `/evals/jobs${qs ? `?${qs}` : ''}`);
  }

  get(suite: Suite, id: string) {
    return this.call(suite, `/evals/jobs/${encodeURIComponent(id)}`);
  }

  start(suite: Suite, body: StartRunBody) {
    const payload =
      suite === 'rag'
        ? { answer: body.answer ?? true, judge: body.judge ?? true, limit: body.limit ?? null }
        : { suite, n: body.n ?? 5, k: body.k ?? 5 };
    return this.call(suite, '/evals/jobs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  private base(suite: Suite): { url: string; name: string } {
    if (suite === 'rag') {
      return { url: this.config.get<string>('RAG_URL') ?? 'http://localhost:8001', name: 'RAG' };
    }
    return { url: this.config.get<string>('AGENT_URL') ?? 'http://localhost:8000', name: 'Agent' };
  }

  private async call(suite: Suite, path: string, init?: RequestInit): Promise<unknown> {
    const { url, name } = this.base(suite);
    let response: Response;
    try {
      response = await fetch(`${url}${path}`, init);
    } catch {
      throw new ServiceUnavailableException(`${name} service is unavailable at ${url}`);
    }
    if (!response.ok) {
      const text = await response.text();
      let detail: unknown = text;
      try {
        detail = (JSON.parse(text) as { detail?: unknown }).detail ?? text;
      } catch {
        // plain-text error body
      }
      const message = typeof detail === 'string' ? detail : JSON.stringify(detail);
      throw new HttpException(message || `${name} request failed`, response.status);
    }
    return response.json();
  }
}
