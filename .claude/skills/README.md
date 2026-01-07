# Specialized Skills for Financial Insight & Risk Advisor Agent

This directory contains specialized skills that provide domain expertise for building the Financial Insight & Risk Advisor Agent. Each skill represents a focused area of expertise with constitution-aligned best practices, code examples, and deliverables.

## Available Skills

### 1. Frontend UI Designer (`frontend-ui-designer.md`)

**Expertise**: Power BI dashboards, financial visualizations, executive-friendly UI

**Key Capabilities**:
- Power BI dashboard design with DAX queries
- Financial data visualization (KPIs, anomaly heatmaps, trend lines)
- Confidence score indicators and alert notifications
- Explainability components with source references
- Accessibility and responsive design

**When to Use**:
- Designing executive dashboards for quarterly reviews
- Creating visualizations for anomaly detection
- Building drill-down interfaces for reasoning chains
- Implementing real-time financial metrics displays

**Example Invocation**:
```
"As the Frontend UI Designer, design the executive dashboard for quarterly financial review with anomaly highlighting"
```

---

### 2. Backend Engineer (`backend-engineer.md`)

**Expertise**: Azure services, API design, integration architecture

**Key Capabilities**:
- RESTful API endpoint design with versioning
- Azure Functions and Durable Functions orchestration
- Azure Service Bus event-driven workflows
- Data storage strategy (Blob, Cosmos DB, Table Storage)
- Performance optimization and caching (Azure Redis)
- Application Insights monitoring

**When to Use**:
- Designing the ingestion and analysis pipeline
- Creating API endpoints for insights retrieval
- Implementing autonomous routing logic
- Setting up monitoring and telemetry

**Example Invocation**:
```
"As the Backend Engineer, design the API endpoints for document ingestion and analysis triggering"
```

---

### 3. Dependencies Manager (`dependencies-manager.md`)

**Expertise**: Azure SDK management, Python packages, IaC, CI/CD

**Key Capabilities**:
- Python dependency management (Poetry, pip-tools)
- Azure SDK version compatibility tracking
- Security vulnerability scanning (Dependabot, Safety, Bandit)
- Infrastructure-as-Code (Bicep templates)
- Docker containerization with multi-stage builds
- CI/CD pipeline configuration (GitHub Actions, Azure DevOps)

**When to Use**:
- Setting up project dependencies and virtual environments
- Managing Azure SDK updates and breaking changes
- Provisioning Azure resources with Bicep
- Creating deployment pipelines
- Responding to security vulnerabilities

**Example Invocation**:
```
"As the Dependencies Manager, setup dependency management with security scanning for the project"
```

---

### 4. AI Agent Developer (`ai-agent-developer.md`)

**Expertise**: Azure OpenAI prompts, reasoning chains, confidence scoring

**Key Capabilities**:
- Prompt engineering for anomaly detection, trend analysis, risk assessment
- Confidence scoring algorithms with weighted factors
- Autonomous routing logic (high/medium/low confidence thresholds)
- Reasoning chain logging for explainability
- Prompt template versioning and A/B testing
- Golden dataset evaluation

**When to Use**:
- Designing prompt templates for financial analysis
- Implementing confidence score calculations
- Building threshold-based decision logic
- Creating reasoning chain audit trails
- Optimizing prompts through A/B testing

**Example Invocation**:
```
"As the AI Agent Developer, design the prompt and confidence scoring for anomaly detection"
```

---

### 5. Data Ingestion Engineer (`data-ingestion-engineer.md`)

**Expertise**: Azure Document Intelligence, PDF/Excel extraction, data validation

**Key Capabilities**:
- Azure Document Intelligence integration (prebuilt-layout model)
- Financial statement parsing (P&L, balance sheet, cash flow)
- Table extraction with cell-level source references
- Data validation with Pydantic schemas
- OCR quality assessment and error handling
- Batch processing with retry logic

**When to Use**:
- Integrating Azure Document Intelligence for PDF processing
- Parsing complex financial tables
- Validating extracted data quality
- Tracking source references for audit trail
- Handling extraction failures gracefully

**Example Invocation**:
```
"As the Data Ingestion Engineer, design the pipeline for extracting financial data from PDF reports"
```

---

### 6. Security & Compliance Specialist (`security-compliance-specialist.md`)

**Expertise**: Azure security, RBAC, compliance (SOX, GDPR, FINRA)

**Key Capabilities**:
- Azure AD RBAC configuration with custom roles
- Conditional access policies (MFA, trusted locations, compliant devices)
- Azure Key Vault secrets management
- Encryption at rest and in transit (TLS 1.3)
- PII/PCI redaction for logs and outputs
- Audit logging with 7-year retention
- Compliance reporting (SOX quarterly reports)
- Automated security scanning (Trivy, Bandit, TruffleHog)

**When to Use**:
- Setting up authentication and authorization
- Configuring encryption for sensitive data
- Implementing PII redaction in logs
- Creating audit trails for compliance
- Generating SOX/GDPR compliance reports
- Responding to security vulnerabilities

**Example Invocation**:
```
"As the Security & Compliance Specialist, configure RBAC and audit logging for the agent"
```

---

