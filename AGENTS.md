# Project rules

## Backward compatibility

- Every new release must read all previously supported persisted formats, including saved study sets and browser drafts. Preserve formulas, source references, variants and user content.
- Evolve formats with compatible defaults or explicit, non-destructive upgrades. Missing study-set version markers mean version 1. Keep historical compatibility fixtures unchanged and add fixtures for new formats.
- Never silently delete, discard, reinterpret or require regeneration of older data to accommodate a new feature.
- Breaking backward read compatibility is permitted only for a major change with the project owner's explicit approval. Do not infer this approval from permission to implement or deploy a feature.
- Older application releases are not required to read newer formats.

Documentation, UI copy and LLM prompt files must be in English.
