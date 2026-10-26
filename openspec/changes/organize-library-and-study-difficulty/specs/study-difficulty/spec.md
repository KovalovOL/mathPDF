## Purpose

Allow learners to choose appropriate challenge and receive understandable explanations without extra generation requests.

## ADDED Requirements

### Requirement: Difficulty band and progression
Generation SHALL accept an integer difficulty from 1 to 5, defaulting to 3, expose an accessible segmented selector and preserve the selection in saved sets. Prompts SHALL order distinct items from easier to harder within that band and preserve source notation.

#### Scenario: Chosen difficulty
- **WHEN** a learner selects level 4 and generates ten problems
- **THEN** one provider request includes level-4 guidance and within-band progression, and the resulting set retains difficulty 4

#### Scenario: Historical content
- **WHEN** a versionless or version-1 set omits difficulty
- **THEN** it remains readable with default difficulty 3 and its content is preserved

### Requirement: Understandable answers
Prompt guidance SHALL request a direct answer and useful reasoning. Flashcard answers SHALL target 45–90 explanatory words and at most three short paragraphs plus necessary formulas, allowing less for simple facts. Problem solutions SHALL include all needed steps without a card-sized word limit. Answers SHALL remain hidden on card fronts.

#### Scenario: Worked solution
- **WHEN** a problem requires multiple steps
- **THEN** guidance requests the method, justified steps and final result, with source notation intact
