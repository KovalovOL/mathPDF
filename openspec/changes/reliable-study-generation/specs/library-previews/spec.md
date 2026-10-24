## Purpose

Help signed-in learners recognize their uploaded files before opening the reading workspace.

## ADDED Requirements

### Requirement: Recognizable private file previews
The home library SHALL display each PDF's first page, a thumbnail for images, and an opening excerpt for text or Markdown. Previews SHALL use owner-authorized file access and preserve file names, metadata, opening links, and download actions.

#### Scenario: Uploaded PDF
- **WHEN** an owned PDF appears in the visible library
- **THEN** its first page is previewed and choosing the file opens its existing workspace

#### Scenario: Foreign document
- **WHEN** a preview request references another account's file
- **THEN** the existing file endpoint denies access without returning bytes

### Requirement: Resilient lazy previews
The library SHALL load previews near the viewport with bounded concurrency and release document resources after rendering. A failed preview SHALL leave the file's open/download actions usable. Text previews SHALL be displayed as plain text.

#### Scenario: Unavailable preview
- **WHEN** the first page cannot be rendered
- **THEN** the file shows a readable preview fallback while remaining available to open or download
