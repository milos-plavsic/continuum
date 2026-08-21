# Originality, Provenance, and Licensing

Continuum was initialized on August 17, 2026 as a new repository for the All Things Agentic Hackathon submission period.

---

## Prior-Work Relationship

The project is informed by general lessons learned while building earlier agent systems, including RecallOps and LineageGuard: governed memory, explicit state invalidation, human approval, evidence trails, observability, and reproducible evaluation.

No source code, assets, deployment configuration, or documentation from those projects was copied into this repository at initialization.

Continuum has a distinct product purpose, user workflow, data model, Google Cloud architecture, and implementation.

---

## Incorporated Module Declarations & Provenance

### Module: Independent Verification & Evidence-Chain Evaluation (`verification/`)

* **Primary Author:** Fahim Khan (`@phahim1`)
* **Repository:** `milos-plavsic/continuum`
* **Date Incorporated:** August 2026
* **Purpose:** Implements the independent read-only evidence verification boundary, proof-of-fencing checks, deterministic clock evaluations, replay protection, and Continuum Contract 1.0 canonical digest calculations:

  * `verification/schemas.py`
  * `verification/provider.py`
  * `verification/engine.py`
  * `verification/test_verification.py`
* **Provenance & Status:** Created as new, original open-source software specifically for the 2026 All Things Agentic Hackathon. No closed-source code or external proprietary material was imported.
* **License:** Apache License, Version 2.0.

Copyright 2026 Milos Plavsic and Fahim Khan

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at:

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

---

## Pre-Existing Material Register

Standard open-source frameworks and libraries are declared through the project's dependency manifests (`pyproject.toml` / `requirements.txt`) and applicable license notices, including:

* **Pydantic (`>=2.0.0`):** Schema definition and JSON serialization.
* **Google Cloud Firestore SDK:** Read-only evidence retrieval boundary.
* **OpenTelemetry SDK:** Distributed trace instrumentation.
* **PyTest:** Adversarial red-team test harness.

All third-party dependencies remain subject to their respective licenses and copyright notices.

---

## Collaboration & Team Award Distribution Terms

By mutual agreement between co-creators Milos Plavsic and Fahim Khan, the team terms for the All Things Agentic Hackathon submission are recorded as follows:

### 1. Submission Co-Authorship & Attribution

* Both members shall be listed as equal co-authors and teammates on the Devpost project submission and repository.
* Both members maintain write access to the `milos-plavsic/continuum` GitHub repository.

### 2. Net Awards Allocation (60% / 40% Split)

* **Definition of Net Monetary Awards:** Defined as total gross monetary cash or cash-equivalent prize awards received from the hackathon organizers minus mandatory payment processing fees, platform wire transfer charges, or direct currency conversion costs.
* **Cash Distribution:** Net Monetary Awards shall be distributed **60% to Milos Plavsic** and **40% to Fahim Khan**.
* **Cloud Credits & Non-Monetary Vouchers:** Any non-monetary awards, cloud infrastructure credits, or service vouchers shall be distributed or allocated 60% / 40% via platform sub-accounts or shared access according to project and development requirements.
* **Tax Responsibility:** Each party retains sole individual responsibility for reporting and fulfilling any applicable tax liabilities or regulatory filings within their respective legal tax jurisdictions.
