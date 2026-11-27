import { HttpException, Injectable, ServiceUnavailableException } from '@nestjs/common';
import { Queue } from 'bullmq';
import { mkdir, writeFile } from 'fs/promises';
import { dirname } from 'path';

type Reserved = {
  id: string;
  version: number;
  filename: string;
  storage_path: string;
  status: string;
  source_key: string;
  source_type: string | null;
  source_uri: string | null;
  title: string | null;
  error: string | null;
  created_at: string;
  chunk_count?: number;
};

export type DocumentView = {
  id: string;
  sourceKey: string;
  version: number;
  filename: string;
  sourceType: string | null;
  sourceUri: string | null;
  title: string | null;
  status: string;
  error: string | null;
  createdAt: string;
  chunkCount: number;
};

function ragBase(): string {
  return process.env.RAG_URL ?? 'http://localhost:8001';
}

function toView(row: Reserved): DocumentView {
  return {
    id: row.id,
    sourceKey: row.source_key,
    version: row.version,
    filename: row.filename,
    sourceType: row.source_type,
    sourceUri: row.source_uri,
    title: row.title,
    status: row.status,
    error: row.error,
    createdAt: row.created_at,
    chunkCount: row.chunk_count ?? 0,
  };
}

@Injectable()
export class DocumentsService {
  private queue: Queue | null = null;

  private ingestQueue(): Queue {
    if (!this.queue) {
      const url = new URL(process.env.REDIS_URL ?? 'redis://localhost:6379');
      this.queue = new Queue('ingest', {
        connection: {
          host: url.hostname,
          port: Number(url.port || 6379),
          maxRetriesPerRequest: null,
        },
        defaultJobOptions: {
          attempts: 3,
          backoff: { type: 'exponential', delay: 2000 },
          removeOnComplete: 100,
          removeOnFail: 200,
        },
      });
    }
    return this.queue;
  }

  async uploadFile(file: Express.Multer.File): Promise<DocumentView> {
    const reserved = await this.reserve({
      sourceKey: file.originalname,
      filename: file.originalname,
      sourceUri: null,
    });
    await mkdir(dirname(reserved.storage_path), { recursive: true });
    await writeFile(reserved.storage_path, file.buffer);
    await this.enqueue(reserved.id);
    return toView(reserved);
  }

  async uploadUrl(url: string): Promise<DocumentView> {
    const reserved = await this.reserve({
      sourceKey: url,
      filename: 'snapshot.bin',
      sourceUri: url,
    });
    await this.enqueue(reserved.id);
    return toView(reserved);
  }

  async list(): Promise<DocumentView[]> {
    const rows = (await this.rag('/documents')) as Reserved[];
    return rows.map(toView);
  }

  async get(id: string): Promise<DocumentView> {
    return toView((await this.rag(`/documents/${id}`)) as Reserved);
  }

  private async reserve(body: {
    sourceKey: string;
    filename: string;
    sourceUri: string | null;
  }): Promise<Reserved> {
    return (await this.rag('/documents/reserve', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })) as Reserved;
  }

  private async enqueue(documentId: string): Promise<void> {
    try {
      await this.ingestQueue().add(
        'ingest',
        { documentId },
        { jobId: documentId },
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'queue failed';
      await this.rag(`/documents/${documentId}/status`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ status: 'failed', error: message }),
      }).catch(() => undefined);
      throw new ServiceUnavailableException(`Could not queue ingest: ${message}`);
    }
  }

  private async rag(path: string, init?: RequestInit): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(`${ragBase()}${path}`, init);
    } catch {
      throw new ServiceUnavailableException('RAG service is unavailable');
    }
    if (!response.ok) {
      const detail = await response.text();
      throw new HttpException(detail || 'RAG request failed', response.status);
    }
    return response.json();
  }
}
