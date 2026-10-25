# Historical study-set fixtures

These synthetic payloads use the canonical shape supported by the first authenticated library (`0a32c9e`). They contain no real user data. Version markers, goal identifiers, item-level citations, generation comments and context snapshots are intentionally absent, exercising the defaults used by older records and browser drafts.

Keep these JSON files unchanged when the schema evolves. Add separate fixtures for each new format, and retain read/save/render/export checks for the older files. Updating a fixture to make a breaking reader pass defeats the compatibility requirement. The flashcard fixture deliberately includes older front-side formula placements so display recovery can be checked without rewriting stored content.
