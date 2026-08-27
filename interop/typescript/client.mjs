import { createHash } from "node:crypto";

export function canonical(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean") return JSON.stringify(value);
  if (Number.isSafeInteger(value)) return String(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (typeof value === "object") return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonical(value[k])}`).join(",")}}`;
  throw new Error("CANONICAL_VALUE_UNSUPPORTED");
}
export const digest = value => createHash("sha256").update(canonical(value)).digest("hex");

export class ContinuumClient {
  constructor(transport) { this.transport = transport; }
  publishAgent(agent) { return this.transport.call("agent.publish", {...agent, digest: digest(agent)}); }
  recordObligation(obligation) { return this.transport.call("obligation.record", {...obligation, digest: digest(obligation)}); }
  requestEffect(effect) { return this.transport.call("effect.request", {...effect, digest: digest(effect)}); }
}
