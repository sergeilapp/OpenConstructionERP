# RFC 001 — Incoming Webhook Leads Module

**Status:** proposed
**Date:** 2026-05-18
**Related:** ADR 004, ROADMAP_WEBHOOK_LEADS.md

## Summary

This RFC proposes adding a new `oe_webhook_leads` module to OpenConstructionERP that provides secure incoming webhook endpoints for automatically creating CRM leads from external data sources.

## Motivation

Currently, OpenConstructionERP excels at sending data out via outgoing webhooks (integrations module) but lacks the ability to receive data in to create leads automatically. Users manually enter leads from external sources like:
- Marketing form builders (HubSpot, Mailchimp, Typeform)
- Advertising platforms (Facebook Lead Ads, Google Lead Form Extensions)
- CRM systems (Salesforce, Zoho, Pipedrive)
- Custom applications and landing pages
- Chatbots and conversational interfaces

This manual process is error-prone, time-consuming, and creates data latency between lead capture and follow-up.

## Detailed Design

### Core Functionality
The module will provide:
1. Secure HTTP endpoints to receive webhook POST requests
2. Authentication mechanisms (API keys, HMAC signatures, JWT tokens)
3. Payload validation and schema mapping
4. Integration with existing CRM service for lead creation
5. Comprehensive logging and audit trails
6. Configuration UI for managing webhook sources

### API Design
```
POST /api/v1/webhook_leads/incoming/
  Headers: 
    X-API-Key: {source_api_key}  OR
    Authorization: Bearer {jwt_token}  OR
    X-Signature: {hmac_signature} (with X-Timestamp and Source-ID)
  Body: {external_payload_format}

Response:
  202 Accepted: {webhook_id, status: "queued"}
  400 Bad Request: {error: "validation_details"}
  401 Unauthorized: {error: "auth_failed"}
  429 Too Many Requests: {error: "rate_limited"}
  500 Internal Server Error: {error: "processing_failed"}
```

### Source-Specific Endpoints
```
POST /api/v1/webhook_leads/incoming/github/    # For GitHub webhooks
POST /api/v1/webhook_leads/incoming/typeform/  # For Typeform submissions
POST /api/v1/webhook_leads/incoming/salesforce/ # For Salesforce webhooks
```

### Security Considerations
- Per-source API keys stored encrypted at rest
- Optional HMAC-SHA256 verification with timestamp validation
- JWT bearer token support with expiry validation
- IP address filtering per webhook source
- Rate limiting (configurable requests/minute/source)
- Payload size limits (default 1MB)
- Request/response logging without sensitive data
- SQL injection and XSS prevention

### Data Flow
1. External system → POST webhook to OCERP endpoint
2. Authenticate request using configured method
3. Validate payload size and basic structure
4. Parse payload according to source configuration
5. Apply field mapping rules to convert to LeadCreate schema
6. Validate lead data (required fields, email format, etc.)
7. Create lead via `CrmService.create_lead()`
8. Log reception with metadata (source, timestamp, outcome)
9. Return appropriate HTTP response
10. Optional: Publish `webhook_leads.lead.created` event

### Payload Mapping System
Each webhook source can define:
- JSON path expressions for field extraction
- Default values for missing fields
- Data transformation functions (trim, lowercase, parse date)
- Conditional logic based on payload values
- Example mappings:
  - GitHub Issues: `issue.title` → contact_name, `issue.body` → description
  - Typeform: `answers[0].text` → contact_name, `answers[1].email` → contact_email
  - Salesforce: `Lead.FirstName` + `Lead.LastName` → contact_name

### Database Models
```sql
oe_webhook_sources:
  - id (UUID)
  - user_id (UUID, foreign key)
  - name (string)
  - source_type (string: generic, github, typeform, salesforce, etc.)
  - is_active (boolean)
  - api_key_encrypted (string)
  - hmac_secret_encrypted (string, optional)
  - ip_whitelist (text array)
  - rate_limit_per_minute (integer)
  - field_mappings (JSONB)
  - created_at, updated_at

oe_webhook_logs:
  - id (UUID)
  - webhook_source_id (UUID, foreign key)
  - received_at (timestamp)
  - source_ip (inet)
  - http_method (string)
  - path (string)
  - headers (JSONB, sanitized)
  - payload_size (integer)
  - auth_method (string)
  - auth_success (boolean)
  - validation_success (boolean)
  - lead_created (boolean, nullable)
  - lead_id (UUID, foreign key to oe_crm_leads, nullable)
  - error_message (text, nullable)
  - processed_at (timestamp)
```

### Frontend Components
- Webhook Sources Management (Settings → Modules → Webhook Leads)
  - Add/Edit/Delete sources
  - Test webhook endpoint with sample payloads
  - View recent logs and statistics
  - Configure field mappings per source
- Webhook Logs Viewer
  - Filter by source, date range, outcome
  - View detailed request/response information
  - Resend failed webhooks for testing

## Implementation Approach

### Phase 1: Core Infrastructure (Week 1)
- Scaffold module from oe-module-template
- Implement database models and migrations
- Create basic router with generic webhook endpoint
- Build service layer with authentication and validation
- Integrate with CRM service for lead creation
- Write unit tests for core logic

### Phase 2: Security & Robustness (Week 2)
- Implement multiple authentication methods
- Add rate limiting and IP filtering
- Enhance payload validation and error handling
- Add comprehensive logging
- Write integration tests for end-to-end flows
- Implement source-specific endpoint routing

### Phase 3: UI & Polish (Week 3)
- Build frontend configuration management
- Create log viewer dashboard
- Add documentation and example configurations
- Implement testing utilities (webhook simulator)
- Perform security review and load testing

## Drawbacks
- Increases system complexity and attack surface
- Requires ongoing maintenance and security vigilance
- Potential for abuse if not properly secured
- Development effort delays other features
- May need ongoing updates for new source formats

## Alternatives Considered
1. **Use existing integrations module**: Would require significant changes to outgoing-only webhook system
2. **Core modification to CRM service**: Violates module architecture principles, harder to maintain
3. **External middleware solution**: Adds dependency and complexity, not self-contained
4. **Zapier/Make.com integration**: Requires third-party service, not self-hosted
5. **Polling-based integration**: Higher latency, more complex than push webhooks

## Unresolved Questions
1. Should we provide pre-built templates for popular sources (GitHub, Typeform, etc.)?
2. What level of retry logic should we implement for transient failures?
3. Should webhook processing be synchronous or use a queue for high-volume scenarios?
4. How detailed should the logging be for debugging vs. privacy concerns?
5. Should we support webhook response customization (beyond standard HTTP status codes)?

## Acceptance Criteria
[ ] Module can be installed and enabled via Settings → Modules
[ ] Webhook endpoints authenticate via API key, HMAC, and JWT
[ ] External payloads can be mapped to create valid CRM leads
[ ] Invalid or malicious requests are properly rejected
[ ] Successful webhook receptions are logged with appropriate metadata
[ ] Failed receptions include error details for troubleshooting
[ ] Module follows OCERP coding standards and passes all quality gates
[ ] Documentation includes setup instructions and example configurations
[ ] Security review identifies no critical vulnerabilities
[ ] Performance testing shows acceptable behavior under load

## References
- ADR 004: Incoming Webhook Leads Module Architecture
- ROADMAP_WEBHOOK_LEADS.md: Detailed implementation timeline
- Existing modules for reference: oe_integrations (outgoing webhooks), oe_crm (lead management)
- Webhook security best practices: OWASP ASVS, GitHub webhook security guide