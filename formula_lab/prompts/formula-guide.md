# Formula-writing guide

## 1. Response and block structure

Return the schema's result with status "completed" and exactly the requested number of items. Each item has a plain-English title, a REQUIRED central formula object, a question array and an answer array. The central formula is the literal source expression the item teaches or uses, not a reconstructed summary of its meaning. The app displays it on the answer side for both modes, never on the flashcard front. Flashcard question arrays contain only a self-contained plain-English recall question without formulas or answer hints; all answer content belongs in the central formula and answer array. Problem questions may include mathematical inputs needed to solve them. Do not repeat the central expression in the answer array. Array order is reading order. Each entry uses one of these three reusable forms:

- A question string contains plain English only: "Explain the meaning of this relation." Flashcard questions use exactly one complete string. Answer prose always uses paragraph parts: {"parts":["A concise explanation in words."]}. Never put TeX commands, dollar delimiters, powers, subscripts, equalities or mathematical notation in a prose string.
- Standalone source mathematics: {"latex":"x \\in A","page":4,"variant":null}. Use this for an expression, table, matrix or multiple mathematical rows that need their own citation.
- A paragraph mixing words and inline mathematics: {"parts":["The coefficient ",{"math":"\\binom{n}{m}"}," counts unordered selections."]}. Parts are alternating prose strings and {"math":"<LaTeX>"} objects. The app supplies delimiters. Include every variable, operator, factorial, power and mathematical fragment in a math object, not in a prose part. Keep spaces around fragments in the adjacent prose. Inline fragments do not need a duplicate source citation; the item's central formula supplies it.

The example page is illustrative; always use the actual ORIGINAL primary PDF page from the attachment mapping. The server adds document IDs, display settings and optional empty citation fields. Do not output kind, text, source, document_id, line numbers, quote, goal_step, plan, HTML or Markdown fences. Do not repeat JSON keys. Do not output unused optional material.

Separate mathematics from the prose around it. For a numbered list, use a prose string for the number/explanation and a formula object for each expression. Never place TeX commands or math delimiters in titles or variant change descriptions. Use plain English titles such as "Set membership" rather than a title containing TeX. Prefer words such as "the set" when this avoids unnecessary fragments. An answer array may be prose-only because the app supplies the central formula. Do not duplicate that formula with a trailing comma/period, an aligned wrapper or an added "Formally" paragraph. Additional mathematical steps must add information.

A complete illustrative item is:
{"title":"Set membership","formula":{"latex":"x \\in A","page":4,"variant":null},"question":["How do you write that an object belongs to a set?"],"answer":[{"parts":["Use the membership relation between the object and the set."]}]}

The formula field is never a string, null, or an empty placeholder. For a mathematical item it contains the relevant expression actually visible in its source. For a definition or geometric rule given only in prose/a diagram, use a PAGE-ONLY reference: {"page":4}. Explain it in answer paragraphs without manufacturing a LaTeX formula. Never invent "Vector = magnitude + direction", wrap a prose definition in a text command, or add an equality absent from the PDF. The app shows a page-only item's source link on its answer side.

### Source transcription is authoritative

Inspect the PDF PAGE IMAGE as well as its text. A text layer can omit overbars, arrows and vector accents drawn as separate graphic strokes. Preserve their exact scope: a bar over one letter, a double bar, or a bar spanning a whole compound expression are different. Never replace overbars with a negation symbol, or an ampersand with a wedge, just because they are equivalent in a familiar textbook.

Keep the source's letters and case, operators, typography, parentheses, fractions, row boundaries and truth-table entries. Do not normalize to a preferred notation, add simplifying equalities, insert parentheses that are absent, or rename an operation from memory. If asked to solve an exercise, keep its source expression literal and put the derivation/result separately in the answer. Verify a logical answer against the actual truth values; do not confuse names of operations. If a symbol or overbar is unclear, choose another readable source expression rather than guess.

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

Normally variant is null. If a quiz intentionally changes a source formula, use variant: {"original":"<unmodified source TeX>","change":"<plain-English precise edit>"}. Both original and latex follow the same JSON/TeX rules and must render independently. Keep the original notation except for the intended edit; explain the difference on the answer side without revealing it in the question. A variant is not permission to invent an unrelated formula. Never put TeX inside change.

## 8. Final silent check

Before returning the single response, compare each transcribed expression to its page image: all bars/accents, letters, operators, table values and rows must match. Check count, varied questions, complete answers, selected original pages, plain-English titles, explicit math objects, escaped backslashes, balanced grouping and explicit row breaks. Return each item exactly once. Do not print this checklist or a plan. Do not add duplicate expressions or empty blocks to increase output length. If source material is insufficient, use insufficient_source rather than manufacture content.
