import assert from "node:assert/strict";
import test from "node:test";
import { parseResponse } from "./api.js";

test("parseResponse() returns parsed JSON on success", async () => {
  const response = new Response(JSON.stringify({ documents: [] }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
  const result = await parseResponse(response);
  assert.deepEqual(result, { documents: [] });
});

test("parseResponse() throws the server's detail message on error", async () => {
  const response = new Response(
    JSON.stringify({ detail: "Only PDF files are supported." }),
    { status: 400 }
  );
  await assert.rejects(() => parseResponse(response), {
    message: "Only PDF files are supported.",
  });
});

test("parseResponse() falls back to statusText when the error body isn't JSON", async () => {
  const response = new Response("not json", { status: 500, statusText: "Internal Server Error" });
  await assert.rejects(() => parseResponse(response), {
    message: "Internal Server Error",
  });
});

test("parseResponse() returns null on 204 No Content", async () => {
  const response = new Response(null, { status: 204 });
  const result = await parseResponse(response);
  assert.equal(result, null);
});
