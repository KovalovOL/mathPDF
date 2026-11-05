# Formula-writing guide

## 1. Response and block structure

Return the schema's result with status "completed" and exactly the requested number of items. Each item has a plain-English title, a REQUIRED source reference in formula, a skill chosen before question, and a question array. The reference is either {"page": <original page>} for a prose-based fact or an object with the exact printed source latex, page and variant. A symbolic central formula is not compulsory; prefer a page-only reference for a prose-based concept or a method stated in words. For problems, choose the method and original task before selecting this supporting reference. Problems use answer for their worked solution. Flashcards use from_notes for source-only content, verbatim or near-verbatim, and explanation for short AI-added context; return their legacy answer array as [] because the app assembles the two labeled back sections. When present, the central mathematical formula is the literal source expression the item teaches or uses, not a reconstructed summary of its meaning. The app displays it on the answer side for both modes, within From notes for new flashcards, never on the flashcard front. Flashcard question arrays contain only a self-contained plain-English question matching the selected skill without formulas or answer hints. Problem questions may include mathematical inputs needed to solve them. Do not repeat the central expression in the back arrays. Array order is reading order. Each entry uses one of these three reusable forms:

- A question string contains plain English only: "What does set membership mean?" Flashcard questions use exactly one complete string and explicitly name the mathematical objects. Back-side prose always uses paragraph parts: {"parts":["A concise statement in words."]}. Never put TeX commands, dollar delimiters, powers, subscripts, equalities or mathematical notation in a prose string.
- Standalone mathematics: {"latex":"x \\in A","page":4,"variant":null}. Use this for source expressions, generated problem inputs or derived steps that need their own block. For source content, page identifies the printed expression; for generated content, it identifies the supporting method. See section 7 for variant rules.
- A paragraph mixing words and inline mathematics: {"parts":["The coefficient ",{"math":"\\binom{n}{m}"}," counts unordered selections."]}. Parts are alternating prose strings and {"math":"<LaTeX>"} objects. The app supplies delimiters. Include every variable, operator, factorial, power and mathematical fragment in a math object, not in a prose part. Keep spaces around fragments in the adjacent prose. Inline fragments do not need a duplicate source citation; the item's central formula supplies it.

Paragraph parts are joined exactly as written, without inserted spaces. Keep consecutive ordinary sentences in one prose part, including their spaces. When separate prose parts are necessary, include the space between words or sentences explicitly; never return adjacent parts that join into text such as "set.The".

The example page is illustrative; always use the actual ORIGINAL primary PDF page from the attachment mapping. The server adds document IDs, display settings and optional empty citation fields. Do not output kind, text, source, document_id, line numbers, quote, goal_step, plan, HTML or Markdown fences. Do not repeat JSON keys. Do not output unused optional material.

Separate mathematics from the prose around it. For a numbered list, use a prose string for the number/explanation and a formula object for each expression. Never place TeX commands or math delimiters in titles or variant change descriptions. Use plain English titles such as "Set membership" rather than a title containing TeX. Prefer words such as "the set" when this avoids unnecessary fragments. A problem's answer or a flashcard's from_notes/explanation array may be prose-only because the app supplies the central formula. Keep source quotations only in from_notes and AI-added reasoning only in explanation on flashcards. Do not duplicate the central formula with a trailing comma/period, an aligned wrapper or an added "Formally" paragraph. Additional mathematical steps must add information.

A complete illustrative flashcard is:
{"title":"Set membership","formula":{"latex":"x \\in A","page":4,"variant":null},"skill":"recall","question":["How do you write that an object belongs to a set?"],"answer":[],"from_notes":[],"explanation":[{"parts":["Use the membership relation between the object and the set."]}]}

Here the literal central formula supplies all source content, so from_notes is empty; the extra prose is explicitly AI-added explanation. When the source also states a relevant definition or qualification, quote or closely transcribe it in from_notes instead of inventing it. An explanation may also be empty when no additional context is needed.

The formula field is never a string, null, or an empty placeholder. For a mathematical item it contains the relevant expression actually visible in its source. For a definition, geometric rule or supporting problem method given only in prose/a diagram, use a PAGE-ONLY reference: {"page":4}. On a flashcard, put the source statement in from_notes and any short added context in explanation; on a problem, explain it in answer paragraphs. Do not manufacture a LaTeX formula. Never invent "Vector = magnitude + direction", wrap a prose definition in a text command, or add an equality absent from the PDF. The app shows a page-only item's source link on its answer side.

### Source transcription is authoritative

Inspect the PDF PAGE IMAGE as well as its text. A text layer can omit overbars, arrows and vector accents drawn as separate graphic strokes. Preserve their exact scope: a bar over one letter, a double bar, or a bar spanning a whole compound expression are different. Never replace overbars with a negation symbol, or an ampersand with a wedge, just because they are equivalent in a familiar textbook.

