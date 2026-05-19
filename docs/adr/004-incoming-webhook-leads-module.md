# ADR 004 — Incoming Webhook Leads Module

**Status:** proposed
**Date:** 2026-05-18
**Related:** ADR 000 (template), `app/core/events.py`, `app/modules/integrations/`, `app/modules/crm/`

## Context

OpenConstructionERP currently supports outgoing webhooks (sending data to external systems via the integrations module) but lacks the ability to receive incoming webhook data from external sources to automatically create CRM leads. Users need a way to integrate external lead generation systems (marketing platforms, form builders, CRM systems, etc.) with OCERP's lead management without manual data entry.

Constraints from the user / existing platform:
- Must follow OCERP's module system architecture
- Should leverage existing CRM service layer for lead creation
- Needs robust security to prevent unauthorized lead creation
- Should integrate with existing event bus for module-to-module communication
- Must support various webhook payload formats (JSON, form-data) from different sources
- Requires audit logging and debugging capabilities
- Should not modify core OCERP code (follow module pattern)
- Needs to handle high-volume webhook traffic gracefully
- Must provide configuration UI for non-technical users

## Decision

Create a new integration module `oe_webhook_leads` that provides secure incoming webhook endpoints for automatic CRM lead creation, following OCERP's established module architecture patterns.

### Module Architecture
```
backend/app/modules/webhook_leads/
├── __init__.py
├── manifest.py              # Module metadata
├── router.py                # FastAPI routes for webhook reception
├── schemas.py               # Pydantic models for requests/responses
├── service.py               # Core business logic (authentication, validation, lead creation)
├── models.py                # SQLAlchemy models (WebhookSource, WebhookLog, PayloadMapping)
├── repository.py            # Data access layer
├── permissions.py           # Permission definitions (webhook_leads.create, webhook_leads.read)
├── validators.py            # Custom validation rules for webhook payloads
└── tests/                   # Unit and integration tests
```

### Key Components

1. **Manifest** (`manifest.py`):
   ```python
   manifest = ModuleManifest(
       name="oe_webhook_leads",
       version="1.0.0",
       display_name="Webhook Leads",
       description="Incoming webhook endpoints for external lead creation",
       author="OpenConstructionERP Community",
       category="integration",
       depends=["oe_crm", "oe_integrations", "oe_users"],
       auto_install=False,
       enabled=True,
   )
   ```

2. **Router** (`router.py`):
   - `POST /api/v1/webhook_leads/incoming/` - Main webhook endpoint
   - `POST /api/v1/webhook_leads/incoming/{source}/` - Source-specific endpoints
   - CRUD endpoints for webhook source configuration
   - Log viewing endpoints

3. **Service Layer** (`service.py`):
   - Multiple authentication methods (API Key, HMAC-SHA256, JWT)
   - Payload parsing and validation
   - Field mapping from external schemas to LeadCreate
   - Integration with existing `CrmService.create_lead()`
   - Comprehensive error handling and logging
   - Event publishing via `event_bus` for `webhook_leads.lead.created`

4. **Security Features**:
   - Per-source API keys stored encrypted in database
   - Optional HMAC signature verification with per-source secrets
   - JWT bearer token support
   - IP address whitelisting/blacklisting per source
   - Rate limiting (requests per minute/source)
   - Payload size limits
   - Request/response logging for audit trails

5. **Data Models** (`models.py`):
   - `WebhookSource`: Configuration for each external webhook source
   - `WebhookLog`: Detailed log of each webhook reception attempt
   - `PayloadMapping`: Field mapping rules for different sources/formats

### Integration Points
- **CRM Service**: Direct use of `CrmService.create_lead()` method
- **Event Bus**: Publish `webhook_leads.lead.created` events for other modules
- **Existing Integrations**: Complements outgoing webhook functionality in `oe_integrations`
- **Validation Engine**: Custom validation rules for payload schemas
- **Permissions System**: Fine-grained access control for webhook management

## Consequences

### Positive
- Enables seamless integration with external lead generation systems
- Eliminates manual data entry for leads from web forms, marketing platforms, etc.
- Follows established OCERP module patterns (no core modifications)
- Leverages existing, battle-tested CRM service for lead creation
- Provides robust security measures to prevent abuse
- Offers detailed audit logging for troubleshooting and compliance
- Scalable design that can support additional webhook sources over time
- Maintains loose coupling through event-driven architecture

### Negative / Trade-offs
- Increases attack surface (mitigated by strong authentication/validation)
- Adds complexity to the system (mitigated by clear separation of concerns)
- Requires ongoing maintenance of the module (standard for custom features)
- Potential for high-volume traffic (mitigated by rate limiting and async processing)
- Development effort required (estimated 2-3 weeks for MVP)

### Risks & Mitigations
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Security vulnerabilities (unauthorized lead creation) | Medium | Strong authentication, input validation, rate limiting, encryption of secrets |
| Performance issues under high load | Low-Medium | Rate limiting, async processing options, caching where appropriate |
| Payload mapping complexity for diverse sources | Medium | Extensible mapping system, pre-built transformers for common sources |
| Configuration complexity for end users | Low-Medium | Intuitive UI, template configurations, clear documentation |
| Dependency conflicts with future OCERP updates | Low | Follow module interface contracts, minimal core dependencies |

## Rollback Path
If this decision proves problematic:
1. Disable the module via Settings → Modules & Marketplace
2. Remove `backend/app/modules/webhook_leads/` directory
3. Remove any database migrations (if any were applied)
4. No core code modifications were made, so rollback is clean
5. Database tables can be left in place or removed via manual SQL if desired

## Related
- Issues: To be created upon implementation
- ADRs: ADR-000 (template), ADR-002 (DDC canonical format reference)
- Files: 
  - `backend/app/modules/webhook_leads/` (new module)
  - `app/modules/crm/service.py` (existing CRM service to be used)
  - `app/modules/integrations/service.py` (existing outgoing webhooks for reference)
  - `app/core/events.py` (event bus for potential event publishing)