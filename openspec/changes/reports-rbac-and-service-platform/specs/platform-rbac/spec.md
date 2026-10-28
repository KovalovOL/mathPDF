## Purpose

Control administrative access and role changes using verified application identities and persistent roles.

## ADDED Requirements

### Requirement: Persistent verified roles
Users SHALL have free, premium, admin or owner roles with free as the compatible default. Verified sasha.kovalov2008@gmail.com SHALL receive owner access. Roles SHALL be resolved server-side for every protected request.

#### Scenario: Existing account
- **WHEN** an existing verified account signs in after migration
- **THEN** its user/session identity is preserved and it receives its persisted role or the compatible free default

### Requirement: Administrative access and grants
Only admin/owner SHALL access the administration UI/APIs and private reports. Only owner SHALL grant/revoke admin or assign account tiers. Owner privilege SHALL NOT be transferable or removable through role APIs. All successful role changes SHALL record actor, target, old/new roles and time.

#### Scenario: Free user requests admin data
- **WHEN** a free user requests an admin endpoint directly
- **THEN** the server rejects access without exposing user/report content

#### Scenario: Owner grants an admin
- **WHEN** owner assigns admin to another existing user
- **THEN** the next request recognizes that role and an audit record preserves the change
