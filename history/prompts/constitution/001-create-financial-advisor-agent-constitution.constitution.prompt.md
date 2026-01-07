---
id: 001
title: Create Financial Advisor Agent Constitution
stage: constitution
date: 2026-01-08
surface: agent
model: claude-sonnet-4-5
feature: none
branch: master
user: unknown
command: /sp.constitution
labels: ["constitution", "financial-analysis", "ai-agent", "azure", "compliance", "security"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .specify/memory/constitution.md
tests:
  - null
---

## Prompt

"Challenge Overview
Learn about the problem, solution, and objectives

The Problem
This module guides learners through developing an autonomous Financial Insight & Risk Advisor Agent that can analyze financial datasets and reports, detect anomalies or risk indicators, and generate human-readable financial insights for leadership review.
The Solution
The module covers the end-to-end development pipeline: ingesting PDF/Excel financial reports using Azure Document Intelligence, extracting structured values, and applying Azure OpenAI reasoning to identify abnormal patterns, variances, or unexpected correlation shifts. It explains how to chain reasoning and alert-trigger logic in Azure AI Foundry so that the agent autonomously decides when to generate CFO-ready summaries, when to escalate issues, and when confidence thresholds require manual review. The content also emphasizes explainability by logging the reasoning chain, providing source references for insights, and enabling Power BI visualization for trend interpretation. Deployment instructions, workflow diagrams, prompts, and testing guides are included to support production use.
Learning Objectives
Participants will learn to build an autonomous financial advisory agent that reviews financial documents, identifies anomalies, generates insights, and notifies business leadership for proactive decision-making.

Ingest financial data (PDF/Excel) using Azure Document Intelligence
Apply reasoning prompts for trend detection and anomaly flagging
Build autonomous confidence-based decision logic for alerting
Generate natural-language financial summaries and recommendations
Design explainable AI reporting for transparency and auditability"

## Response snapshot

Created comprehensive constitution (v1.0.0) for Financial Insight & Risk Advisor Agent with seven core principles:

1. Data-First Financial Analysis - All insights traceable to source documents via Azure Document Intelligence
2. Autonomous Reasoning with Confidence Thresholds - Confidence-based routing (high/medium/low) with logged reasoning chains
3. Explainability and Auditability - Human-readable explanations, source references, 7-year audit retention
4. Anomaly Detection and Risk Flagging - Configurable detection rules for statistical outliers, variances, correlation shifts
5. Secure Data Handling and Access Control - Azure AD RBAC, Key Vault for secrets, PII/PCI redaction
6. Human-in-the-Loop for High-Stakes Decisions - Agent advises, humans approve financial actions
7. Continuous Learning and Model Versioning - Semantic versioning for prompts, detection rules, and models

Additional sections: Security & Compliance (SOX, GDPR, FINRA), Development Workflow (test-first, code review gates), and Governance (amendment process, compliance verification).

## Outcome

- ✅ Impact: Project constitution established with principles aligned to autonomous financial agent requirements (data provenance, explainability, security, human oversight)
- 🧪 Tests: No tests created (constitution is policy document)
- 📁 Files: Created .specify/memory/constitution.md (v1.0.0)
- 🔁 Next prompts: /sp.specify to create feature specifications aligned with constitution principles
- 🧠 Reflection: Constitution balances AI autonomy with financial compliance requirements; confidence thresholds and explainability are critical differentiators

## Evaluation notes (flywheel)

- Failure modes observed: None (initial creation)
- Graders run and results (PASS/FAIL): Manual review required - constitution should be validated by compliance/security stakeholders
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add specific metrics/KPIs for principle compliance (e.g., "100% of insights include source references")
