import { copyFile, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const source = resolve(root, '..', 'chatbot_app', 'contracts');
const target = resolve(root, 'src', 'generated');
await copyFile(resolve(source, 'types.ts'), resolve(target, 'chatbot-types.ts'));
const client = await readFile(resolve(source, 'client.ts'), 'utf8');
const browserClient = client
  .replace("from './types'", "from './chatbot-types'")
  .replace(
    "if (!response.ok) throw new ChatbotError(response.status, payload.error?.code ?? 'http_error', payload.error?.message ?? 'Chatbot request failed.');",
    "if (!response.ok) {\n      if (response.status === 401) window.dispatchEvent(new CustomEvent('auth:expired'));\n      throw new ChatbotError(response.status, payload.error?.code ?? 'http_error', payload.error?.message ?? 'Chatbot request failed.');\n    }",
  );
await writeFile(resolve(target, 'chatbot-client.ts'), browserClient);
console.log('Copied chatbot_app/contracts types and client into src/generated.');
