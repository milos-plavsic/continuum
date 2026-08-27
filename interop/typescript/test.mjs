import test from "node:test";
import assert from "node:assert/strict";
import { ContinuumClient, canonical, digest } from "./client.mjs";

test("independent client reproduces golden canonical bytes and three-call lifecycle", async () => {
  assert.equal(canonical({z:[2,1],a:"continuum"}), '{"a":"continuum","z":[2,1]}');
  assert.equal(digest({z:[2,1],a:"continuum"}), "26198a2c21c58e943854da0069c9fa58ff4b7c7a2e64ff2ed0c97c881be80f36");
  const calls = [];
  const transport = {call: async (method, body) => { calls.push({method, body}); return {status:"ACCEPTED", method}; }};
  const client = new ContinuumClient(transport);
  await client.publishAgent({principal_id:"candidate-ts", tenant_id:"acme", version:"1"});
  await client.recordObligation({obligation_id:"supplier-42", tenant_id:"acme", state:"OPEN"});
  await client.requestEffect({operation:"vendor.create", idempotency_key:"supplier-42:create:1"});
  assert.deepEqual(calls.map(x => x.method), ["agent.publish", "obligation.record", "effect.request"]);
  assert.ok(calls.every(x => /^[0-9a-f]{64}$/.test(x.body.digest)));
});

test("canonicalizer rejects floats and undefined instead of drifting across languages", () => {
  assert.throws(() => canonical(1.2), /CANONICAL_VALUE_UNSUPPORTED/);
  assert.throws(() => canonical(undefined), /CANONICAL_VALUE_UNSUPPORTED/);
});
