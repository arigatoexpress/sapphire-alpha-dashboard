/**
 * Remove comments from TypeScript/TSX source, leaving string literals intact.
 *
 * The source-rule tests forbid certain names from appearing in the desk's code.
 * Those same names belong in the comments that explain why they were removed —
 * "this used to read `load_band`" is exactly the note a future reader needs.
 * So the scan runs over code with the prose taken out.
 *
 * This is a scanner, not a parser. It knows about `//`, block comments and the
 * three kinds of string literal. It does **not** know about regular-expression
 * literals, which would be mistaken for division followed by other tokens; the
 * desk source contains none, and `stripComments` is itself unit-tested so a
 * future one fails visibly rather than quietly hiding a violation.
 */
export function stripComments(source: string): string {
  let out = ''
  let index = 0

  while (index < source.length) {
    const char = source[index]
    const next = source[index + 1]

    if (char === '/' && next === '/') {
      while (index < source.length && source[index] !== '\n') index += 1
      continue
    }

    if (char === '/' && next === '*') {
      index += 2
      while (index < source.length && !(source[index] === '*' && source[index + 1] === '/')) {
        index += 1
      }
      index += 2
      continue
    }

    if (char === '"' || char === "'" || char === '`') {
      const quote = char
      out += char
      index += 1
      while (index < source.length) {
        if (source[index] === '\\') {
          out += source[index] + (source[index + 1] ?? '')
          index += 2
          continue
        }
        out += source[index]
        const closed = source[index] === quote
        index += 1
        if (closed) break
      }
      continue
    }

    out += char
    index += 1
  }

  return out
}
