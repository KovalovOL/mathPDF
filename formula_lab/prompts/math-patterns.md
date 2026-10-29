# Reusable LaTeX structures

These are STRUCTURE examples, not a formula catalog or substitute for the source. Reuse the container appropriate to any topic. For source references and quotations, transcribe contents from the selected page image and never replace the source's symbols with those in an example. For original problem inputs and derived solution steps, fill the container with the new task's valid mathematics using source-supported methods and notation; these expressions need not be printed in the source. Cite the supporting method page, use variant null unless directly editing a source expression, and do not present generated mathematics as a quotation. The examples below show JSON, so every LaTeX backslash is doubled.

## Inline mathematics inside ordinary sentences

Use an explicit math part for each mathematical fragment. This applies equally to sets, logic, vectors, calculus and other topics:

{"parts":["The coefficient ",{"math":"\\binom{n}{m}"}," counts selections of ",{"math":"m"}," elements."]}
{"parts":["The implication ",{"math":"P \\Rightarrow Q"}," is false only for a true hypothesis and false conclusion."]}
{"parts":["The intersection is ",{"math":"A \\cap B"},"."]}

Avoid repeating the central equation in prose. A concise explanation in words alone is usually sufficient.

## Overbars and source operators

Copy the exact bar scope and operator. These are different source structures:

{"math":"\\bar{w} \\Leftrightarrow 0"}
{"math":"\\overline{u \\vee \\bar{p}}"}
{"math":"\\overline{\\bar{w}}"}
{"math":"s \\& x \\Rightarrow r \\vee y"}

If the PDF uses & for conjunction, retain \\&; do not substitute \\land. If it uses a bar, retain the bar; do not substitute \\neg. Preserve \\Rightarrow versus \\rightarrow, \\Leftrightarrow versus \\equiv, \\subset versus \\subseteq, and bold/vector-arrow notation as printed. Never put &amp; in LaTeX.

## Rows and labelled alternatives

A multi-row expression uses aligned with explicit row breaks. Labels stay short, separate from the mathematics:

{"latex":"\\begin{aligned}\\text{(P)}\\quad&1\\Rightarrow p\\\\\\text{(F)}\\quad&0\\vee\\bar{p}\\end{aligned}","page":2,"variant":null}

Copy the real labels and accents from the selected page. Do not concatenate labelled alternatives as `(P)1 => p; (F)0 or p` or add an equality between them. Keep separately cited source expressions in separate formula objects.

In an aligned Boolean expression, a VISIBLE conjunction ampersand must still be escaped. Only the alignment marker is bare. For example, if these exact rows and accents are printed in the source:

{"latex":"\\begin{aligned}t \\& \\bar{t}&\\Leftrightarrow 0\\\\t \\& t&\\Leftrightarrow t\\end{aligned}","page":2,"variant":null}

Here `\\&` in JSON prints the source ampersand; `&` before the relation aligns the rows. Writing `t&t` inside aligned consumes the conjunction as a column separator. Inline explanations must likewise use math parts, for example {"parts":["The source conjunction is ",{"math":"t \\& t \\Leftrightarrow t"},"."]}. Never omit an overbar or infer one from this example.

## Tables, matrices and cases

A truth table uses array. Preserve its header, truth values, row order and the exact source separator rules:

{"latex":"\\begin{array}{c|c|c}u&z&u\\ast z\\\\\\hline 0&0&1\\\\0&1&0\\\\1&0&0\\\\1&1&0\\end{array}","page":2,"variant":null}

The same array structure can represent tabular formulas from other topics. Matrix delimiters use the matching source container: matrix (no surrounding brackets), pmatrix (parentheses), bmatrix (square brackets), vmatrix (determinant bars). Piecewise expressions use cases. Do not add brackets or table rules absent from the source.

## Fractions, binomial coefficients, sums and accents

{"math":"\\binom{n}{m}=\\frac{P(n,m)}{m!}=\\frac{n!}{m!(n-m)!}"}
{"math":"(x+y)^n=\\sum_{k=0}^{n}\\binom{n}{k}x^{n-k}y^k"}
{"math":"\\overrightarrow{AB}"}

These show supported structures only. Copy the original letters, indices, order, font variants, visible spacing and punctuation; do not insert a more familiar equivalent. For a proof with several lines, preserve those lines instead of flattening them. For a printed slash fraction, keep the slash rather than introducing a stacked fraction.

A chained equality must keep its original order. If the source has `a=b=c`, copying `a=c=b` is not faithful even when equivalent. In particular, a product followed by a factorial fraction must stay in that order; do not move the fraction ahead of the product. Likewise preserve the source's grouping and accents instead of adding more familiar parentheses or replacing an overbar with a negation sign.

## Incomplete exercises and non-formula material

An exercise blank, answer-option list, diagram or prose definition is not a license to invent a central formula. Copy a complete readable source expression or coherent mathematical subexpression, and put a solved result separately in the answer. Do not append an invented equality or "...". If the source has only a prose definition or a geometric rule, use a page-only reference, for example {"page":4}, and an answer paragraph. Never manufacture `Vector = magnitude + direction` or wrap that prose in a LaTeX text command.

A complete prose-only example (use the actual source page, not this illustrative number):

{"title":"Vector equality","formula":{"page":6},"skill":"conditions","question":["What conditions make two vectors equal?"],"answer":[],"from_notes":[{"parts":["Two vectors are equal when their direction and magnitude are the same."]}],"explanation":[]}

Use that from_notes wording only if it is stated verbatim or near-verbatim on the actual source page. Put any short AI-added interpretation or worked reasoning in explanation instead; never present it as source text.

## Source exercises are questions, not asserted facts

Multiple-choice options and labelled expressions may intentionally be false. Their presence in a PDF does not make them theorems or correct answers. Check the actual exercise before explaining it. Keep the copied expression unchanged while assessing it.

For Boolean exercises, silently evaluate truth values: implication from true has the value of its conclusion, so `1 implies p` is not a tautology; disjunction with false has the other operand's value. A variable OR its negation is excluded middle; this is not double negation. Double negation removes two negations. NOR is true only for two false inputs; NAND is false only for two true inputs. Apply contraposition by negating the ENTIRE conclusion and hypothesis, accounting for any existing overbars. These are checking principles, not permission to replace the source's printed operators or accents.
