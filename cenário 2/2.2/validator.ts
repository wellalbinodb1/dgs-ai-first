import { z } from "zod";
import { ValidationError } from "../../shared/errors";

const QueryRequestSchema = z.object({
  question: z
    .string({ error: "question is required" })
    .min(1, "question cannot be empty")
    .max(1000, "question must not exceed 1000 characters"),
});

export function validateQueryRequest(body: unknown): { question: string } {
  const result = QueryRequestSchema.safeParse(body);
  if (!result.success) {
    const message = result.error.issues.map((issue) => issue.message).join("; ");
    throw new ValidationError(message);
  }
  return result.data;
}