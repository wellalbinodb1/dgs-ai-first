# tasks.md — Query Endpoint
# Gerado com apoio do Claude (Chat) a partir do plan.md
# Status: aguardando aprovação do Tech Lead antes de iniciar TASK-001

---

## TASK-001 — Setup do endpoint: HTTP trigger + validação de input

**Descrição:** Criar a estrutura base do Azure Function HTTP trigger com validação de input via Zod. Esta é a task de entrada — todas as demais dependem dela.

**Estimativa:** P

**Depende de:** nenhuma

**Critérios de aceite:**
- `POST /api/query` com body `{ "question": "texto válido" }` retorna HTTP 200
- `POST /api/query` sem o campo `question` retorna HTTP 400 com body `{ "error": "question is required" }`
- `POST /api/query` com `question: ""` (string vazia) retorna HTTP 400
- `POST /api/query` com `question` acima de 1.000 caracteres retorna HTTP 400
- Validação implementada com Zod — nenhum `as any` nem `typeof` manual no schema
- Logs gerados com pino (nunca `console.log`) — cada request registra `requestId = context.invocationId`
- Arquivos criados nos paths corretos: `src/functions/query/handler.ts` e `src/functions/query/validator.ts`
- Código compila sem erros com `tsc --noEmit`

---

## TASK-002 — Geração de embedding via Azure OpenAI

**Descrição:** Implementar a função que converte a pergunta do atendente em vetor de embedding usando o Azure OpenAI Embeddings API.

**Estimativa:** M

**Depende de:** TASK-001

**Critérios de aceite:**
- Função `generateEmbedding(question: string): Promise<number[]>` criada em `src/services/embedder.ts`
- Retry com exponential backoff: máximo 3 tentativas, delays de 500ms / 1s / 2s
- Erros da API Azure lançam `EmbeddingError` (custom error de `src/shared/errors.ts`) — nunca `Error` genérico
- Nenhuma credencial hardcoded — configuração lida de `src/shared/config.ts` via `process.env`
- Teste unitário cobre 3 cenários: sucesso na 1ª tentativa; falha na 1ª + sucesso na 2ª; falha nas 3 tentativas (deve lançar `EmbeddingError`)

---

## TASK-003 — Busca de chunks no Azure AI Search (top-5)

**Descrição:** Implementar a função que recebe o embedding e retorna os 5 chunks mais relevantes do índice, aplicando o filtro de versão de documentos (ADR-0003).

**Estimativa:** M

**Depende de:** TASK-002

**Critérios de aceite:**
- Função `searchChunks(embedding: number[]): Promise<Chunk[]>` criada em `src/services/search.ts`
- Retorna no máximo 5 chunks ordenados por score de similaridade
- Filtra `status !== "superseded"` — documentos obsoletos (ex: PROC-042-v1) nunca chegam ao prompt (ADR-0003)
- Chunks com `fonteTier === "informal"` são retornados mas marcados no objeto (para o prompt-builder sinalizar)
- Tipo `Chunk` definido em `src/shared/types.ts` com campos: `id`, `docId`, `section`, `text`, `score`, `status`, `fonteTier`
- Erro da API lança `SearchError`

---

## TASK-004 — Montagem do prompt respeitando o context budget

**Descrição:** Implementar a função que monta o prompt completo (system prompt + chunks + pergunta) respeitando os limites definidos na ADR-0002.

**Estimativa:** P

**Depende de:** TASK-003

**Critérios de aceite:**
- Função `buildPrompt(question: string, chunks: Chunk[]): string` criada em `src/services/prompt-builder.ts`
- System prompt lido de `/prompts/system-prompt.md` em runtime — nunca hardcoded no código
- Budget respeitado: system prompt ≤ 4.096 tokens + chunks ≤ 8.192 tokens (ADR-0002)
- Chunks com `fonteTier === "informal"` recebem prefixo `[FONTE INFORMAL — verificar com normativo]` no prompt
- Função lança `ContextBudgetError` se o prompt montado ultrapassar o budget total
- Teste unitário verifica: prompt gerado contém o texto do chunk; chunks informais têm o prefixo correto; `ContextBudgetError` lançado quando budget excedido

---

## TASK-005 — Chamada ao GPT-4o e retorno estruturado

**Descrição:** Implementar a chamada ao GPT-4o com o prompt montado e transformar a resposta em objeto estruturado com `source_document`.

**Estimativa:** M

**Depende de:** TASK-004

**Critérios de aceite:**
- Resposta retornada como `{ answer: string, source_document: string, confidence: "high" | "low" }`
- Campo `source_document` nunca ausente — se o modelo não citar fonte, o campo recebe o `docId` do chunk com maior score
- Timeout de 25 segundos (SLA de 30s com 5s de margem operacional)
- Retry com backoff para erros HTTP 429 e 5xx do Azure OpenAI
- Resposta com `confidence: "low"` inclui prefixo: `"Não encontrei informação suficiente. Recomendo escalar para o supervisor."`
- Teste unitário com mock do Azure OpenAI: cobre resposta com fonte citada, sem fonte citada, e timeout

---

## TASK-006 — Health check endpoint (independente)

**Descrição:** Criar endpoint de health check que verifica se as dependências externas estão acessíveis.

**Estimativa:** P

**Depende de:** nenhuma (pode ser implementada em paralelo com qualquer task)

**Critérios de aceite:**
- `GET /api/health` retorna HTTP 200 com `{ status: "ok", version: string, timestamp: string }`
- Retorna HTTP 503 com `{ status: "degraded", failing: string[] }` quando Azure AI Search ou Azure OpenAI estiverem inacessíveis
- `version` lido de `package.json` — nunca hardcoded
- Implementado em `src/functions/health/handler.ts`
- Não tem dependência de lógica de negócio — é um endpoint simples e isolado

---

## Ordem de implementação recomendada

## Conexão com o cenário 1

O protótipo open-source (Exercício 1.3) validou a abordagem de RAG com TF-IDF local. Os problemas identificados lá foram formalizados como critérios de aceite aqui:

- **Filtro de versão (TASK-003):** No protótipo, a PROC-042-v1 aparecia nos resultados e causava multiplicadores errados. Aqui o critério `status !== "superseded"` resolve isso de forma determinística.
- **Context budget (TASK-004):** O protótipo não controlava o tamanho do contexto. Aqui o budget de 4K + 8K tokens é um critério de aceite verificável, derivado da ADR-0002.
- **FAQ informal sinalizado (TASK-003 + TASK-004):** No protótipo, o FAQ dominava o ranking sem aviso. Aqui o `fonteTier` é propagado até o prompt, onde o modelo recebe o sinal explícito.