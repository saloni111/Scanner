"""Rule-based static analysis agent.

This agent runs first and produces high-precision findings without any LLM
calls. It catches the obvious classes of issues — hardcoded secrets, unsafe
deserialization, SQL string interpolation, dangerous shell calls, weak crypto,
etc. — and tags each with a CWE.

The patterns are intentionally conservative: each rule favors specificity over
recall so that the LLM agent (which runs next) can focus on the trickier cases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.state import AgentState, FileBlob, Finding
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: re.Pattern[str]
    title: str
    category: str
    severity: str
    description: str
    recommendation: str
    cwe_id: str
    languages: tuple[str, ...] = ()  # empty = all
    confidence: float = 0.85


_RULES: list[Rule] = [
    Rule(
        id="hardcoded-secret-aws",
        pattern=re.compile(r"AKIA[0-9A-Z]{16}"),
        title="Hardcoded AWS access key",
        category="secret",
        severity="critical",
        description=(
            "An AWS access key ID was found in source. Anyone reading this repo "
            "can authenticate to your AWS account."
        ),
        recommendation=(
            "Rotate the key in IAM, remove it from git history (BFG / git "
            "filter-repo), and load credentials from the environment or a "
            "secrets manager instead."
        ),
        cwe_id="CWE-798",
    ),
    Rule(
        id="hardcoded-secret-generic",
        pattern=re.compile(
            r"""(?ix)
            (?:password|passwd|pwd|secret|api[_-]?key|token)
            \s*[:=]\s*
            ['"][A-Za-z0-9_\-/+=!@#$%^&*]{8,}['"]
            """,
        ),
        title="Hardcoded credential",
        category="secret",
        severity="high",
        description=(
            "What looks like a password, API key, or token is hardcoded as a "
            "string literal. Secrets in source are leaked to anyone with repo "
            "access and stay in git history forever."
        ),
        recommendation=(
            "Move the value to an environment variable or a secrets manager "
            "(AWS Secrets Manager, Vault, Doppler, ...) and read it at runtime."
        ),
        cwe_id="CWE-798",
        confidence=0.7,
    ),
    Rule(
        id="py-eval",
        pattern=re.compile(r"(?<![\w.])eval\s*\("),
        title="Use of `eval()`",
        category="code-injection",
        severity="high",
        description=(
            "`eval` executes arbitrary Python code. If any part of the input "
            "comes from a user it becomes a remote-code-execution sink."
        ),
        recommendation=(
            "Replace `eval` with `ast.literal_eval` for parsing literals, or "
            "design an explicit parser. Never feed user input into `eval`."
        ),
        cwe_id="CWE-95",
        languages=("python",),
    ),
    Rule(
        id="py-exec",
        pattern=re.compile(r"(?<![\w.])exec\s*\("),
        title="Use of `exec()`",
        category="code-injection",
        severity="high",
        description="`exec` runs arbitrary statements; treat all uses as suspect.",
        recommendation="Refactor to call the intended function directly.",
        cwe_id="CWE-95",
        languages=("python",),
    ),
    Rule(
        id="py-pickle",
        pattern=re.compile(r"\bpickle\.(loads?|Unpickler)\b"),
        title="Unsafe deserialization with pickle",
        category="deserialization",
        severity="high",
        description=(
            "`pickle` will execute code embedded in the payload. Loading "
            "pickle data from an untrusted source is equivalent to running "
            "arbitrary code."
        ),
        recommendation=(
            "Use `json` for data exchange. If you need a richer format, use "
            "`msgpack` or a schema-driven library (protobuf, pydantic)."
        ),
        cwe_id="CWE-502",
        languages=("python",),
    ),
    Rule(
        id="py-yaml-load",
        pattern=re.compile(r"\byaml\.load\s*\((?![^)]*Loader\s*=\s*yaml\.SafeLoader)"),
        title="Unsafe yaml.load",
        category="deserialization",
        severity="high",
        description=(
            "`yaml.load` without `SafeLoader` can instantiate arbitrary Python "
            "objects, leading to RCE on a malicious document."
        ),
        recommendation="Use `yaml.safe_load(...)` instead.",
        cwe_id="CWE-502",
        languages=("python",),
    ),
    Rule(
        id="py-subprocess-shell",
        pattern=re.compile(r"subprocess\.(?:call|run|Popen|check_output)\([^)]*shell\s*=\s*True"),
        title="subprocess invoked with shell=True",
        category="command-injection",
        severity="high",
        description=(
            "Passing `shell=True` to subprocess feeds the argument string to "
            "`/bin/sh`. If any portion is user-controlled this is a classic "
            "command-injection sink."
        ),
        recommendation=(
            "Pass the command as a list (`['ls', path]`) and keep "
            "`shell=False` (the default)."
        ),
        cwe_id="CWE-78",
        languages=("python",),
    ),
    Rule(
        id="py-os-system",
        pattern=re.compile(r"\bos\.system\s*\("),
        title="Use of os.system",
        category="command-injection",
        severity="medium",
        description="`os.system` invokes a shell with the supplied string.",
        recommendation="Prefer `subprocess.run([...], shell=False)`.",
        cwe_id="CWE-78",
        languages=("python",),
    ),
    Rule(
        id="sql-string-format",
        pattern=re.compile(
            r"""(?ix)
            (?:execute|executemany|cursor\.execute|query)
            \s*\(\s*
            (?:f["']|["'][^"']*?\{|["'][^"']*?%[sd])
            """,
        ),
        title="Possible SQL injection via string formatting",
        category="sql-injection",
        severity="high",
        description=(
            "SQL is being assembled with f-strings, `%` formatting, or `.format()` "
            "before it is sent to the database driver. If any interpolated value "
            "comes from user input this is exploitable."
        ),
        recommendation=(
            "Use parameterized queries: `cursor.execute(\"SELECT ... WHERE id = "
            "%s\", (user_id,))` or your ORM's bound parameters."
        ),
        cwe_id="CWE-89",
        confidence=0.75,
    ),
    Rule(
        id="js-innerhtml",
        pattern=re.compile(r"\.innerHTML\s*="),
        title="Direct innerHTML assignment",
        category="xss",
        severity="medium",
        description=(
            "Assigning to `.innerHTML` with values that contain user input is "
            "a primary source of DOM-based XSS."
        ),
        recommendation=(
            "Use `.textContent` for plain text, or sanitize via DOMPurify "
            "before rendering HTML."
        ),
        cwe_id="CWE-79",
        languages=("javascript", "typescript"),
    ),
    Rule(
        id="js-eval",
        pattern=re.compile(r"(?<![\w.])eval\s*\("),
        title="Use of eval() in JavaScript",
        category="code-injection",
        severity="high",
        description="`eval` evaluates arbitrary JavaScript at runtime.",
        recommendation="Refactor to call functions directly or use `JSON.parse`.",
        cwe_id="CWE-95",
        languages=("javascript", "typescript"),
    ),
    Rule(
        id="weak-md5",
        pattern=re.compile(r"hashlib\.md5\s*\(|MessageDigest\.getInstance\(\s*['\"]MD5"),
        title="Weak hash algorithm (MD5)",
        category="crypto",
        severity="medium",
        description=(
            "MD5 is collision-broken and unsuitable for any security-relevant "
            "use (signing, password hashing, integrity)."
        ),
        recommendation=(
            "Use SHA-256 or stronger; for passwords use a KDF such as bcrypt, "
            "argon2id, or scrypt."
        ),
        cwe_id="CWE-327",
    ),
    Rule(
        id="insecure-random",
        pattern=re.compile(r"\brandom\.(?:random|randint|choice)\s*\("),
        title="Use of non-cryptographic random for security context",
        category="crypto",
        severity="low",
        description=(
            "Python's `random` module is not cryptographically secure. If the "
            "value is used for tokens, password resets, or session IDs, it can "
            "be predicted."
        ),
        recommendation="Use `secrets.token_urlsafe()` / `secrets.randbelow()`.",
        cwe_id="CWE-330",
        languages=("python",),
        confidence=0.5,
    ),
    Rule(
        id="ssl-verify-disabled",
        pattern=re.compile(r"verify\s*=\s*False"),
        title="TLS certificate verification disabled",
        category="tls",
        severity="high",
        description=(
            "Disabling certificate verification opens the connection to "
            "trivial machine-in-the-middle attacks."
        ),
        recommendation=(
            "Remove `verify=False`. If a private CA is involved, point "
            "`verify` at the CA bundle path instead."
        ),
        cwe_id="CWE-295",
    ),
    Rule(
        id="debug-true",
        pattern=re.compile(r"\bDEBUG\s*=\s*True\b"),
        title="Debug mode enabled",
        category="config",
        severity="medium",
        description=(
            "Debug mode leaks stack traces and internal state to clients and "
            "(in Flask/Django) lets remote users execute code via the debugger."
        ),
        recommendation="Read `DEBUG` from the environment and default to False.",
        cwe_id="CWE-489",
        confidence=0.6,
    ),
]


def static_analyzer_node(state: AgentState) -> AgentState:
    findings: list[Finding] = []
    for blob in state.get("files", []) or []:
        findings.extend(_scan_file(blob))

    state["static_findings"] = findings
    metrics = state.get("metrics", {}) or {}
    metrics["static_rules_total"] = len(_RULES)
    state["metrics"] = metrics
    logger.info(f"static_analyzer: {len(findings)} findings")
    return state


def _scan_file(blob: FileBlob) -> list[Finding]:
    findings: list[Finding] = []
    lines = blob.content.splitlines()
    for rule in _RULES:
        if rule.languages and blob.language not in rule.languages:
            continue
        for match in rule.pattern.finditer(blob.content):
            line_num = blob.content.count("\n", 0, match.start()) + 1
            snippet = lines[line_num - 1].strip() if 0 < line_num <= len(lines) else None
            findings.append(
                Finding(
                    file_path=blob.path,
                    line_start=line_num,
                    line_end=line_num,
                    title=rule.title,
                    category=rule.category,
                    severity=rule.severity,
                    confidence=rule.confidence,
                    description=rule.description,
                    recommendation=rule.recommendation,
                    code_snippet=snippet,
                    cwe_id=rule.cwe_id,
                    related_cves=None,
                    detected_by=f"static:{rule.id}",
                )
            )
    return findings
