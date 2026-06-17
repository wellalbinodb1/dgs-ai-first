# SKILL — Azure Functions Endpoint (Domain)
# Nível: Domain
# Depende de: skills/foundation/typescript-conventions.md
# Consumido por: Devs, Copilot, Claude Code

## Quando usar
Leia este arquivo ao criar ou modificar qualquer Azure Function HTTP trigger.

Frases-ativação:
- "criar endpoint"
- "HTTP trigger"
- "nova rota /api/"
- "Azure Function handler"

---

## Estrutura de arquivos obrigatória

```
src/functions/<nome>/
├── handler.ts          ← HTTP trigger (app.http)
├── validator.ts        ← Zod schema + função de validação
└── response-builder.ts ← montagem da resposta tipada
```

---

## Template de handler

```typescript
// src/functions/<nome>/handler.ts
import { app, HttpRequest, HttpResponseInit, InvocationContext } from "@azure/functions";
import pino from "pino";
import { validate<Nome>Request } from "./validator";
import { ValidationError } from "../../shared/errors";

const logger = pino({ name: "<nome>-handler" });

async function <nome>Handler(
  request: HttpRequest,
  context: InvocationContext
): Promise<HttpResponseInit> {
  const requestId = context.invocationId;
  logger.info({ requestId }, "<nome> request received");

  try {
    const body = await request.json();
    const validated = validate<Nome>Request(body);
    // lógica de negócio aqui
    return { status: 200, jsonBody: { /* resposta tipada */ } };
  } catch (error) {
    if (error instanceof ValidationError) {
      logger.warn({ requestId, error: error.message }, "validation failed");
      return { status: 400, jsonBody: { error: error.message } };
    }
    logger.error({ requestId, error }, "unexpected error");
    return { status: 500, jsonBody: { error: "internal server error" } };
  }
}

app.http("<nome>", {
  methods: ["POST"],
  authLevel: "function",
  route: "<nome>",
  handler: <nome>Handler,
});
```

---

## Anti-padrões específicos do Copilot para Azure Functions

| Anti-padrão | Código errado | Correção |
|---|---|---|
| Sintaxe v3 | `module.exports = async function(context, req)` | `app.http("name", { handler })` |
| Status omitido | `return { jsonBody: data }` | `return { status: 200, jsonBody: data }` |
| Parse sem try/catch | `const body = await request.json()` | Envolver em try/catch — erros de parse → 400 |
| Logger sem name | `const logger = pino()` | `pino({ name: "handler-name" })` |

---

## Dependências
- Leia antes: `skills/foundation/typescript-conventions.md`
- Tipos: `src/shared/types.ts`
- Erros: `src/shared/errors.ts`
- Config: `src/shared/config.ts`