If extracted text contains missing operators, broken indices, glyph identifiers or character-code fragments, use the page image to recover the printed expression. Do not copy those artifacts as mathematical content, spell command names as words, or delete a sign to fit a prose string. If the expression remains unreadable, choose another supported target. Mathematical fragments in source excerpts also belong in math objects, with the surrounding words in prose parts. This preserves the quotation's meaning without forcing its symbols through plain-English text.

For example, a paragraph explaining an induction step can use {"parts":["Assume ",{"math":"P(n)"}," and prove ",{"math":"P(n+1)"}," for an arbitrary integer ",{"math":"n\\geq n_0"},"."]}. Membership uses {"parts":["We write ",{"math":"x\\in A"}," when the object belongs to the set."]}. These demonstrate encoding only: quote their wording or expressions as source content only when visible on the selected page. Keep complete operators, braces and index groups inside each math object. Prefer one coherent fragment to many single-character fragments, and use standalone blocks for multi-step derivations.

When transcribing the central reference formula or a variant's original expression, keep the source's letters and case, operators, typography, parentheses, fractions, row boundaries and truth-table entries. Do not normalize these source transcriptions to a preferred notation, add simplifying equalities, insert parentheses that are absent, or rename an operation from memory. A problem's question should use an original analogous task as described in section 7; its central reference formula stays literal, and its derivation/result belongs separately in the answer. Verify a logical answer against the actual truth values of the stated instance; do not confuse names of operations. If a source symbol or overbar is unclear, choose another readable source expression rather than guess.

Treat exercise labels and options as layout, not mathematical operands. Separate rows labelled (P), (F), (G), (R), A/B/C/D and numbered options; do not concatenate them into an invented equation or one unstructured line. A worksheet's blank or unfinished relation is not a complete answer: use a coherent visible source expression as the central formula and explain the completed result separately. Do not introduce an ellipsis as a placeholder for an answer. Reproduce an ellipsis only when it is genuinely part of the source formula.

## 2. TeX versus JSON escaping

The latex field is TeX encoded inside a JSON string. JSON must escape every backslash. Write TWO backslashes in the JSON source to represent ONE TeX backslash. Write FOUR backslashes in JSON to represent the TWO TeX backslashes used for an aligned or matrix row break.

| Intended TeX after JSON decoding | Valid JSON latex string |
| --- | --- |
| x \in A | "x \\in A" |
| \frac{a}{b} | "\\frac{a}{b}" |
| \{1,2\} | "\\{1,2\\}" |
| \begin{aligned}a&=b+c\\d&=e-f\end{aligned} | "\\begin{aligned}a&=b+c\\\\d&=e-f\\end{aligned}" |

A single JSON backslash before in, frac, text, begin or a brace is wrong: it may be invalid JSON or decode into a control character such as a tab/form-feed. Do not double-escape a second time: the decoded TeX must contain one command backslash, not two. TeX row breaks are the intentional exception. JSON newline escapes are not mathematical row breaks.

## 3. Self-contained expressions

Put only the expression in latex/math, without $, $$, \(, \), \[, \], equation wrappers, surrounding backticks, HTML or HTML entities. Write the source ampersand as \\& in JSON, never &amp;. A bare & is only an alignment separator inside an environment; a visible ampersand is \&. Every expression must render independently using the supported LaTeX math subset in KaTeX, trust disabled and strict errors enabled. Do not depend on a macro, package, label, environment or brace opened in another block. Balance every brace and match every environment. Do not include document preambles, usepackage, def, newcommand, label/ref, includegraphics, href, html commands, external resources or custom macros. Expand a source macro into supported standard commands while preserving its displayed notation.

TeX braces group content invisibly: x_{n+1}, a^{2k}, \frac{a+b}{c+d}. Use \{ and \} for visible set braces. Group every multi-character index, exponent, numerator and denominator. Do not replace stacked fractions with a slash, or an original slash with a stacked fraction. Use \sqrt{x} and \sqrt[n]{x} for source radicals. Use \binom{n}{k} for a source binomial coefficient.

## 4. Symbols, fonts, operators and spacing

Preserve the exact source symbols and meaning: \in versus \notin, \subset versus \subseteq, \cup versus \cap, \setminus, \emptyset, \leq, \geq, \neq, \to, \implies, \iff and quantifiers. Do not normalize the source's subset convention or choose a preferred equivalent notation. Preserve prime marks, signs, accents, dots and overbars: A', \bar{x}, \overline{A}, \hat{x}, \vec{v}, \dot{x} and \ldots/\cdots as appropriate.