## How to Use Skills

### Invoking Skills in Conversation

You can invoke a skill by referencing its role:

```
"As the [Skill Name], [your request]"
```

**Examples**:
- "As the Backend Engineer, design the API for retrieving insights"
- "As the AI Agent Developer, create a prompt for risk assessment"
- "As the Security Specialist, audit the authentication flow"

### Combining Multiple Skills

For complex tasks, you can chain skills:

```
User: "Setup the complete ingestion pipeline"

Response:
1. Data Ingestion Engineer: Design PDF extraction with Azure Document Intelligence
2. Backend Engineer: Create API endpoints and storage architecture
3. Dependencies Manager: Configure required Azure SDKs and dependencies
4. Security Specialist: Add encryption and audit logging
```

### Skill Handoffs

Skills include predefined handoff points for seamless collaboration:

- **Data Ingestion → Backend Engineer**: Pass extracted data schema for API design
- **AI Agent Developer → Backend Engineer**: Provide reasoning chain storage format
- **Backend Engineer → Security Specialist**: Request authentication middleware audit
- **Any Skill → Dependencies Manager**: Request package or Azure resource setup

---

## Constitution Alignment

All skills are aligned with the project constitution (`.specify/memory/constitution.md`):

| Principle | Aligned Skills |
|-----------|----------------|
| I. Data-First Financial Analysis | Data Ingestion Engineer, Backend Engineer |
| II. Autonomous Reasoning with Confidence Thresholds | AI Agent Developer, Backend Engineer |
| III. Explainability and Auditability | AI Agent Developer, Frontend UI Designer, Security Specialist |
| IV. Anomaly Detection and Risk Flagging | AI Agent Developer, Frontend UI Designer |
| V. Secure Data Handling and Access Control | Security Specialist, Backend Engineer, Dependencies Manager |
| VI. Human-in-the-Loop | Frontend UI Designer, AI Agent Developer |
| VII. Continuous Learning and Model Versioning | AI Agent Developer, Dependencies Manager |

---

## Skill Development Workflow

### Example: Building Anomaly Detection Feature

**Phase 1: Data Ingestion**
```
"As the Data Ingestion Engineer, setup Azure Document Intelligence to extract financial metrics from Q4 reports"
```

**Phase 2: AI Analysis**
```
"As the AI Agent Developer, create the anomaly detection prompt with confidence scoring"
```

**Phase 3: Backend Integration**
```
"As the Backend Engineer, design the API endpoints for triggering analysis and retrieving insights"
```

**Phase 4: Frontend Visualization**
```
"As the Frontend UI Designer, create a Power BI dashboard showing detected anomalies with confidence scores"
```

**Phase 5: Security & Compliance**
```
"As the Security Specialist, add audit logging for all insight access and configure RBAC"
```

**Phase 6: Deployment**
```
"As the Dependencies Manager, create the Bicep templates and CI/CD pipeline for deployment"
```

---

## Best Practices

### 1. Start with Constitution Review
Before invoking any skill, review the constitution (`.specify/memory/constitution.md`) to understand the non-negotiable requirements.

### 2. Use Precise Invocations
Be specific about what you need:
- ❌ "Design the backend"
- ✅ "As the Backend Engineer, design the API endpoints for document ingestion with source reference tracking"

### 3. Reference Related Skills
When one skill's output depends on another:
- "As the Backend Engineer, design the API using the data schema from the Data Ingestion Engineer"

### 4. Ask for Deliverables
Each skill can provide specific outputs:
- "As the AI Agent Developer, provide the prompt template and confidence scoring code"

### 5. Validate Against Constitution
After receiving output from a skill, verify alignment:
- "Does this design comply with Principle V (Secure Data Handling)?"

---

## Skill Maintenance

### Adding New Skills
To add a new skill:
1. Create `[skill-name].md` in `.claude/skills/`
2. Follow the template structure (see existing skills)
3. Include YAML frontmatter with description and expertise
4. Define constitution alignment section
5. Provide code examples and deliverables
6. Update this README

### Updating Existing Skills
When updating a skill:
1. Review constitution for any principle changes
2. Update code examples to match latest Azure SDK versions
3. Add new best practices discovered during implementation
4. Update handoff points if integration patterns change

---

## Quick Reference

| Task | Recommended Skill |
|------|-------------------|
| PDF extraction | Data Ingestion Engineer |
| API design | Backend Engineer |
| Prompt engineering | AI Agent Developer |
| Dashboard design | Frontend UI Designer |
| Package management | Dependencies Manager |
| RBAC configuration | Security Specialist |
| Bicep templates | Dependencies Manager |
| Confidence scoring | AI Agent Developer |
| PII redaction | Security Specialist |
| OCR quality assessment | Data Ingestion Engineer |
| Monitoring setup | Backend Engineer |
| Vulnerability scanning | Dependencies Manager + Security Specialist |

---

## Support

For questions about skill usage or to request new skills, refer to:
- Project constitution: `.specify/memory/constitution.md`
- Command files: `.claude/commands/sp.*.md`
- Template files: `.specify/templates/*.md`

---

**Version**: 1.0.0 | **Created**: 2026-01-08 | **Skills Count**: 6