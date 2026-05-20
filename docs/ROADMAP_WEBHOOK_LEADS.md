# OpenConstructionERP — Webhook Leads Feature Roadmap

## Overview
This document outlines the implementation plan for adding incoming webhook functionality to automatically create CRM leads from external data sources.

## Status
- **Feature**: Incoming Webhook Leads Module
- **Priority**: p2 (This Quarter)
- **Estimated Effort**: 2-3 weeks
- **Dependencies**: oe_crm, oe_integrations, oe_users

## Implementation Plan

### Round 1 — Core Backend Module (Week 1)
**Goal**: Establish the foundation module with basic webhook reception and lead creation

| Task | Description | Status |
|------|-------------|--------|
| Scaffold module structure | Copy oe-module-template to webhook_leads | ☐ |
| Database models | WebhookSource, WebhookLog, PayloadMapping tables | ☐ |
| Basic router | POST /webhook_leads/incoming/ endpoint | ☐ |
| Service layer | Webhook validation → CRM lead creation flow | ☐ |
| Unit tests | Core service logic validation | ☐ |

### Round 2 — Security & Validation (Week 2)
**Goal**: Implement robust security, authentication, and payload validation

| Task | Description | Status |
|------|-------------|--------|
| Authentication | API keys, HMAC signatures, JWT support | ☐ |
| Rate limiting | Per-source/IP rate limiting middleware | ☐ |
| Payload validation | Schema validation for common webhook formats | ☐ |
| Error handling | Comprehensive error responses and logging | ☐ |
| Integration tests | End-to-end webhook → lead creation flow | ☐ |

### Round 3 — Frontend UI & Documentation (Week 3)
**Goal**: Provide configuration interface and complete documentation

| Task | Description | Status |
|------|-------------|--------|
| Configuration UI | Webhook source management in Settings | ☐ |
| Log viewer | Audit trail of webhook receptions | ☐ |
| API documentation | OpenAPI spec updates | ☐ |
| Setup guide | Example configurations for common sources | ☐ |
| E2E tests | Full-stack validation | ☐ |

## Technical Specifications

### API Endpoints
- `POST /api/v1/webhook_leads/incoming/` - Generic webhook receiver
- `POST /api/v1/webhook_leads/incoming/{source}/` - Source-specific endpoints
- `GET /api/v1/webhook_leads/sources/` - List configured sources
- `POST /api/v1/webhook_leads/sources/` - Create new source config
- `GET /api/v1/webhook_leads/logs/` - View processing logs

### Security Features
- Multiple auth methods: API Key header, HMAC-SHA256, Bearer JWT
- IP whitelisting/blacklisting per source
- Rate limiting (requests/minute/source)
- Payload size limits
- Comprehensive audit logging

### Data Flow
1. External system → POST to webhook endpoint
2. Authenticate request (API key/HMAC/JWT)
3. Validate payload against source-specific schema
4. Map external fields to OCERP LeadCreate schema
5. Validate lead data (required fields, formats)
6. Create lead via existing CRM service
7. Log success/failure with detailed metadata
8. Optional: Publish `webhook_leads.lead.created` event

### Payload Mapping
Support for common formats:
- JSON payloads with field mapping
- Form-encoded data
- Custom headers for metadata
- Source-specific transformers (GitHub, Jira, etc.)

## Quality Gates
All commits must pass:
- Backend: `ruff check` + `pytest` coverage >80%
- Frontend: `npm run lint` + `npm run test` + `npm run build`
- Security: No hardcoded secrets, proper input validation
- Documentation: API spec updated, user guide complete

## Open Questions
1. Should we support webhook signature verification for all sources?
2. What default field mappings should we provide for popular systems?
3. Should webhook processing be synchronous or queued for high volume?
4. What level of retry logic should we implement for failed deliveries?

---
*This roadmap follows the OCERP versioning convention and should be referenced when creating GitHub issues and PRs for this feature.*