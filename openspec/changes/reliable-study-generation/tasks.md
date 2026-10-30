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

- [ ] 5.1 Implement bounded owner-scoped FIFO waiting, cancellation, position and frontend waiting deadlines; verify queue ordering, failure recovery and compatibility, then deploy.
