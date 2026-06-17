import {
  app,
  HttpRequest,
  HttpResponseInit,
  InvocationContext,
} from "@azure/functions";
import pino from "pino";
import { validateQueryRequest } from "./validator";
import { ValidationError } from "../../shared/errors";

const logger = pino({ name: "query-handler" });

async function queryHandler(
  request: HttpRequest,
  context: InvocationContext
): Promise<HttpResponseInit> {
  const requestId = context.invocationId;

  logger.info({ requestId }, "query request received");

  try {
    const body = await request.json();
    const { question } = validateQueryRequest(body);

    logger.info({ requestId, questionLength: question.length }, "input validated");

    // TODO TASK-002: const embedding = await generateEmbedding(question);
    // TODO TASK-003: const chunks = await searchChunks(embedding);
    // TODO TASK-004: const prompt = buildPrompt(question, chunks);
    // TODO TASK-005: const response = await getCompletion(prompt);

    return {
      status: 200,
      jsonBody: {
        answer: "not implemented",
        source_document: "",
        confidence: "low",
      },
    };
  } catch (error) {
    if (error instanceof ValidationError) {
      logger.warn({ requestId, error: error.message }, "validation failed");
      return { status: 400, jsonBody: { error: error.message } };
    }

    logger.error({ requestId, error }, "unexpected error");
    return { status: 500, jsonBody: { error: "internal server error" } };
  }
}

app.http("query", {
  methods: ["POST"],
  authLevel: "function",
  route: "query",
  handler: queryHandler,
});