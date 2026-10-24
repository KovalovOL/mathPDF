# Spec Delta

## Purpose

Provides account sign-in and isolates each learner's PDFs and generated study material from other users.

## ADDED Requirements

### Requirement: User can sign in with Google
The system SHALL allow a user to create or access an application account by completing Google sign-in.

#### Scenario: Successful Google sign-in
- **WHEN** a user completes Google sign-in successfully
- **THEN** the system creates or resumes the application account associated with that Google identity and grants an authenticated application session

#### Scenario: Google sign-in is canceled or rejected
- **WHEN** Google sign-in is canceled or does not establish a valid identity
- **THEN** the system does not grant an authenticated application session

### Requirement: User data is isolated by account
The system SHALL make each user's PDFs and generated study material accessible only to that user.

#### Scenario: User requests another account's resource
- **WHEN** an authenticated user requests a PDF or study material owned by a different account
- **THEN** the system denies access without disclosing the resource contents

#### Scenario: Unauthenticated user requests a private resource
- **WHEN** a request for a user's private PDF or study material has no valid application session
- **THEN** the system denies access
