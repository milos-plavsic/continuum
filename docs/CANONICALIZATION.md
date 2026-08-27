# Canonicalization profile

Continuum uses exactly one security-relevant JSON representation:
[RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785).
The profile identifier is `urn:ietf:rfc:8785`.

`continuum.canonicalization.canonical_json_bytes()` is the implementation
boundary for every digest, signature, idempotency request, event hash, contract
artifact and evidence manifest. `models.canonical()` and
`contract.canonical_bytes()` remain compatibility APIs, but delegate to that
same boundary and introduce no second serialization algorithm.

RFC 8785 constrains values to I-JSON, applies ECMAScript number serialization,
sorts object properties by UTF-16 code units and emits UTF-8. NaN, infinity,
integers outside the interoperable range, lone surrogate code points and
non-string object keys fail closed.

The language-neutral vectors in
`fixtures/canonicalization-rfc8785-v1.json` contain input JSON, canonical bytes
as Base64, and SHA-256. A second-language implementation is conformant only if
all bytes and digests match exactly. Semantic or canonicalization changes
require a new profile identifier and new vectors; they must never silently
reinterpret an existing digest.
