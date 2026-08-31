"""Deterministic display-formula parsing and rendering helpers."""

from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
import re
from typing import List, Optional, Tuple

from matplotlib.font_manager import FontProperties
from matplotlib.mathtext import MathTextParser, math_to_image


FORMULA_VERTICAL_PADDING = 0.08
CONTENT_BLOCK_GAP = 0.08
FORMULA_DPI = 300

_FORMULA_HINT_RE = re.compile(
    r"(?:[εαλσΔ]|epsilon|alpha|lambda|sigma|Delta|max_|[_^×≤≥])"
)
_EQUATION_LHS_RE = re.compile(
    r"(?P<lhs>(?:[εαλσΔ]|epsilon|alpha|lambda|sigma|Delta)"
    r"[^\s,;:]*)\s*=\s*"
)
_SATISFIES_RE = re.compile(r"\bsatisfies\s+", re.IGNORECASE)

_GREEK = {
    "ε": r"\epsilon",
    "alpha": r"\alpha",
    "α": r"\alpha",
    "lambda": r"\lambda",
    "λ": r"\lambda",
    "sigma": r"\sigma",
    "σ": r"\sigma",
    "Delta": r"\Delta",
    "Δ": r"\Delta",
}
_COMPARISONS = {
    "=": "=",
    "≤": r"\leq",
    "≥": r"\geq",
    "<": "<",
    ">": ">",
}
_OPERATOR_CHARS = set("()+-×*/·=≤≥<>")


@dataclass(frozen=True)
class DisplayFormula:
    prefix: str
    expression: str
    mathtext: str


@dataclass(frozen=True)
class ContentBlock:
    kind: str
    text: str
    formula: Optional[DisplayFormula] = None


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


@dataclass(frozen=True)
class _Node:
    kind: str
    value: str = ""
    left: Optional["_Node"] = None
    right: Optional["_Node"] = None


class FormulaParseError(ValueError):
    """Raised when a candidate display formula is outside the safe grammar."""


def _tokenize(expression: str) -> List[_Token]:
    tokens: List[_Token] = []
    index = 0

    while index < len(expression):
        char = expression[index]

        if char.isspace():
            index += 1
            continue

        if char in _OPERATOR_CHARS:
            kind = "paren" if char in "()" else "operator"
            tokens.append(_Token(kind, char))
            index += 1
            continue

        start = index
        brace_depth = 0
        while index < len(expression):
            current = expression[index]
            if current == "{":
                brace_depth += 1
            elif current == "}" and brace_depth:
                brace_depth -= 1
            elif (
                brace_depth == 0
                and (
                    current.isspace()
                    or current in _OPERATOR_CHARS
                )
            ):
                break
            index += 1

        value = expression[start:index]
        if not value:
            raise FormulaParseError(
                f"cannot tokenize formula at position {index}"
            )
        tokens.append(_Token("atom", value))

    tokens.append(_Token("end", ""))
    return tokens


class _FormulaParser:
    def __init__(self, expression: str):
        self.tokens = _tokenize(expression)
        self.index = 0

    def parse(self) -> _Node:
        node = self._parse_comparison()
        if self._peek().kind != "end":
            raise FormulaParseError(
                f"unexpected token {self._peek().value!r}"
            )
        return node

    def _peek(self) -> _Token:
        return self.tokens[self.index]

    def _consume(self) -> _Token:
        token = self._peek()
        self.index += 1
        return token

    def _match(self, *values: str) -> Optional[str]:
        if self._peek().value not in values:
            return None
        return self._consume().value

    def _parse_comparison(self) -> _Node:
        node = self._parse_additive()
        while self._peek().value in _COMPARISONS:
            operator = self._consume().value
            node = _Node(
                "binary",
                operator,
                node,
                self._parse_additive(),
            )
        return node

    def _parse_additive(self) -> _Node:
        node = self._parse_multiplicative()
        while self._peek().value in {"+", "-"}:
            operator = self._consume().value
            node = _Node(
                "binary",
                operator,
                node,
                self._parse_multiplicative(),
            )
        return node

    def _parse_multiplicative(self) -> _Node:
        node = self._parse_factor()

        while True:
            operator = self._match("×", "*", "·", "/")
            if operator is not None:
                node = _Node(
                    "binary",
                    operator,
                    node,
                    self._parse_factor(),
                )
                continue

            if self._peek().kind == "atom" or self._peek().value == "(":
                node = _Node(
                    "binary",
                    "implicit",
                    node,
                    self._parse_factor(),
                )
                continue

            return node

    def _parse_factor(self) -> _Node:
        unary = self._match("+", "-")
        if unary is not None:
            return _Node("unary", unary, self._parse_factor())

        if self._match("(") is not None:
            node = self._parse_comparison()
            if self._match(")") is None:
                raise FormulaParseError("unclosed parenthesis")
            return _Node("group", left=node)

        token = self._peek()
        if token.kind != "atom":
            raise FormulaParseError(
                f"expected formula atom, got {token.value!r}"
            )

        node = _Node("atom", self._consume().value)
        while self._peek().value == "(":
            self._consume()
            argument = self._parse_comparison()
            if self._match(")") is None:
                raise FormulaParseError("unclosed function argument")
            node = _Node("call", left=node, right=argument)
        return node


