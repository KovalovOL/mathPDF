# Tasks

## 1. Reliable generation

- [x] 1.1 Raise canonical/request limits to 50 and implement bounded batches, per-item validation, duplicate rejection, top-up prompts, and exact final count; review failure/recovery paths and document the contract.
- [x] 1.2 Add an exact-count OpenAI response envelope with an insufficient-source branch and repairable parse failures; review SDK/schema integration and compile the modified Python modules.

## 2. Workspace feedback

- [x] 2.1 Update count controls/API limits and add an accessible animated waiting state with elapsed time and cleanup; inspect CSS/DOM behavior and check JavaScript syntax.

## 3. Library previews

- [x] 3.1 Add lazy PDF first-page, image, and text previews with owned requests, bounded loading, cleanup, and fallbacks; review lifecycle/privacy and check module syntax.
- [x] 3.2 Integrate responsive file cards while retaining open/download actions; document preview behavior and inspect library markup and any available authenticated browser view.

## 4. Integration

- [x] 4.1 Review the final diff and existing-set compatibility, run static syntax and strict OpenSpec checks, record observations and live-generation limits, and push the completed change through the existing deployment.

## 5. Generation queue

- [x] 5.1 Implement bounded owner-scoped FIFO waiting, cancellation, position and frontend waiting deadlines; verify queue ordering, failure recovery and compatibility, then deploy.

Queue rollout verified October 30, 2026: full regression 175 passed / 6 opt-in infrastructure tests skipped; final queue suite 4 passed (two additional cases beyond the full-run collection). FIFO, ownership, duplicate/capacity limits, cancellation before and after lock acquisition, recovery after failure, and browser waiting deadlines verified with synthetic data. Deployment fbb6374 succeeded (Actions 41016546247); public health and normalized local build match 9f95308eb874. No persistence schemas, stored content, sessions or allowance configuration changed. Existing open clients retain the earlier waiting timeout until reload. In-process jobs do not survive restart.
