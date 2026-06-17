# SKILL — Create RAG Endpoint (Artifact)
# Nível: Artifact
# Depende de: skills/foundation/typescript-conventions.md
#             skills/domain/azure-functions-endpoint.md
# Consumido por: Devs, Copilot

## Quando usar
Use esta skill para criar um endpoint completo com fluxo RAG
(embedding → search → prompt → completion).

Frases-ativação:
- "criar endpoint RAG"
- "endpoint com Azure AI Search"
- "query endpoint completo"

---

## Checklist de implementação

1. [ ] Validação de input com Zod (ver validator.ts)
2. [ ] Embedding via Azure OpenAI com retry
3. [ ] Busca top-5 no Azure AI Search — filtrar `status !== "superseded"`
4. [ ] Montagem do prompt respeitando budget: 4K system + 8K chunks (ADR-0002)
5. [ ] Chunks com `fonteTier === "informal"` recebem prefixo `[FONTE INFORMAL]`
6. [ ] Resposta com `{ answer, source_document, confidence }`
7. [ ] `source_document` nunca ausente
8. [ ] Timeout de 25s

---

## Dependências
- Leia antes: `skills/foundation/typescript-conventions.md`
- Leia antes: `skills/domain/azure-functions-endpoint.md`
