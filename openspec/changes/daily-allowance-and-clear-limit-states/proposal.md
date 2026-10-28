# Proposal

## Why
The owner intended a daily generation allowance and needs a clearer remaining-usage indicator and a friendly insufficient-allowance experience.

## What Changes
- Reset free allowances every 24 hours at 00:00 UTC, retaining the 200,000-token default and existing configured amounts.
- Explicitly read and non-destructively upgrade historical monthly limit settings; keep usage, reservation and content history.
- Show a clearly labeled used/remaining bar and live reset countdown.
- Return typed allowance failures through synchronous and background generation, and show an accessible recovery dialog that preserves the generation selection.

## Impact
Quota accounting, additive settings schema, admin wording, generation error transport, shared allowance UI, regression coverage and deployment.
