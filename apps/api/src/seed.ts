import { readFileSync } from 'fs';
import { readdir, readFile } from 'fs/promises';
import { join } from 'path';
import { DocumentsService } from './documents/documents.service';

const repoRoot = join(__dirname, '..', '..', '..');
const waitMs = 3 * 60 * 1000;

function loadEnv(path: string): void {
  let text: string;
  try {
    text = readFileSync(path, 'utf8');
  } catch {
    return;
  }
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const raw = trimmed.startsWith('export ') ? trimmed.slice(7) : trimmed;
    const eq = raw.indexOf('=');
    if (eq <= 0) continue;
    const key = raw.slice(0, eq).trim();
    let value = raw.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (process.env[key] === undefined) process.env[key] = value;
  }
}

async function waitForIngest(documents: DocumentsService, id: string, name: string) {
  const deadline = Date.now() + waitMs;
  for (;;) {
    const doc = await documents.get(id);
    if (doc.status === 'done') return doc;
    if (doc.status === 'failed') {
      throw new Error(`${name} ingest failed: ${doc.error ?? 'unknown error'}`);
    }
    if (Date.now() > deadline) {
      throw new Error(`${name} still ${doc.status} after 3 minutes. Is the rag worker running?`);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

async function main(): Promise<void> {
  loadEnv(join(repoRoot, 'apps', 'api', '.env'));
  loadEnv(join(repoRoot, '.env'));

  const seedDir = join(repoRoot, 'data', 'seed');
  const names = (await readdir(seedDir, { withFileTypes: true }))
    .filter((entry) => entry.isFile() && !entry.name.startsWith('.'))
    .map((entry) => entry.name)
    .sort();
  if (names.length === 0) {
    console.log(`No files in ${seedDir}`);
    return;
  }

  const documents = new DocumentsService();
  try {
    for (const name of names) {
      const buffer = await readFile(join(seedDir, name));
      const reserved = await documents.uploadFile({
        originalname: name,
        buffer,
      } as Express.Multer.File);
      const done = await waitForIngest(documents, reserved.id, name);
      console.log(`${name} -> ${done.id} v${done.version} (${done.chunkCount} chunks)`);
    }
  } finally {
    await documents.close();
  }
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exit(1);
});
