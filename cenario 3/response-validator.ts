import { z } from "zod";
import pino from "pino";

const logger = pino({ name: "response-validator" });

export const AssistantResponseSchema = z
  .object({
    answer: z.string().min(1, "answer cannot be empty").trim(),
    source_document: z.string().min(1, "source_document is required").trim(),
    confidence: z.enum(["high", "low"]),
  })
  .strict();

export type AssistantResponse = z.infer<typeof AssistantResponseSchema>;

const SAFE_FALLBACK: AssistantResponse = {
  answer:
    "Não foi possível processar esta resposta com segurança. " +
    "Por favor, reformule a pergunta ou escale para o supervisor.",
  source_document: "sistema",
  confidence: "low",
};

const VALID_DOCUMENTS = new Set([
  "POL-001", "PROC-042", "PROC-042-v2",
  "SLA-2024", "FAQ-Atendimento", "sistema",
]);

function checkSourceDocument(response: AssistantResponse, requestId: string): boolean {
  const sources = response.source_document.split(",").map((s) => s.trim());
  const allValid = sources.every((docId) => VALID_DOCUMENTS.has(docId));
  if (!allValid) {
    logger.warn({ requestId, source_document: response.source_document }, "guardrail-1: invalid source");
    return false;
  }
  return true;
}

function checkDangerousCargoReturn(response: AssistantResponse, requestId: string): boolean {
  const answer = response.answer.toLowerCase();
  const mentionsDangerousCargo =
    answer.includes("carga perigosa") ||
    answer.includes("material perigoso") ||
    answer.includes("produto perigoso");
  const mentionsReturn =
    answer.includes("devolução") ||
    answer.includes("devolver") ||
    answer.includes("retorno");

  if (!mentionsDangerousCargo || !mentionsReturn) return true;

  const hasNegation =
    answer.includes("não pode") ||
    answer.includes("não é permitida") ||
    answer.includes("não são elegíveis") ||
    answer.includes("proibida") ||
    answer.includes("bloqueada") ||
    answer.includes("vedado") ||
    answer.includes("não autorizado");

  if (!hasNegation) {
    logger.warn({ requestId }, "guardrail-2: dangerous cargo without negation — BLOCKED");
    return false;
  }
  return true;
}

export interface ValidationResult {
  valid: boolean;
  response: AssistantResponse;
  reason?: string;
}

export function validateResponse(rawResponse: unknown, requestId: string): ValidationResult {
  const parsed = AssistantResponseSchema.safeParse(rawResponse);
  if (!parsed.success) {
    const reason = parsed.error.issues.map((e) => e.message).join("; ");
    logger.warn({ requestId, reason }, "schema validation failed");
    return { valid: false, response: SAFE_FALLBACK, reason };
  }

  if (!checkSourceDocument(parsed.data, requestId))
    return { valid: false, response: SAFE_FALLBACK, reason: "source_document inválido" };

  if (!checkDangerousCargoReturn(parsed.data, requestId))
    return { valid: false, response: SAFE_FALLBACK, reason: "guardrail-2 ativado" };

  logger.info({ requestId }, "response validated successfully");
  return { valid: true, response: parsed.data };
}