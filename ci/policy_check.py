"""汎用ポリシーチェッカー。

プロジェクト固有の禁止パターンと秘密情報パターンをチェックする。
project-config.yml の policies セクション、または本ファイル内の定数で設定する。

使い方:
    python ci/policy_check.py
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

# スキャン対象ディレクトリ（プロジェクトに合わせて変更）
SCAN_DIRS = [
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
    REPO_ROOT / "scripts",
    REPO_ROOT / ".github",
    REPO_ROOT / "configs",
    REPO_ROOT / "ci",
]

# スキャン対象の拡張子
SCAN_EXTENSIONS = {
    ".py",
    ".ts",
    ".js",
    ".go",
    ".rs",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
    ".md",
    ".json",
    ".sh",
}

# スキップするディレクトリ名
SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    "target",
}

# ホワイトリスト（パスの相対表記）— 誤検知を除外するファイル
SKIP_FILES: set[str] = {
    "ci/policy_check.py",  # 自分自身のパターン定義は除外
}

# ---------------------------------------------------------------------------
# 禁止パターン（プロジェクトに合わせてカスタマイズ）
# ---------------------------------------------------------------------------

# 禁止 import パターン（正規表現、Python ファイルのみ適用）
# 例: 外部 HTTP ライブラリを禁止する場合
FORBIDDEN_IMPORT_PATTERNS: list[str] = [
    # r"^\s*import\s+requests",
    # r"^\s*from\s+requests\s+import",
    # r"^\s*import\s+httpx",
    # r"^\s*from\s+httpx\s+import",
]

# 秘密情報パターン（正規表現、全ファイル種別に適用）
SECRET_PATTERNS: list[str] = [
    r"AKIA[0-9A-Z]{16}",  # AWS Access Key ID
    r"-----BEGIN\s+(RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----",  # SSH 秘密鍵
    r"ghp_[A-Za-z0-9_]{36,}",  # GitHub Personal Access Token
    r"gho_[A-Za-z0-9_]{36,}",  # GitHub OAuth Token
    r"sk-[A-Za-z0-9]{32,}",  # 汎用 API キー
    r"sk-ant-api03-[A-Za-z0-9\-_]{20,}",  # Anthropic API キー新形式
    r"sk-proj-[A-Za-z0-9]{20,}",  # OpenAI API キー新形式
    r"Bearer\s+[A-Za-z0-9\-._~+/]{20,}=*",  # Bearer トークン（最小20文字で誤検知低減）
    r"password\s*=\s*[\"'][^\"\']+[\"']",  # パスワードハードコード
    r"passwd\s*=\s*[\"'][^\"\']+[\"']",  # パスワードハードコード
    r"secret\s*=\s*[\"'][^\"\']+[\"']",  # シークレットハードコード
    r"api_key\s*=\s*[\"'][^\"\']+[\"']",  # API キーハードコード
]

# 個人情報パターン（正規表現、全ファイル種別に適用）
# ログ出力や不適切な保存を検出
PERSONAL_INFO_PATTERNS: list[str] = [
    # メールアドレスのログ出力（logger.info や print 内）
    r'(logger\.(info|debug|warning|error)|print)\s*\([^)]*["\'].*@.*\..*["\']',
    # 電話番号のログ出力（日本の電話番号形式）
    r'(logger\.(info|debug|warning|error)|print)\s*\([^)]*["\'].*\d{2,4}-\d{2,4}-\d{4}.*["\']',
    # 平文パスワードのログ出力
    r"(logger\.(info|debug|warning|error)|print)\s*\([^)]*password[^)]*\)",
]

# URL パターン（コード中の外部 URL 直書きを検出）
URL_PATTERN = r"https?://[^\s\"')\]>]+"

# URL ホワイトリスト（マッチしたら許可）
URL_ALLOWLIST_PATTERNS: list[str] = [
    r"example\.com",
    r"github\.com",
    r"pypi\.org",
    r"npmjs\.com",
    r"docs\.python\.org",
    r"schemas\.openapi",
    r"json-schema\.org",
    r"astral\.sh",
    r"opentelemetry\.io",
]

# 禁止操作パターン（言語非依存、全ファイルに適用）
FORBIDDEN_PATTERNS: list[str] = [
    # プロジェクト固有の禁止パターンをここに追加
]


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------


def git_ls_files() -> list[Path]:
    """git 管理対象のファイル一覧を取得する。"""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        )
        return [REPO_ROOT / line for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def should_skip(path: Path) -> bool:
    """スキップ対象のディレクトリに含まれるか判定する。"""
    parts = set(path.parts)
    return any(name in parts for name in SKIP_DIR_NAMES)


def is_skipped_file(path: Path) -> bool:
    """ホワイトリストに登録されたファイルか判定する。"""
    rel = path.relative_to(REPO_ROOT).as_posix()
    return rel in SKIP_FILES


def read_text_safely(path: Path) -> str | None:
    """ファイルを安全に読み込む。"""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return None


def git_show_text(revision: str, relative_path: str) -> str | None:
    """指定リビジョンのファイル本文を取得する。"""
    try:
        result = subprocess.run(
            ["git", "show", f"{revision}:{relative_path}"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def is_url_allowlisted(line: str) -> bool:
    """URL がホワイトリストに該当するか判定する。"""
    return any(re.search(pat, line) for pat in URL_ALLOWLIST_PATTERNS)


def is_code_file(path: Path) -> bool:
    """コード系ファイルか判定する（コメント行の判定に使用）。"""
    return path.suffix.lower() in {".py", ".ts", ".js", ".go", ".rs"}


def is_comment_line(line: str, suffix: str) -> bool:
    """コメント行か判定する。"""
    stripped = line.lstrip()
    return suffix in {".py", ".ts", ".js", ".go", ".rs"} and (
        stripped.startswith("#") or stripped.startswith("//")
    )


def should_skip_secret_pattern(path: Path, pattern: str) -> bool:
    """ファイル種別に応じて秘密情報パターン検査を除外する。"""
    rel = path.relative_to(REPO_ROOT).as_posix()

    is_password_assignment_pattern = "password\\s*=\\s*" in pattern or "passwd\\s*=\\s*" in pattern
    if is_password_assignment_pattern:
        if rel.startswith("tests/"):
            return True
        if path.suffix.lower() == ".md":
            return True

    return False


def _is_sensitive_env_key(key: str) -> bool:
    """.env 系で機密値になりうるキーか判定する。"""
    normalized = key.strip().upper()
    sensitive_tokens = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "API_KEY")
    return any(token in normalized for token in sensitive_tokens)


def scan_env_example_for_secrets(path: Path) -> list[str]:
    """.env.example に機密値が直接記載されていないか確認する。"""
    issues: list[str] = []
    text = read_text_safely(path)
    if text is None:
        return issues

    rel = path.relative_to(REPO_ROOT)
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        if not _is_sensitive_env_key(key):
            continue

        if value.strip():
            issues.append(
                "秘密情報疑い: .env.example の機密キーに値が設定されています "
                f"({key.strip()}) in {rel}:{lineno}"
            )

    return issues


def scan_sec_triage_spec_freeze(path: Path) -> list[str]:
    """SEC系トリアージ仕様凍結ドキュメントの最低限の整合性を確認する。"""
    issues: list[str] = []
    if not path.exists():
        issues.append(
            "仕様不足: docs/sec-triage-spec-freeze.md が存在しません。"
        )
        return issues

    text = read_text_safely(path)
    if text is None:
        issues.append("仕様不足: docs/sec-triage-spec-freeze.md を読み取れません。")
        return issues

    rel = path.relative_to(REPO_ROOT)
    rel_posix = rel.as_posix()
    required_fragments = [
        "## 2. 確定仕様",
        "## 4. 凍結方針",
        "## 5. 変更管理",
        "## 6. 変更履歴",
        ".github/workflows/sec011-issue-triage.yml",
        ".github/workflows/security-issue-triage-report.yml",
        "docs/development.md",
        "README.md",
    ]

    for fragment in required_fragments:
        if fragment not in text:
            issues.append(
                f"仕様不足: 凍結仕様ドキュメントの必須要素が不足 ({fragment}) in {rel}"
            )

    if not re.search(r"-\s*v\d+\.\d+\s*[\(（]\d{4}-\d{2}-\d{2}[\)）]", text):
        issues.append(
            "仕様不足: 変更履歴の版表記（例: v1.0 (2026-03-05)）が見つかりません in "
            f"{rel}"
        )

    current_versions = [
        (int(major), int(minor))
        for major, minor in re.findall(r"-\s*v(\d+)\.(\d+)\s*[\(（]\d{4}-\d{2}-\d{2}[\)）]", text)
    ]
    previous_text = git_show_text("HEAD^", rel_posix)
    if previous_text is not None and previous_text != text:
        previous_versions = [
            (int(major), int(minor))
            for major, minor in re.findall(
                r"-\s*v(\d+)\.(\d+)\s*[\(（]\d{4}-\d{2}-\d{2}[\)）]",
                previous_text,
            )
        ]
        if previous_versions and current_versions:
            if max(current_versions) <= max(previous_versions):
                issues.append(
                    "仕様不足: docs/sec-triage-spec-freeze.md を変更した場合は "
                    "変更履歴の版番号を増分してください（例: v1.1 へ更新）。"
                )

    return issues


# ---------------------------------------------------------------------------
# スキャン
# ---------------------------------------------------------------------------


def scan_file(path: Path) -> list[str]:
    """1 ファイルをスキャンし、問題を返す。"""
    issues: list[str] = []
    text = read_text_safely(path)
    if text is None:
        return issues

    rel = path.relative_to(REPO_ROOT)
    suffix = path.suffix.lower()

    # 禁止 import（コードファイルのみ）
    if is_code_file(path) and FORBIDDEN_IMPORT_PATTERNS:
        for pat in FORBIDDEN_IMPORT_PATTERNS:
            if re.search(pat, text, flags=re.MULTILINE):
                issues.append(f"禁止操作疑い: 禁止import検出 ({pat}) in {rel}")

    # URL 直書き（コードファイルのみ — コメント行は除外）
    if is_code_file(path):
        for lineno, line in enumerate(text.splitlines(), start=1):
            if is_comment_line(line, suffix):
                continue
            if re.search(URL_PATTERN, line) and not is_url_allowlisted(line):
                issues.append(f"外部接続疑い: URL直書き検出 in {rel}:{lineno}")

    # 秘密情報（全ファイル種別）
    for pat in SECRET_PATTERNS:
        if should_skip_secret_pattern(path, pat):
            continue
        if re.search(pat, text):
            issues.append(f"秘密情報疑い: パターン検出 ({pat}) in {rel}")

    # 個人情報（全ファイル種別）
    for pat in PERSONAL_INFO_PATTERNS:
        if re.search(pat, text):
            issues.append(f"個人情報保護違反疑い: パターン検出 ({pat}) in {rel}")

    # プロジェクト固有の禁止パターン（全ファイル種別）
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, text, flags=re.MULTILINE):
            issues.append(f"禁止パターン検出: ({pat}) in {rel}")

    return issues


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------


def main() -> int:
    """ポリシーチェックを実行し、違反があれば非ゼロで終了する。"""
    issues: list[str] = []

    # .env が git 管理されていないことを確認
    tracked_files = {p.relative_to(REPO_ROOT).as_posix() for p in git_ls_files()}
    if ".env" in tracked_files:
        issues.append(
            "禁止: .env がリポジトリにコミットされています。削除し、gitignore 対象にしてください。"
        )

    # .env.example の機密キー値が空であることを確認
    env_example_path = REPO_ROOT / ".env.example"
    if env_example_path.exists():
        issues.extend(scan_env_example_for_secrets(env_example_path))

    # SEC系トリアージ仕様凍結ドキュメントの整合性を確認
    sec_triage_spec_path = REPO_ROOT / "docs" / "sec-triage-spec-freeze.md"
    issues.extend(scan_sec_triage_spec_freeze(sec_triage_spec_path))

    # 対象ファイルのスキャン
    for root in SCAN_DIRS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if should_skip(path):
                continue
            if is_skipped_file(path):
                continue
            if path.suffix.lower() not in SCAN_EXTENSIONS:
                continue
            issues.extend(scan_file(path))

    if issues:
        print("[policy_check] FAILED")
        for i, msg in enumerate(issues, start=1):
            print(f"  {i}. {msg}")
        return 1

    print("[policy_check] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