def _parse_script_payload(
    atom: str,
    start: int,
) -> Tuple[str, int]:
    if start >= len(atom):
        raise FormulaParseError("empty math script")

    if atom[start] == "{":
        depth = 1
        index = start + 1
        while index < len(atom):
            if atom[index] == "{":
                depth += 1
            elif atom[index] == "}":
                depth -= 1
                if depth == 0:
                    payload = atom[start + 1:index]
                    if not payload:
                        raise FormulaParseError("empty braced math script")
                    return payload, index + 1
            index += 1
        raise FormulaParseError("unclosed math script")

    index = start
    while index < len(atom) and atom[index].isalnum():
        index += 1
    if index == start:
        raise FormulaParseError("invalid math script")
    return atom[start:index], index


def _format_fragment(fragment: str) -> str:
    result: List[str] = []
    index = 0

    while index < len(fragment):
        char = fragment[index]
        if char.isspace():
            result.append(r"\,")
            index += 1
            continue
        if char == "∈":
            result.append(r"\in ")
            index += 1
            continue
        if char in _GREEK:
            result.append(_GREEK[char])
            index += 1
            continue
        if char.isalpha():
            end = index + 1
            while end < len(fragment) and fragment[end].isalpha():
                end += 1
            word = fragment[index:end]
            if word == "in":
                result.append(r"\in ")
            elif word in _GREEK:
                result.append(_GREEK[word])
            elif len(word) == 1:
                result.append(word)
            else:
                result.append(rf"\mathrm{{{word}}}")
            index = end
            continue
        if char.isdigit() or char in {"'", ".", ","}:
            result.append(char)
            index += 1
            continue
        raise FormulaParseError(
            f"unsupported math-script character {char!r}"
        )

    return "".join(result)


def _format_atom(atom: str) -> str:
    script_index = min(
        (
            index
            for index, char in enumerate(atom)
            if char in {"_", "^"}
        ),
        default=len(atom),
    )
    base = atom[:script_index]
    if not base:
        raise FormulaParseError("formula atom has no base")

    if base == "max":
        result = r"\max"
    elif base in _GREEK:
        result = _GREEK[base]
    elif re.fullmatch(r"\d+(?:\.\d+)?", base):
        result = base
    elif len(base) == 1 and base.isalnum():
        result = base
    elif base.isalpha():
        result = rf"\mathrm{{{base}}}"
    else:
        raise FormulaParseError(f"unsupported formula atom {base!r}")

    index = script_index
    while index < len(atom):
        marker = atom[index]
        if marker not in {"_", "^"}:
            raise FormulaParseError(
                f"unexpected formula atom suffix {atom[index:]!r}"
            )
        payload, index = _parse_script_payload(atom, index + 1)
        result += marker + "{" + _format_fragment(payload) + "}"

    return result


def _node_precedence(node: _Node) -> int:
    if node.kind != "binary":
        return 5
    if node.value in _COMPARISONS:
        return 1
    if node.value in {"+", "-"}:
        return 2
    return 3


def _render_fraction_part(node: _Node) -> str:
    if node.kind == "group" and node.left is not None:
        return _render_node(node.left)
    return _render_node(node)