Preserve font variants where visible: \mathbb{R}, \mathbb{N}, \mathcal{P}, \mathbf{x}, \mathrm{d}. Ordinary variables use normal math italics. Use supported operator names such as \sin, \cos, \log, \ln, \lim, \max and \det instead of italic letter products. Use \operatorname{rank} for an operator lacking a built-in command. Do not use \mathbb for unsupported arbitrary words.

Use \text{...} only for short mathematical labels or conditions, for example a cases condition. Put questions, exercise numbers, headings and explanatory sentences in prose strings. Ordinary spaces in TeX do not preserve PDF layout; use mathematical structure, not padding with dozens of spaces. Use small explicit spaces such as \, or \quad only where the source calls for them. Do not invent fixed-width boxes, repeated commands, negative spacing hacks, or enormous dimensions to imitate a page.

## 5. Delimiters and mathematical rows

Match parentheses, brackets and visible braces. Use \left( ... \right), \left[ ... \right] or \left\{ ... \right\} when the source uses scalable delimiters. Every \left needs its own \right in the SAME mathematical row; an invisible delimiter is \left. or \right. only when the source needs it. Do not pair delimiters across a row break. Use \lvert x\rvert and \lVert v\rVert for source absolute values and norms when appropriate.

Use supported aligned environments for multiple mathematical rows. The decoded TeX
\begin{aligned}a&=b+c\\d&=e-f\end{aligned}
has an explicit two-backslash row break and alignment markers. Do not concatenate independent rows into one formula or substitute prose newlines for row breaks. Preserve source line structure when transcribing it; split genuinely independent source formulas into separate objects.

Use matrix, pmatrix, bmatrix or vmatrix for the corresponding source matrix/determinant. Separate columns with & and rows with a two-backslash TeX row break. Example decoded TeX: \begin{pmatrix}a&b\\c&d\end{pmatrix}. For a piecewise definition use cases, for example \begin{cases}x^2&\text{if }x\geq0\\-x&\text{if }x<0\end{cases}. Apply the JSON backslash rules from section 2 to every example.

## 6. Sums, products, integrals and bounds

Attach lower and upper limits to the correct operator: \sum_{i=1}^{n}a_i, \prod_{i=1}^{n}a_i, \bigcup_{i=1}^{n}A_i, \bigcap_{i=1}^{n}A_i, \int_{a}^{b}f(x)\,\mathrm{d}x. These are examples of supported structure, not permission to substitute notation. Preserve the source's order of factors, differential notation, limit positioning and line breaks. Use \limits or \nolimits only if needed to match the source. Do not collapse several source sums, set operations or equations into one long unstructured line.

## 7. Citations and deliberate quiz variants

Every formula object needs its ORIGINAL primary PDF page. A reduced attachment may start at original page 5, so attachment page 1 is not necessarily citation page 1. Cite only selected primary pages. Do not invent quotes or line coordinates. Context attachments supply examples, not replacement authoritative citations.

For problems, preserve a relevant central reference formula verbatim, or use a page-only reference to a method stated in words. Construct a new analogous task using that method; copying the exercise or changing only its constants, names or wording is insufficient. New givens and correct derivations may contain expressions absent from the PDF. Source fidelity constrains quoted material; method fidelity constrains generated problems.

For independently generated question inputs and derived steps, use the supporting original page and variant null. These citations identify method support, not literal source quotations. Do not invent an original expression for an independently constructed task. Explain the method support briefly on the answer side using existing paragraph parts; do not add output fields.

Only a direct edit of an actual source expression uses a non-null variant: {"original":"<unmodified source TeX>","change":"<plain-English precise edit>"}. Both original and latex follow the same JSON/TeX rules and must render independently. Preserve notation except for the intentional edit. An edit may accompany a substantive new task, but a numerical edit alone does not satisfy problem novelty. Unchanged source references keep variant null. Flashcards do not need artificial exercise variations. Never put TeX inside change or reveal solution hints in the question.

## 8. Final silent check

For flashcards, verify one learning target per card, coverage across the selected concepts, and no pair answered by the same fact under different wording. Read each front without its back, especially proof-specific objects and conditions. Check all source excerpts against the page image and justify added inferences from supported premises. Do not treat a sufficient condition as necessary, a sufficient count as minimal, or an exercise option as a theorem. Do not remove essential reasoning merely to shorten an answer. This review stays inside the single response and is not output.

Before returning the single response, compare each transcribed expression to its page image: all bars/accents, letters, operators, table values and rows must match. Check count, original analogous problems rather than numerical-only copies, complete answers to the actual generated tasks, selected original pages, plain-English titles, explicit math objects, escaped backslashes, balanced grouping and explicit row breaks. Return each item exactly once. Do not print this checklist or a plan. Do not add duplicate expressions or empty blocks to increase output length. If source material is insufficient, use insufficient_source rather than manufacture content.
