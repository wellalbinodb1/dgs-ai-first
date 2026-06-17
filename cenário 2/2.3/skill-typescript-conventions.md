# SKILL — TypeScript Conventions (Foundation)
# Nível: Foundation
# Depende de: nenhuma (esta é a skill raiz)
# Consumido por: todas as skills Domain e Artifact

## Quando usar
Leia este arquivo ANTES de gerar qualquer código TypeScript neste projeto.

Frases-ativação:
- "gerar código TypeScript"
- "criar arquivo .ts"
- "implementar endpoint"
- "criar função"
- "escrever teste"

---

## Stack obrigatória

- **TypeScript 5.x** com `strict: true` (conforme tsconfig.json do repositório)
- **Azure Functions v4** — usar `app.http()`, NUNCA `module.exports`
- **Zod** para toda validação de input e output
- **pino** para logging — NUNCA `console.log` ou `console.error`
- **Custom errors** de `src/shared/errors.ts` — NUNCA `throw new Error()`

---

## Regras prescritivas

### Imports

```typescript
// ✅ DO — named imports, paths relativos explícitos
import { validateQueryRequest } from "./validator";
import { ValidationError } from "../../shared/errors";
import { app, HttpRequest } from "@azure/functions";

// ❌ DON'T — require(), default imports de módulos próprios, paths ambíguos
const validator = require("./validator");
import validator from "./validator";
import * as errors from "../../shared/errors";
```

### Tipos

```typescript
// ✅ DO — tipos explícitos em toda assinatura de função
function buildPrompt(question: string, chunks: Chunk[]): string { ... }
async function searchChunks(embedding: number[]): Promise<Chunk[]> { ... }

// ❌ DON'T — any, as any, unknown sem narrowing
function buildPrompt(question: any, chunks: any[]): any { ... }
const result = response as any;
const data = body as unknown as QueryRequest; // cast duplo — nunca
```

### Erros

```typescript
// ✅ DO — custom error + catch com narrowing de tipo
try {
  const validated = validateQueryRequest(body);
} catch (error) {
  if (error instanceof ValidationError) {
    return { status: 400, jsonBody: { error: error.message } };
  }
  logger.error({ error }, "unexpected error");
  return { status: 500, jsonBody: { error: "internal server error" } };
}

// ❌ DON'T — throw genérico, catch sem narrowing, expor stack trace
throw new Error("invalid input");
catch (e) { return { status: 400, body: e.stack }; }
catch (e: any) { return { status: 500, body: e.message }; }
```

### Logging

```typescript
// ✅ DO — pino com contexto estruturado e requestId
import pino from "pino";
const logger = pino({ name: "query-handler" });

logger.info({ requestId, questionLength: question.length }, "input validated");
logger.warn({ requestId, error: error.message }, "validation failed");
logger.error({ requestId, error }, "unexpected error");

// ❌ DON'T — console.log, console.error, strings sem contexto
console.log("input validated");
console.error(error);
console.log(`question length: ${question.length}`);
```

### Async/await

```typescript
// ✅ DO — async/await com tratamento explícito de erro
const embedding = await generateEmbedding(question);
const chunks = await searchChunks(embedding);

// ❌ DON'T — .then/.catch encadeados, floating promises, Promise sem await
generateEmbedding(question).then(e => searchChunks(e)).catch(console.error);
searchChunks(embedding); // sem await — floating promise
```

### Variáveis de ambiente

```typescript
// ✅ DO — sempre via src/shared/config.ts
import { config } from "../../shared/config";
const endpoint = config.azureOpenAiEndpoint;

// ❌ DON'T — process.env direto no código de negócio, valores hardcoded
const endpoint = process.env.AZURE_OPENAI_ENDPOINT;
const apiKey = "sk-1234..."; // NUNCA
```

---

## Anti-padrões que o Copilot gera com frequência

| Anti-padrão | Exemplo errado | Por que é problema | Correção |
|---|---|---|---|
| `as any` em parsing de body | `const body = await request.json() as any` | Bypassa o sistema de tipos — erros de runtime invisíveis no TypeScript | Usar Zod `.safeParse()` com tipo `unknown` |
| `console.log` | `console.log("request received")` | Não aparece no Azure Monitor; sem correlação de requestId | `logger.info({ requestId }, "request received")` |
| Sintaxe Azure Functions v3 | `module.exports = async function(context, req)` | Incompatível com v4 — não compila com as dependências do package.json | `app.http("name", { handler })` |
| `throw new Error()` | `throw new Error("invalid input")` | Perde o tipo no catch — impossible narrowing em strict mode | Usar custom error de `src/shared/errors.ts` |
| Credencial hardcoded | `const key = "abc123"` | Vaza em logs e git history | `config.azureSearchKey` via `src/shared/config.ts` |
| Zod sem `.min()` | `z.string()` para campo obrigatório | Aceita string vazia — passa pela validação sem utilidade | `z.string().min(1, "cannot be empty")` |
| Zod sem `.max()` | `z.string().min(1)` | Sem limite de tamanho — vetor de prompt injection | `z.string().min(1).max(1000)` |
| Status HTTP implícito | `return { jsonBody: result }` | Padrão é 200, mas torna a intenção opaca para quem lê | Sempre incluir `status` explícito |

---

## Dependências
Esta é uma skill Foundation. Não depende de nenhuma outra skill.
Todas as skills Domain e Artifact dependem desta.