def _render_node(node: _Node, parent_precedence: int = 0) -> str:
    if node.kind == "atom":
        return _format_atom(node.value)

    if node.kind == "group" and node.left is not None:
        return rf"\left({_render_node(node.left)}\right)"

    if node.kind == "call" and node.left is not None and node.right is not None:
        return (
            _render_node(node.left, 5)
            + rf"\left({_render_node(node.right)}\right)"
        )

    if node.kind == "unary" and node.left is not None:
        return node.value + _render_node(node.left, 4)

    if node.kind != "binary" or node.left is None or node.right is None:
        raise FormulaParseError("incomplete formula expression")

    precedence = _node_precedence(node)
    if node.value == "/":
        rendered = (
            rf"\frac{{{_render_fraction_part(node.left)}}}"
            rf"{{{_render_fraction_part(node.right)}}}"
        )
    else:
        operator = {
            "×": r"\times",
            "*": r"\times",
            "·": r"\times",
            "implicit": r"\,",
            "+": "+",
            "-": "-",
            **_COMPARISONS,
        }[node.value]
        rendered = (
            f"{_render_node(node.left, precedence)} "
            f"{operator} "
            f"{_render_node(node.right, precedence + 1)}"
        )

    if precedence < parent_precedence:
        return rf"\left({rendered}\right)"
    return rendered


@lru_cache(maxsize=256)
def expression_to_mathtext(expression: str) -> str:
    """Convert the safe inline formula grammar to Matplotlib mathtext."""

    value = expression.strip()
    terminal_period = value.endswith(".")
    if terminal_period:
        value = value[:-1].rstrip()

    value = value.replace(r"\cdot", "×").replace(r"\times", "×")
    node = _FormulaParser(value).parse()
    rendered = _render_node(node)
    if terminal_period:
        rendered += "."

    mathtext = f"${rendered}$"
    MathTextParser("agg").parse(
        mathtext,
        dpi=72,
        prop=FontProperties(size=12),
    )
    return mathtext


def extract_display_formula(line: str) -> Optional[DisplayFormula]:
    """Extract a slash-based formula that should use stacked fractions."""

    value = str(line).strip()
    if "/" not in value or not _FORMULA_HINT_RE.search(value):
        return None

    equation_match = _EQUATION_LHS_RE.search(value)
    if equation_match is not None:
        formula_start = equation_match.start("lhs")
    else:
        satisfies_match = _SATISFIES_RE.search(value)
        if satisfies_match is None:
            return None
        formula_start = satisfies_match.end()

    prefix = value[:formula_start].strip()
    expression = value[formula_start:].strip()
    try:
        mathtext = expression_to_mathtext(expression)
    except (FormulaParseError, ValueError):
        return None

    return DisplayFormula(
        prefix=prefix,
        expression=expression,
        mathtext=mathtext,
    )


def split_content_blocks(text: str) -> List[ContentBlock]:
    """Group plain text lines around independently rendered formulas."""

    blocks: List[ContentBlock] = []
    pending_text: List[str] = []

    def flush_text() -> None:
        if not pending_text:
            return
        blocks.append(
            ContentBlock(
                kind="text",
                text="\n".join(pending_text),
            )
        )
        pending_text.clear()

    for line in str(text).split("\n"):
        formula = extract_display_formula(line)
        if formula is None:
            pending_text.append(line)
            continue

        flush_text()
        blocks.append(
            ContentBlock(
                kind="formula",
                text=line,
                formula=formula,
            )
        )

    flush_text()
    return blocks


@lru_cache(maxsize=256)
def measure_formula(
    mathtext: str,
    font_size: float,
    max_width_inches: float,
) -> Tuple[float, float]:
    """Measure a display formula in inches, shrinking only to fit width."""

    # math_to_image uses the path parser to determine its exact canvas.
    parsed = MathTextParser("path").parse(
        mathtext,
        dpi=72,
        prop=FontProperties(size=font_size),
    )
    natural_width = parsed.width / 72
    natural_height = parsed.height / 72
    scale = min(
        1.0,
        max_width_inches / max(natural_width, 0.01),
    )
    return natural_width * scale, natural_height * scale


@lru_cache(maxsize=128)
def render_formula_png(
    mathtext: str,
    font_size: float,
    color: str,
) -> bytes:
    """Render a tightly cropped, high-resolution display formula PNG."""

    output = BytesIO()
    math_to_image(
        mathtext,
        output,
        prop=FontProperties(size=font_size),
        dpi=FORMULA_DPI,
        format="png",
        color=color,
    )
    return output.getvalue()
