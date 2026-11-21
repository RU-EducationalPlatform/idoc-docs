#!/usr/bin/env python3
"""Convert Deng2025_Hilbert6th/main.tex → main.idoc (one-shot paper converter)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEX = ROOT / "main.tex"
OUT = ROOT / "main.idoc"

# Custom preamble macros → IDoc math (no backslash for known cmds).
# Use (?![A-Za-z]) not \b so \vz_N / \Dc_N still expand (\b treats _ as word).
MACROS: list[tuple[str, str]] = [
    (r"\\newterm\{([^{}]*)\}", r"@b{\1}"),
    (r"\\Ps(?![A-Za-z])", r"mathscr{P}"),
    (r"\\jb(?![A-Za-z])", r"mathbf{j}"),
    (r"\\pb(?![A-Za-z])", r"mathbf{p}"),
    (r"\\rb(?![A-Za-z])", r"mathbf{r}"),
    (r"\\supp(?![A-Za-z])", r"mathrm{supp}\\,"),
    (r"\\Dirac(?![A-Za-z])", r"mathbf{Delta}"),
    (r"\\dirac(?![A-Za-z])", r"mathbf{delta}"),
    (r"\\mathbbm\{1\}", r"mathbf{1}"),
    (r"\\mathbbm\{([A-Za-z0-9])\}", r"mathbb{\1}"),
]
for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    MACROS.append((rf"\\{letter}b(?![A-Za-z])", rf"mathbb{{{letter}}}"))
    MACROS.append((rf"\\{letter}c(?![A-Za-z])", rf"mathcal{{{letter}}}"))
    if letter not in "BIR":  # avoid \Bf/\If/\Rf colliding with font switches later
        MACROS.append((rf"\\{letter}f(?![A-Za-z])", rf"mathfrak{{{letter}}}"))
# lowercase fraktur — exclude font switches bf/it/rm/sf/sc/sl/em/tt
_FONT_SWITCHES = {"bf", "it", "rm", "sf", "sc", "sl", "em", "tt", "cal", "mit"}
for letter in "abcdefghijklmnopqrstuvwxyz":
    name = f"{letter}f"
    if name in _FONT_SWITCHES or letter == "b":  # \bf
        continue
    if name in ("if",):  # nonsense
        continue
    MACROS.append((rf"\\{letter}f(?![A-Za-z])", rf"mathfrak{{{letter}}}"))
# explicit fraktur that we skipped
MACROS.append((r"\\Bf(?![A-Za-z])", r"mathfrak{B}"))
MACROS.append((r"\\Rf(?![A-Za-z])", r"mathfrak{R}"))
MACROS.append((r"\\If(?![A-Za-z])", r"mathfrak{I}"))
# special fraktur / script / bold overrides that collide with letter loops
MACROS.extend(
    [
        (r"\\sff(?![A-Za-z])", r"mathfrak{s}"),
        (r"\\Fs(?![A-Za-z])", r"mathscr{F}"),
        (r"\\As(?![A-Za-z])", r"mathscr{A}"),
        (r"\\Hs(?![A-Za-z])", r"mathscr{H}"),
        (r"\\vz(?![A-Za-z])", r"mathbf{z}"),
        (r"\\vm(?![A-Za-z])", r"mathbf{m}"),
        (r"\\vw(?![A-Za-z])", r"mathbf{w}"),
        (r"\\vf(?![A-Za-z])", r"mathbf{f}"),
        (r"\\vg(?![A-Za-z])", r"mathbf{g}"),
        (r"\\vLambda(?![A-Za-z])", r"mathbf{Lambda}"),
        (r"\\vF(?![A-Za-z])", r"mathbf{F}"),
        (r"\\vZ(?![A-Za-z])", r"mathbf{Z}"),
        (r"\\vH(?![A-Za-z])", r"mathbf{H}"),
        (r"\\vt(?![A-Za-z])", r"mathbf{t}"),
        (r"\\vD(?![A-Za-z])", r"mathbf{D}"),
        (r"\\ef(?![A-Za-z])", r"mathfrak{e}"),
        (r"\\Eb(?![A-Za-z])", r"mathbb{E}"),
        (r"\\Pb(?![A-Za-z])", r"mathbb{P}"),
        (r"\\Sb(?![A-Za-z])", r"mathbb{S}"),
        (r"\\Zb(?![A-Za-z])", r"mathbb{Z}"),
        (r"\\Rb(?![A-Za-z])", r"mathbb{R}"),
        (r"\\Tb(?![A-Za-z])", r"mathbb{T}"),
        (r"\\Nb(?![A-Za-z])", r"mathbb{N}"),
        (r"\\Hb(?![A-Za-z])", r"mathbb{H}"),
        (r"\\Wb(?![A-Za-z])", r"mathbb{W}"),
        (r"\\Cb(?![A-Za-z])", r"mathbb{C}"),
    ]
)

# Known math commands to strip leading \
# Binary/relational ops get surrounding spaces so `v\cdot\nabla` → `v cdot nabla`.
MATH_BINOPS = {
    "cdot", "times", "pm", "mp", "oplus", "otimes", "ominus", "oslash",
    "leq", "geq", "neq", "approx", "equiv", "sim", "simeq", "propto", "ll", "gg",
    "subset", "supset", "subseteq", "supseteq", "in", "ni", "notin", "mapsto",
    "to", "rightarrow", "leftarrow", "Rightarrow", "Leftarrow", "leftrightarrow",
    "hookrightarrow", "longrightarrow", "longleftarrow", "Leftrightarrow",
    "iff", "implies", "impliedby", "land", "lor", "cap", "cup", "wedge", "vee",
    "setminus", "circ", "bullet", "ast", "star", "dagger", "ddagger",
    "prec", "succ", "preceq", "succeq", "gtrsim", "lesssim", "cong", "asymp",
    "models", "vdash", "dashv", "perp", "parallel", "mid",
    "lessapprox", "gtrapprox", "eqsim", "thicksim", "lless", "ggg", "lll", "doteq",
}
MATH_CMDS = {
    "frac", "dfrac", "tfrac", "sqrt", "sum", "prod", "int", "iint", "iiint", "oint",
    "partial", "nabla", "infty",
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta",
    "theta", "vartheta", "iota", "kappa", "lambda", "mu", "nu", "xi", "pi",
    "varpi", "rho", "varrho", "sigma", "varsigma", "tau", "upsilon", "phi",
    "varphi", "chi", "psi", "omega", "Gamma", "Delta", "Theta", "Lambda",
    "Xi", "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega",
    "mathbb", "mathcal", "mathfrak", "mathscr", "mathbf", "mathrm", "mathit",
    "mathsf", "mathtt", "operatorname", "text", "textbf", "textit",
    "hat", "bar", "tilde", "vec", "dot", "ddot", "overline", "underline",
    "overbrace", "underbrace", "widehat", "widetilde", "overrightarrow",
    "left", "right", "big", "Big", "bigg", "Bigg", "bigl", "bigr",
    "quad", "qquad", "hspace", "vspace", "!", ",", ";", ":",
    "sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp", "det",
    "dim", "ker", "deg", "max", "min", "sup", "inf", "lim", "limsup", "liminf",
    "binom", "dbinom", "tbinom", "overset", "underset", "stackrel",
    "langle", "rangle", "lfloor", "rfloor", "lceil", "rceil",
    "Vert", "vert", "lVert", "rVert",
    "forall", "exists", "emptyset", "varnothing", "cdots", "ldots", "vdots", "ddots",
    "ell", "hbar", "imath", "jmath", "wp", "Re", "Im", "angle", "triangle",
    "square", "blacksquare", "diamond",
    "bigcirc", "amalg", "uplus",
    "lessapprox", "gtrapprox", "eqsim", "thicksim",
    "lless", "ggg", "lll", "doteq",
    "varsubsetneq", "nsubseteq", "nsupseteq", "owns",
    "twoheadrightarrow", "rightarrowtail",
    "lnot", "top", "bot", "sharp", "flat", "natural", "clubsuit",
    "subsetneq", "supsetneq",
} | MATH_BINOPS

ENV_MAP = {
    "matrix": "matrix", "pmatrix": "pmatrix", "bmatrix": "bmatrix",
    "vmatrix": "vmatrix", "Vmatrix": "Vmatrix", "smallmatrix": "smallmatrix",
    "cases": "cases", "aligned": "aligned", "gathered": "gathered", "split": "split",
    "align": "aligned", "eqnarray": "aligned", "Bmatrix": "matrix",
}


def brace_arg(s: str, i: int) -> tuple[str, int] | None:
    if i >= len(s) or s[i] != "{":
        return None
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
    return None


def opt_arg(s: str, i: int) -> tuple[str | None, int]:
    if i < len(s) and s[i] == "[":
        depth = 0
        for j in range(i, len(s)):
            if s[j] == "[":
                depth += 1
            elif s[j] == "]":
                depth -= 1
                if depth == 0:
                    return s[i + 1 : j], j + 1
    return None, i


def convert_math_envs(body: str) -> str:
    prev = None
    while prev != body:
        prev = body

        def repl(m: re.Match[str]) -> str:
            env, inner = m.group(1), m.group(2)
            name = ENV_MAP.get(env)
            if not name:
                return m.group(0)
            rows = [r.strip() for r in re.split(r"\\\\", inner) if r.strip()]
            return f"{name}{{{' ; '.join(rows)}}}"

        body = re.sub(
            r"\\begin\{([A-Za-z]+)\*?\}(?:\{[^}]*\})?([\s\S]*?)\\end\{\1\*?\}",
            repl,
            body,
        )
    return body


def latex_math_to_idoc(tex: str) -> str:
    """LaTeX math body → IDoc math (strip \\ from known cmds; match engine latex.ts)."""
    s = convert_math_envs(tex)
    s = re.sub(r"\\\\", " newline ", s)
    s = re.sub(
        r"\\(?:left|right|middle|bigl|bigr|Bigl|Bigr|biggl|biggr|Biggl|Biggr|big|Big|bigg|Bigg)\b\s*",
        "",
        s,
    )
    s = re.sub(r"\\[,;:!> ]", " ", s)
    s = re.sub(r"\\(?:quad|qquad|thinspace)\b", "  ", s)

    def strip_cmd(m: re.Match[str]) -> str:
        cmd = m.group(1)
        if cmd in MATH_BINOPS:
            return f" {cmd} "
        if cmd in MATH_CMDS:
            return cmd
        return m.group(0)

    s = re.sub(r"\\([A-Za-z]+)", strip_cmd, s)
    # \{ \} after \left/\right strip → plain braces
    s = s.replace(r"\{", "{").replace(r"\}", "}")
    # letter glued to a following greek/ops name: logvarepsilon → log varepsilon
    s = re.sub(
        r"([a-zA-Z0-9])(varepsilon|alpha|beta|gamma|delta|omega|partial|nabla|infty|mathrm|mathbb|mathcal|mathfrak)",
        r"\1 \2",
        s,
    )
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def block_math_to_idoc(body: str) -> str:
    rows = [latex_math_to_idoc(r.strip()) for r in re.split(r"\\\\", body)]
    rows = [r for r in rows if r]
    if len(rows) <= 1:
        return rows[0] if rows else ""
    return f"aligned{{{' ; '.join(rows)}}}"


def expand_macros(s: str) -> str:
    # longer names first
    for pat, repl in sorted(MACROS, key=lambda x: -len(x[0])):
        s = re.sub(pat, repl, s)
    return s


def convert_named_blocks(s: str) -> str:
    """theorem/lemma/…/proof/mainthm → @theorem … @end (mainthm → @theorem)."""
    mapping = {
        "mainthm": "theorem",
        "theorem": "theorem",
        "lemma": "lemma",
        "corollary": "corollary",
        "proposition": "proposition",
        "claim": "claim",
        "definition": "definition",
        "remark": "remark",
        "example": "example",
        "proof": "proof",
    }

    def one(env: str, idoc: str, text: str) -> str:
        out: list[str] = []
        i = 0
        open_re = re.compile(rf"\\begin\{{{env}\}}")
        close = f"\\end{{{env}}}"
        while True:
            m = open_re.search(text, i)
            if not m:
                out.append(text[i:])
                break
            out.append(text[i : m.start()])
            j = m.end()
            title, j2 = opt_arg(text, j)
            j = j2
            # optional \label{…} right after
            lab = None
            lm = re.match(r"\s*\\label\{([^}]*)\}", text[j:])
            if lm:
                lab = lm.group(1)
                j += lm.end()
            end = text.find(close, j)
            if end < 0:
                out.append(text[m.start() :])
                break
            body = text[j:end].strip()
            head = f"@{idoc}"
            args: list[str] = []
            if title:
                args.append(title.strip())
            if lab:
                args.append(f"label={lab}")
            if args:
                # if only label, use label= form; if title+label combine
                if title and lab:
                    head = f"@{idoc}({title.strip()}, label={lab})"
                elif title:
                    head = f"@{idoc}({title.strip()})"
                else:
                    head = f"@{idoc}(label={lab})"
            out.append(f"\n{head}\n{body}\n@end\n")
            i = end + len(close)
        return "".join(out)

    for env, idoc in mapping.items():
        s = one(env, idoc, s)
    return s


def convert_cite_ref(s: str) -> str:
    def cite(m: re.Match[str]) -> str:
        keys = [k.strip() for k in m.group(1).split(",") if k.strip()]
        return "@cite(" + ", ".join(keys) + ")"

    s = re.sub(r"\\cite[tp]?\{([^}]*)\}", cite, s)
    s = re.sub(r"\\eqref\{([^}]*)\}", r"@eqref(\1)", s)
    s = re.sub(r"\\ref\{([^}]*)\}", r"@ref(\1)", s)
    return s


def convert_caption_math(cap: str) -> str:
    """Inline math + refs inside a figure caption (already cite/ref-converted)."""
    cap = re.sub(
        r"\$([^$\n]+)\$",
        lambda m: f"@eqi({latex_math_to_idoc(m.group(1))})",
        cap,
    )
    cap = re.sub(
        r"\\\(([^)]*)\\\)",
        lambda m: f"@eqi({latex_math_to_idoc(m.group(1))})",
        cap,
    )
    return re.sub(r"\s+", " ", cap).strip()


def convert_figures(s: str) -> str:
    """Turn figure floats into @figure. Caption uses balanced braces (math may contain })."""

    def fig(m: re.Match[str]) -> str:
        inner = m.group(1)
        lab_m = re.search(r"\\label\{([^}]*)\}", inner)
        img_m = re.search(
            r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", inner
        )
        if not img_m:
            return inner
        f = img_m.group(1)
        args = [f"file={f}"]
        cap = None
        cm = re.search(r"\\caption\{", inner)
        if cm:
            barg = brace_arg(inner, cm.end() - 1)
            if barg:
                cap = convert_caption_math(barg[0])
                # escape quotes for @figure(caption="…")
                cap = cap.replace("\\", "\\\\").replace('"', '\\"')
                args.append(f'caption="{cap}"')
        if lab_m:
            args.append(f"label={lab_m.group(1)}")
        opt_m = re.search(r"\\includegraphics\[([^\]]*)\]", inner)
        if opt_m:
            wm = re.search(r"width\s*=\s*([^,\]]+)", opt_m.group(1))
            if wm:
                w = wm.group(1).strip()
                if "cm" in w or "in" in w or "mm" in w or w.endswith(("%", "pt")):
                    args.append(f"w={w}")
                elif w.replace(".", "").isdigit():
                    args.append(f"w={w}in")
            sm = re.search(r"scale\s*=\s*([^,\]]+)", opt_m.group(1))
            if sm and not any(a.startswith("w=") for a in args):
                try:
                    sc = float(sm.group(1))
                    args.append(f"w={int(sc * 400)}px")
                except ValueError:
                    pass
        return "\n@figure(" + ", ".join(args) + ")\n"

    return re.sub(
        r"\\begin\{figure\*?\}(?:\[[^\]]*\])?([\s\S]*?)\\end\{figure\*?\}",
        fig,
        s,
    )


def convert_equations_with_labels(s: str) -> str:
    """equation/align with \\label → @eqn(label=…)."""

    def eq_env(m: re.Match[str]) -> str:
        env, body = m.group(1), m.group(2)
        lab = None
        lm = re.match(r"\s*\\label\{([^}]*)\}", body)
        if lm:
            lab = lm.group(1)
            body = body[lm.end() :]
        # also label at end
        lm2 = re.search(r"\\label\{([^}]*)\}\s*$", body)
        if lm2 and not lab:
            lab = lm2.group(1)
            body = body[: lm2.start()]
        body = re.sub(r"\\label\{[^}]*\}", "", body)
        math = block_math_to_idoc(body)
        head = f"@eqn(label={lab})" if lab else "@eqn"
        if env in ("align", "aligned", "eqnarray", "gather", "multline", "flalign", "alignat"):
            if not math.startswith("aligned"):
                math = block_math_to_idoc(body)
        return f"\n{head}\n{math}\n@end\n"

    s = re.sub(
        r"\\begin\{(equation|align|eqnarray|gather|multline|flalign|alignat|displaymath)\*?\}([\s\S]*?)\\end\{\1\*?\}",
        eq_env,
        s,
    )
    return s


def convert_center(s: str) -> str:
    def repl(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        # \tt{…} / \texttt{…} → plain centered text (Hilbert quotations)
        tm = re.match(r"\\t(?:t|exttt)\s*\{", inner)
        if tm:
            barg = brace_arg(inner, tm.end() - 1)
            if barg:
                text, end = barg
                # TeX quirk: \tt{"….} " with closing quote outside the brace
                trail = inner[end:].strip()
                if text.startswith('"') and not text.endswith('"') and trail.startswith('"'):
                    text = text + '"'
                inner = text.strip()
        return f"\n@center\n{inner}\n@end\n"

    return re.sub(
        r"\\begin\{center\}([\s\S]*?)\\end\{center\}",
        repl,
        s,
    )


def convert_bib(s: str) -> str:
    """thebibliography → @bibliography block as plain refs list (idoc @cite keys)."""
    m = re.search(r"\\begin\{thebibliography\}.*?([\s\S]*?)\\end\{thebibliography\}", s)
    if not m:
        return s
    body = m.group(1)
    items: list[str] = []
    for bm in re.finditer(r"\\bibitem\{([^}]*)\}([\s\S]*?)(?=\\bibitem\{|\\end\{thebibliography\}|$)", body):
        key, text = bm.group(1), bm.group(2)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\\emph\{([^{}]*)\}", r"*\1*", text)
        text = re.sub(r"\\textit\{([^{}]*)\}", r"*\1*", text)
        text = re.sub(r"\\textbf\{([^{}]*)\}", r"**\1**", text)
        text = re.sub(r"\$([^$]+)\$", lambda x: f"@eqi({latex_math_to_idoc(x.group(1))})", text)
        items.append(f"@b{{[{key}]}} {text}")
    block = "\n\n@section(References)\n\n" + "\n\n".join(items) + "\n"
    return s[: m.start()] + block + s[m.end() :]


def take_cmd_brace(s: str, i: int, cmd: str) -> tuple[str, int] | None:
    m = re.match(rf"\\{cmd}\s*\{{", s[i:])
    if not m:
        return None
    arg = brace_arg(s, i + m.end() - 1)
    if not arg:
        return None
    return arg[0], arg[1]


def convert_authors_block(text: str) -> tuple[str, str, str]:
    """Return (@author lines, title, text with author/address/email/title/date removed)."""
    lines: list[str] = []
    cleaned_parts: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith(r"\author", i):
            a = take_cmd_brace(text, i, "author")
            if not a:
                cleaned_parts.append(text[i])
                i += 1
                continue
            name, j = a
            # skip whitespace
            while j < len(text) and text[j] in " \t\n":
                j += 1
            ad = take_cmd_brace(text, j, "address")
            if not ad:
                cleaned_parts.append(text[i:j])
                i = j
                continue
            addr, j = ad
            while j < len(text) and text[j] in " \t\n":
                j += 1
            em = take_cmd_brace(text, j, "email")
            if not em:
                cleaned_parts.append(text[i:j])
                i = j
                continue
            email, j = em
            name = re.sub(r"\s+", " ", name).strip()
            addr = re.sub(r"\\textsc\{([^{}]*)\}", r"\1", addr)
            addr = re.sub(r"\s+", " ", addr).strip()
            email = re.sub(r"\\texttt\{([^{}]*)\}", r"\1", email).strip()
            # strip any remaining macros in email
            email = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", email)
            lines.append(
                f'@author(name="{name}", affiliation="{addr}", email="{email}")'
            )
            i = j
            continue
        cleaned_parts.append(text[i])
        i += 1
    cleaned = "".join(cleaned_parts)
    cleaned = re.sub(r"\\date\{[\s\S]*?\}", "", cleaned)
    title = ""
    tm = re.search(r"\\title\{", cleaned)
    if tm:
        arg = brace_arg(cleaned, tm.end() - 1)
        if arg:
            title = re.sub(r"\s+", " ", arg[0]).strip()
            cleaned = cleaned[: tm.start()] + cleaned[arg[1] :]
    return "\n".join(lines), title, cleaned


def rewrite_font_groups(s: str) -> str:
    """{\\bf …} / {\\it …} / {\\em …} → \\textbf{…} etc."""
    mapping = {"bf": "textbf", "it": "textit", "em": "emph", "tt": "texttt", "sc": "textsc"}
    out: list[str] = []
    i = 0
    while i < len(s):
        m = re.match(r"\{\\(bf|it|em|tt|sc)\s+", s[i:])
        if m:
            cmd = m.group(1)
            start = i + m.end()
            depth = 1
            j = start
            while j < len(s) and depth:
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                j += 1
            inner = s[start : j - 1]
            out.append(f"\\{mapping[cmd]}{{{inner}}}")
            i = j
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def convert_abstract(s: str) -> str:
    return re.sub(
        r"\\begin\{abstract\}([\s\S]*?)\\end\{abstract\}",
        lambda m: f"\n@abstract\n{m.group(1).strip()}\n@end\n",
        s,
    )


def stash_balanced_calls(s: str, name: str, math: list[str], ph: str) -> str:
    """Stash @name(…) with balanced parentheses (captions may contain @ref(…))."""
    out: list[str] = []
    i = 0
    token = f"@{name}("
    while i < len(s):
        j = s.find(token, i)
        if j < 0:
            out.append(s[i:])
            break
        out.append(s[i:j])
        depth = 0
        k = j + len(token) - 1  # at '('
        while k < len(s):
            if s[k] == "(":
                depth += 1
            elif s[k] == ")":
                depth -= 1
                if depth == 0:
                    k += 1
                    break
            k += 1
        math.append(s[j:k])
        out.append(f"{ph}{len(math) - 1}{ph}")
        i = k
    return "".join(out)


def stash_math_passthrough(s: str) -> tuple[str, list[str]]:
    """Protect @eqn/@eqi/@figure; convert remaining display/inline math."""
    math: list[str] = []
    ph = "__M__"

    def stash(idoc: str) -> str:
        math.append(idoc)
        return f"{ph}{len(math) - 1}{ph}"

    s = re.sub(
        r"@eqn(?:\([^)]*\))?\n[\s\S]*?\n@end",
        lambda m: stash(m.group(0)),
        s,
    )
    s = stash_balanced_calls(s, "eqi", math, ph)
    s = stash_balanced_calls(s, "figure", math, ph)

    s = re.sub(
        r"\$\$([\s\S]*?)\$\$",
        lambda m: "\n" + stash(f"@eqn\n{block_math_to_idoc(m.group(1))}\n@end") + "\n",
        s,
    )
    s = re.sub(
        r"\\\[([\s\S]*?)\\\]",
        lambda m: "\n" + stash(f"@eqn\n{block_math_to_idoc(m.group(1))}\n@end") + "\n",
        s,
    )
    # Inline only — never cross newlines (stray $ from bad captions must not span).
    s = re.sub(
        r"\\\(([^\\\n]*?)\\\)",
        lambda m: stash(f"@eqi({latex_math_to_idoc(m.group(1)).strip()})"),
        s,
    )
    s = re.sub(
        r"\$([^$\n]+)\$",
        lambda m: stash(f"@eqi({latex_math_to_idoc(m.group(1)).strip()})"),
        s,
    )
    return s, math


def restore_math(s: str, math: list[str]) -> str:
    """Restore placeholders; iterate in case of accidental nesting."""
    for _ in range(8):
        nxt = re.sub(r"__M__(\d+)__M__", lambda m: math[int(m.group(1))], s)
        if nxt == s:
            break
        s = nxt
    return s


def convert_lists(s: str) -> str:
    for env, dir_ in (("itemize", "ul"), ("enumerate", "ol")):
        def repl(m: re.Match[str], d: str = dir_) -> str:
            items = [x.strip() for x in re.split(r"\\item\b", m.group(1)) if x.strip()]
            body = "\n".join(f"  {it}" for it in items)
            return f"\n@{d}\n{body}\n@end\n"

        s = re.sub(rf"\\begin\{{{env}\}}([\s\S]*?)\\end\{{{env}\}}", repl, s)
    return s


def convert_sections(s: str) -> str:
    mapping = {
        "chapter": "section",
        "section": "section",
        "subsection": "subsection",
        "subsubsection": "subsubsection",
        "paragraph": "subsubsection",
    }

    def repl(m: re.Match[str]) -> str:
        cmd, title = m.group(1), m.group(2).strip()
        rest = m.group(0)[m.end(2) - m.start() + m.start(0) :]  # unused
        # label may follow: \section{T}\label{L}
        return f"\n@{mapping[cmd]}({title})\n"

    s = re.sub(
        r"\\(chapter|section|subsection|subsubsection|paragraph)\*?\s*\{([\s\S]*?)\}(?:\\label\{([^}]*)\})?",
        lambda m: (
            f"\n@{mapping[m.group(1)]}({m.group(2).strip()}"
            + (f", label={m.group(3)}" if m.group(3) else "")
            + ")\n"
        ),
        s,
    )
    return s


def convert_inline_text(s: str) -> str:
    pairs = {
        "textbf": "b",
        "bf": "b",
        "textit": "i",
        "emph": "i",
        "it": "i",
        "textsl": "i",
        "underline": "u",
        "texttt": "inlinecode",
        "textsc": "",
        "textrm": "",
        "mbox": "",
        "text": "",
        "tt": "inlinecode",
    }
    # iterative for nesting
    for _ in range(8):
        changed = False

        def wrap(name: str, inner: str) -> str:
            return f"@{name}{{{inner}}}" if name else inner

        out: list[str] = []
        i = 0
        while i < len(s):
            m = re.match(r"\\([A-Za-z]+)\s*\{", s[i:])
            if m and m.group(1) in pairs:
                arg = brace_arg(s, i + m.end() - 1)
                if arg:
                    body, end = arg
                    out.append(wrap(pairs[m.group(1)], body))
                    i = end
                    changed = True
                    continue
            out.append(s[i])
            i += 1
        s = "".join(out)
        if not changed:
            break
    return s


def tidy(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip() + "\n"


def main() -> None:
    raw = TEX.read_text(encoding="latin-1")
    # drop comments (not \%)
    raw = re.sub(r"(?<!\\)%.*$", "", raw, flags=re.M)

    pre_m = re.search(r"\\begin\{document\}([\s\S]*)\\end\{document\}", raw)
    if not pre_m:
        print("no document env", file=sys.stderr)
        sys.exit(1)
    preamble = raw[: pre_m.start()]
    body = pre_m.group(1)

    title_m = re.search(r"\\title\{([\s\S]*?)\}", preamble + body)
    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
    authors = ""

    # Font switches before fraktur macro expansion
    body = rewrite_font_groups(body)

    body = expand_macros(body)
    authors, title2, body = convert_authors_block(body)
    if title2:
        title = title2
    body = convert_abstract(body)
    body = convert_cite_ref(body)  # before figures so captions get @ref
    body = convert_figures(body)
    body = convert_named_blocks(body)
    body = convert_equations_with_labels(body)
    body = convert_center(body)
    body = convert_bib(body)

    # drop junk
    body = re.sub(r"\\maketitle", "", body)
    body = re.sub(r"\\tableofcontents", "", body)
    body = re.sub(r"\\(?:noindent|newpage|clearpage|pagebreak)\b", "", body)
    body = re.sub(r"\\(?:centering|raggedright|raggedleft)\b", "", body)
    body = re.sub(r"\\(?:bigskip|medskip|smallskip|hfill|vfill|indent|par)\b", "", body)
    body = re.sub(r"\\hspace\*?\{{[^}}]*\}}", " ", body)
    body = re.sub(r"\\vspace\*?\{{[^}}]*\}}", "\n", body)

    body, math = stash_math_passthrough(body)
    body = convert_lists(body)
    body = convert_sections(body)
    # cites already done earlier; catch any remaining
    body = convert_cite_ref(body)
    body = convert_inline_text(body)
    body = re.sub(r"\\\\\s*", "\n", body)
    body = body.replace("~", " ")
    body = re.sub(r"\\[,;:!]", " ", body)
    body = re.sub(r"\\([&%_#$])", r"\1", body)
    # leftover labels on their own (section labels already folded)
    body = re.sub(r"\\label\{([^}]*)\}", "", body)
    body = restore_math(body, math)

    # Strip residual environments / layout macros (content already extracted).
    body = re.sub(r"\\begin\{[^}]+\}(?:\[[^\]]*\])?", "", body)
    body = re.sub(r"\\end\{[^}]+\}", "", body)
    for cmd in (
        "tt", "bf", "it", "em", "rm", "sf", "sc", "sl", "Huge", "huge", "LARGE",
        "Large", "large", "normalsize", "small", "footnotesize", "scriptsize",
        "tiny", "displaystyle", "textstyle", "scriptstyle", "limits", "nolimits",
        "nonumber", "notag", "allowbreak", "linebreak", "nolinebreak",
        "mathstrut", "phantom", "hphantom", "vphantom", "smash",
    ):
        body = re.sub(rf"\\{cmd}\b\s*", "", body)
    # bare \\cmd{…} leftovers that aren't IDoc — leave math-looking ones
    body = re.sub(r"\\(?:item|caption|centering)\b", "", body)

    head = ["@doc(template=academic)", f"@title({title})"]
    if authors:
        head.append(authors)
    head.append("")
    out = "\n".join(head) + "\n" + tidy(body)
    # Drop leftover $ (broken pairs) so they don't show in the doc.
    out = out.replace("$", "")
    out = re.sub(r"\n{3,}", "\n\n", out)
    OUT.write_text(out, encoding="utf-8")
    n_ph = out.count("__M__")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {out.count(chr(10))} lines)")
    if n_ph:
        print(f"WARNING: {n_ph} leftover placeholder markers", file=sys.stderr)


if __name__ == "__main__":
    main()
