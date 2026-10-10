#!/usr/bin/env python3
"""
Workshop -- roster to Gitea repositories.

One command line tool for the whole TA worklow of a Gitea-based workshop:

    parse-excel         sign-up spreadsheet -> group.txt + individual.txt
    group               cut the leftover individuals into groups of N
    check-accounts      which accounts exist on Gitea
    detect-typos        find accounts that were probably mistyped
    add-team-members    add accounts to an organization team
    create-repos        one team + repository per line of group.txt
    verify-repos        check collaborators and default branch of those repos
    check-team          collaborators that are missing from an organization team
    report              the grouping and the accounts still not registered

Everything that talks to Gitea is read-only unless a command says --apply or
--yes. Configuration (domain, token, organization) comes from .env, see
.env.example.

Run `python3 workshop.py --help` or `python3 workshop.py <command> --help`.
"""

import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd
import typer
from focs_gitea.rest import ApiException

from joint_teapot.config import settings
from joint_teapot.teapot import Teapot
from joint_teapot.workers.gitea import PermissionEnum, list_all

# --------------------------------------------------------------------------- #
# spreadsheet columns
# --------------------------------------------------------------------------- #

COL_ACCOUNT = "账号"
COL_EMAIL = "Q3. 邮箱 Email"
COL_NAME = "Q1. 姓名 Name"
COL_ID = "Q2. 学工号 ID"
COL_GROUP_5 = "Q5. 请填写本项内容"
COL_GROUP_6 = "Q6. 请填写本项内容"
COL_GROUP_7 = "Q7. 请填写本项内容"
COL_ENROLL_NAME = "Q1. 姓名"
COL_ENROLL_ACCOUNT = "账号"

DEFAULT_GROUP_SIZE = 3
DEFAULT_PREFIX = "GitWksp_team"
DEFAULT_TEMPLATE = "template-Git-wksp-26Fa"


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #

def teapot() -> Teapot:
    return Teapot()


def org_name(override: str = "") -> str:
    return override or teapot().gitea.org_name


def find_spreadsheet(explicit: str = "") -> str:
    """Return the given spreadsheet, or the newest .xlsx in the directory."""
    if explicit:
        return explicit
    found = sorted(f for f in os.listdir(".") if f.endswith(".xlsx"))
    return found[-1] if found else ""


def read_groups(path: str) -> List[List[str]]:
    """Read group.txt: one group per line, members separated by spaces."""
    groups: List[List[str]] = []
    if not os.path.exists(path):
        return groups
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            members = line.split()
            if members:
                groups.append(members)
    return groups


def write_groups(path: str, groups: Sequence[Sequence[str]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for members in groups:
            f.write(" ".join(members) + "\n")


def read_accounts(paths: Iterable[str]) -> Tuple[List[str], Dict[str, str]]:
    """
    Read accounts from group/individual files.

    A group line holds several accounts; an individual line is
    "<account> [student_id]". The first token of every line is an account.

    Returns:
        (accounts in order of first appearance, account -> source file)
    """
    seen: Set[str] = set()
    accounts: List[str] = []
    source: Dict[str, str] = {}
    for path in paths:
        if not os.path.exists(path):
            typer.echo(f"Note: {path} does not exist, skipping")
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                for account in line.split():
                    if account.lower() not in seen:
                        seen.add(account.lower())
                        accounts.append(account)
                        source[account.lower()] = path
    return accounts, source


def account_exists(gitea: Teapot, account: str) -> bool:
    try:
        gitea.gitea.user_api.user_get(account)
        return True
    except ApiException as e:
        if e.status == 404:
            return False
        raise


def split_registered(gitea: Teapot, accounts: Iterable[str]) -> Tuple[List[str], List[str]]:
    """Split accounts into (existing on Gitea, not existing), order preserved."""
    registered: List[str] = []
    missing: List[str] = []
    for account in accounts:
        (registered if account_exists(gitea, account) else missing).append(account)
    return registered, missing


def identity_map(df: Optional[pd.DataFrame]) -> Dict[str, Tuple[str, str]]:
    """
    Map lowercased account -> (name, student ID) using the rows where the
    student filled in their own response. People who never filled in a response
    are absent, which is what "typed by a teammate" looks like.
    """
    mapping: Dict[str, Tuple[str, str]] = {}
    if df is None:
        return mapping
    for _, row in df.iterrows():
        account = str(row.get(COL_ACCOUNT, "")).strip() if pd.notna(row.get(COL_ACCOUNT)) else ""
        email = str(row.get(COL_EMAIL, "")).strip() if pd.notna(row.get(COL_EMAIL)) else ""
        local = email.split("@")[0] if "@" in email else ""
        name = str(row.get(COL_NAME, "")).strip() if pd.notna(row.get(COL_NAME)) else ""
        student_id = str(row.get(COL_ID, "")).strip() if pd.notna(row.get(COL_ID)) else ""
        for key in (account, local):
            if key:
                mapping.setdefault(key.lower(), (name, student_id))
    return mapping


def load_spreadsheet(path: str) -> Optional[pd.DataFrame]:
    if not path or not os.path.exists(path):
        return None
    return pd.read_excel(path)


def normalize_student_id(value: object) -> str:
    """Return the student ID as a plain digit string, or '' if unavailable."""
    if value is None or not pd.notna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def is_email(value: str) -> bool:
    import re

    return re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value.strip()) is not None


def local_part(value: str) -> str:
    """The part before '@'; the whole string when there is no '@'."""
    text = value.strip()
    return text.split("@")[0] if "@" in text else text


def dedupe(entries: Iterable[str]) -> List[str]:
    """Drop empty and repeated entries, ignoring case."""
    seen: Set[str] = set()
    result: List[str] = []
    for entry in entries:
        text = str(entry).strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        result.append(text)
    return result


def team_by_name(gitea: Teapot, org: str, name: str) -> Optional[Dict]:
    found = gitea.gitea.organization_api.team_search(org, q=name, limit=50).to_dict()
    return next((t for t in (found.get("data") or []) if t["name"] == name), None)


def team_members(gitea: Teapot, team_id: int) -> Dict[str, str]:
    """lowercased login -> login for every member of the team."""
    members: Dict[str, str] = {}
    page = 1
    while True:
        res = gitea.gitea.organization_api.org_list_team_members(team_id, page=page)
        if not res:
            break
        for user in res:
            members[user.login.lower()] = user.login
        page += 1
    return members


def repo_names_with_prefix(gitea: Teapot, org: str, prefix: str) -> List[str]:
    return sorted(
        r.name
        for r in list_all(gitea.gitea.organization_api.org_list_repos, org)
        if r.name.startswith(prefix)
    )


def repo_collaborators(gitea: Teapot, org: str, repo: str) -> List[str]:
    return [c.login for c in gitea.gitea.repository_api.repo_list_collaborators(org, repo)]


# --------------------------------------------------------------------------- #
# parse-excel
# --------------------------------------------------------------------------- #

def process_spreadsheet(
    excel_path: str,
    group_output: str,
    individual_output: str,
    enrollment_path: str,
) -> None:
    """
    Turn the sign-up spreadsheet into group.txt and individual.txt.

    A row with a non-empty Q5 is a group: the account column plus Q5/Q6/Q7, the
    e-mail local parts being used when a teammate was given as an address. A row
    with an empty Q5 is an individual. A group whose members all appear again in
    a later group is dropped, and an individual who is already a member of a
    written group is dropped too, so nobody ends up in two groups.
    """
    typer.echo(f"Reading {excel_path}")
    try:
        df = pd.read_excel(excel_path)
    except FileNotFoundError:
        typer.echo(f"Error: {excel_path} not found")
        raise typer.Exit(1)
    typer.echo(f"Columns: {list(df.columns)}")

    for column in (COL_EMAIL, COL_GROUP_5):
        if column not in df.columns:
            typer.echo(f"Error: required column missing: {column}")
            raise typer.Exit(1)
    for column in (COL_GROUP_6, COL_GROUP_7):
        if column not in df.columns:
            typer.echo(f"Warning: optional column missing: {column}")

    groups: List[Tuple[int, List[str]]] = []
    individuals: List[Tuple[int, str, str]] = []

    for index, row in df.iterrows():
        raw_account = row[COL_ACCOUNT] if COL_ACCOUNT in df.columns else None
        raw_email = row[COL_EMAIL] if COL_EMAIL in df.columns else None
        account = ""
        if pd.notna(raw_account) and str(raw_account).strip():
            account = str(raw_account).strip()
        elif pd.notna(raw_email) and is_email(str(raw_email)):
            account = local_part(str(raw_email))
        student_id = normalize_student_id(
            row[COL_ID] if COL_ID in df.columns else None
        )

        q5 = row[COL_GROUP_5] if COL_GROUP_5 in df.columns else None
        teammate_values = [
            row[c] for c in (COL_GROUP_5, COL_GROUP_6, COL_GROUP_7) if c in df.columns
        ]

        if pd.notna(q5) and str(q5).strip():
            members = [account] if account else []
            for value in teammate_values:
                if pd.notna(value) and str(value).strip():
                    members.append(local_part(str(value)))
            members = dedupe(members)
            if members:
                groups.append((index, members))
        elif account:
            individuals.append((index, account, student_id))

    # A group that is a subset of a later group is a duplicate submission: the
    # later group wins, the earlier one is dropped.
    skipped: Set[int] = set()
    for i, (index, members) in enumerate(groups):
        current = {m.lower() for m in members}
        for later_index, later in groups[i + 1:]:
            if current & {m.lower() for m in later}:
                skipped.add(index)
                typer.echo(
                    f"Row {index}: skipped, its members appear again in row {later_index}"
                )
                break

    grouped_accounts: Set[str] = set()
    for index, members in groups:
        if index not in skipped:
            grouped_accounts.update(m.lower() for m in members)

    with open(group_output, "w", encoding="utf-8") as group_file, \
            open(individual_output, "w", encoding="utf-8") as individual_file:
        group_count = 0
        for index, members in groups:
            if index in skipped:
                continue
            group_file.write(" ".join(members) + "\n")
            group_count += 1
            typer.echo(f"Row {index}: group -> {members}")

        individual_count = 0
        for index, account, student_id in individuals:
            if account.lower() in grouped_accounts:
                typer.echo(f"Row {index}: {account} skipped, already in a group")
                continue
            individual_file.write(f"{account} {student_id}".rstrip() + "\n")
            individual_count += 1
            typer.echo(f"Row {index}: individual -> {account} {student_id}".rstrip())

    typer.echo(
        f"Wrote {group_output} ({group_count} groups) and "
        f"{individual_output} ({individual_count} individuals)"
    )

    if enrollment_path and os.path.exists(enrollment_path):
        add_missing_enrollment(
            enrollment_path, group_output, individual_output
        )
    elif enrollment_path:
        typer.echo(f"No {enrollment_path}, skipping the enrollment check")


def add_missing_enrollment(
    enrollment_path: str, group_output: str, individual_output: str
) -> None:
    """Append enrolled people who are in no output file to individual.txt."""
    typer.echo(f"Checking {enrollment_path} for missing participants")
    try:
        enrolled = pd.read_excel(enrollment_path)
    except Exception as e:  # noqa: BLE001 - reported, not fatal
        typer.echo(f"Error reading {enrollment_path}: {e}")
        return
    if COL_ENROLL_NAME not in enrolled.columns:
        typer.echo(f"Warning: {COL_ENROLL_NAME} missing from {enrollment_path}")
        return

    known: Set[str] = set()
    for path in (group_output, individual_output):
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                for token in line.split():
                    known.add(token.lower())
                    break  # only the first token of a line is an account

    missing: List[str] = []
    for _, row in enrolled.iterrows():
        account = row.get(COL_ENROLL_ACCOUNT)
        if pd.notna(account) and str(account).strip():
            account = str(account).strip()
            if account.lower() not in known:
                missing.append(account)

    if not missing:
        typer.echo("No enrolled participant is missing")
        return
    with open(individual_output, "a", encoding="utf-8") as f:
        for account in missing:
            f.write(account + "\n")
    typer.echo(f"Appended {len(missing)} enrolled accounts to {individual_output}")


# --------------------------------------------------------------------------- #
# group
# --------------------------------------------------------------------------- #

def student_id_prefix(student_id: str) -> int:
    """First three digits of the student ID, -1 when unknown (sorted last)."""
    digits = student_id[:3]
    return int(digits) if len(digits) == 3 and digits.isdigit() else -1


def read_individuals(path: str) -> List[Tuple[str, str]]:
    """Read individual.txt into (account, student_id) pairs."""
    entries: List[Tuple[str, str]] = []
    if not os.path.exists(path):
        return entries
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if parts:
                entries.append((parts[0], parts[1] if len(parts) > 1 else ""))
    return entries


def sort_for_grouping(
    entries: List[Tuple[str, str]], registered: Optional[Set[str]]
) -> List[Tuple[str, str]]:
    """
    Order people for grouping: first everyone whose Gitea account already
    exists, then everyone who still has to register, so a group is never left
    with a member that cannot be added as a collaborator. Inside each of those
    buckets people go by student ID prefix and then by the full student ID.
    """
    def key(entry: Tuple[str, str]) -> Tuple[int, int, int, str]:
        account, student_id = entry
        if registered is None:
            bucket = 0
        else:
            bucket = 0 if account.lower() in registered else 1
        prefix = student_id_prefix(student_id)
        if prefix < 0:
            return (bucket, 1, 0, "")
        return (bucket, 0, prefix, student_id)

    return sorted(entries, key=key)


def cut_into_groups(
    entries: List[Tuple[str, str]],
    group_size: int,
    registered: Optional[Set[str]],
) -> List[List[str]]:
    """
    Cut people into groups of group_size, never mixing the two buckets.

    A bucket that cannot fill a group is kept as its own smaller group, except a
    single leftover, which joins the previous group of the same bucket.
    """
    if registered is None:
        buckets: List[Tuple[str, List[str]]] = [("all", [a for a, _ in entries])]
    else:
        buckets = []
        for label, wanted in (("registered", True), ("unregistered", False)):
            bucket = [
                a for a, _ in entries if (a.lower() in registered) == wanted
            ]
            if bucket:
                buckets.append((label, bucket))

    result: List[List[str]] = []
    for label, bucket in buckets:
        typer.echo(f"Bucket '{label}': {len(bucket)} accounts")
        chunks = [
            bucket[i:i + group_size] for i in range(0, len(bucket), group_size)
        ]
        tail = chunks[-1] if chunks and len(chunks[-1]) < group_size else None
        if tail:
            chunks = chunks[:-1]
        if tail:
            if len(tail) == 1 and chunks:
                chunks[-1].extend(tail)
                typer.echo(f"  leftover joins the previous group: {tail}")
            else:
                chunks.append(tail)
                typer.echo(f"  leftover forms its own group: {tail}")
        result.extend(chunks)
    return result


def group_individuals(
    individual_file: str,
    group_file: str,
    group_size: int,
    registered: Optional[Set[str]],
) -> None:
    entries = read_individuals(individual_file)
    typer.echo(f"Read {len(entries)} accounts from {individual_file}")
    if len(entries) < group_size:
        typer.echo(f"Not enough accounts for a group of {group_size}, nothing done")
        return

    prefixes = Counter(student_id_prefix(sid) for _, sid in entries)
    typer.echo(
        "Student ID prefixes: "
        + ", ".join(
            f"{p if p >= 0 else 'unknown'}:{c}" for p, c in sorted(prefixes.items())
        )
    )
    if registered is not None:
        not_yet = [a for a, _ in entries if a.lower() not in registered]
        typer.echo(
            f"Gitea accounts: {len(entries) - len(not_yet)} registered, "
            f"{len(not_yet)} not registered yet"
        )
        if not_yet:
            typer.echo("  not registered: " + ", ".join(not_yet))

    entries = sort_for_grouping(entries, registered)
    new_groups = cut_into_groups(entries, group_size, registered)
    typer.echo(
        f"Created {len(new_groups)} groups "
        f"({sum(1 for g in new_groups if len(g) == group_size)} of them full)"
    )

    groups = read_groups(group_file)
    typer.echo(f"Found {len(groups)} existing groups in {group_file}")
    groups.extend(new_groups)
    write_groups(group_file, groups)

    with open(individual_file, "w", encoding="utf-8") as f:
        f.write("")
    typer.echo(
        f"Wrote {len(groups)} groups to {group_file}, emptied {individual_file}"
    )


# --------------------------------------------------------------------------- #
# check-accounts / detect-typos
# --------------------------------------------------------------------------- #

CONFUSIONS = [
    ("m", "n"), ("n", "m"), ("i", "l"), ("l", "i"), ("i", "1"), ("1", "i"),
    ("l", "1"), ("1", "l"), ("o", "0"), ("0", "o"), ("u", "v"), ("v", "u"),
    ("c", "k"), ("k", "c"), ("s", "z"), ("z", "s"), ("e", "r"), ("r", "e"),
    ("a", "s"), ("s", "a"), ("t", "y"), ("y", "t"), ("g", "h"), ("h", "g"),
    ("b", "d"), ("d", "b"), ("5", "6"), ("6", "5"), ("2", "3"), ("3", "2"),
    ("8", "9"), ("9", "8"), (".", "_"), ("_", "."),
]


def mutations(account: str) -> List[str]:
    """Edit-distance-1 and a few common-typo variants of an account."""
    out: Set[str] = set()
    n = len(account)
    for i in range(n):
        out.add(account[:i] + account[i + 1:])
        if i + 1 < n and account[i] == account[i + 1]:
            out.add(account[:i] + account[i + 1:])
    for i in range(n - 1):
        out.add(account[:i] + account[i + 1] + account[i] + account[i + 2:])
    for i in range(n + 1):
        for char in set(account):
            out.add(account[:i] + char + account[i:])
    for i, char in enumerate(account):
        for old, new in CONFUSIONS:
            if char == old:
                out.add(account[:i] + new + account[i + 1:])
    for i, char in enumerate(account):
        if char.isdigit():
            for delta in (-1, 1):
                out.add(account[:i] + str((int(char) + delta) % 10) + account[i + 1:])
    stripped = account.rstrip("0123456789")
    if stripped != account:
        out.add(stripped)
    out.discard(account)
    out.discard("")
    return sorted(out)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def detect_typos(
    files: List[str],
    excel_path: str,
    threshold: float,
    probe: bool,
) -> None:
    gitea = teapot()
    accounts, _ = read_accounts(files)
    typer.echo(f"Accounts in {', '.join(files)}: {len(accounts)}")

    df = load_spreadsheet(find_spreadsheet(excel_path))
    if df is not None:
        typer.echo("Using the spreadsheet for extra context")

    registered, suspects = split_registered(gitea, accounts)
    members = [
        m.login for m in list_all(gitea.gitea.organization_api.org_list_members, gitea.gitea.org_name)
    ]
    pool = {a.lower() for a in registered} | {m.lower() for m in members}
    typer.echo(
        f"Organization: {gitea.gitea.org_name}\n"
        f"Registered: {len(registered)}, not found on Gitea: {len(suspects)}\n"
        f"Similarity pool: {len(pool)} accounts\n"
    )

    probe_hits: Dict[str, List[str]] = {}
    if probe and suspects:
        variants: Dict[str, str] = {}
        for suspect in suspects:
            for variant in mutations(suspect):
                if variant.lower() not in pool:
                    variants.setdefault(variant, suspect)
        typer.echo(f"Probing {len(variants)} variants ...")
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda v: account_exists(gitea, v), variants))
        for variant, hit in zip(variants, results):
            if hit:
                probe_hits.setdefault(variants[variant], []).append(variant)
        typer.echo(
            f"{sum(len(v) for v in probe_hits.values())} variant(s) exist on Gitea\n"
        )

    identity = identity_map(df)
    high: List[Tuple[str, str, float]] = []
    for suspect in suspects:
        typer.echo(f"--- {suspect}")
        if suspect.lower() in identity:
            name, student_id = identity[suspect.lower()]
            typer.echo(f"    own row: name={name} id={student_id}")
        scored: Dict[str, float] = {}
        for candidate in pool:
            score = similarity(suspect, candidate)
            if score >= threshold:
                scored[candidate] = score
        for variant in probe_hits.get(suspect, []):
            scored[variant] = max(scored.get(variant, 0.0), similarity(suspect, variant))
        ranked = sorted(scored.items(), key=lambda kv: -kv[1])[:5]
        for candidate, score in ranked:
            source = "exists (probe)" if candidate in probe_hits.get(suspect, []) else "similar"
            typer.echo(f"    {score:.2f}  {candidate:24} <- {source}")
            if candidate in identity:
                name, student_id = identity[candidate]
                typer.echo(f"           candidate row: name={name} id={student_id}")
        if not ranked:
            typer.echo("    no similar candidate and no existing variant found")
        if ranked and ranked[0][1] >= 0.85:
            high.append((suspect, ranked[0][0], ranked[0][1]))

    typer.echo(f"\n{len(suspects)} suspect account(s), {len(high)} high-confidence:")
    for suspect, candidate, score in high:
        typer.echo(f"  {suspect:24} -> {candidate:24} ({score:.2f})")


# --------------------------------------------------------------------------- #
# Gitea: teams and repositories
# --------------------------------------------------------------------------- #

def create_teams_and_repos(
    gitea: Teapot,
    group: str,
    usernames: List[str],
    template: str = "",
    permission: PermissionEnum = PermissionEnum.write,
) -> bool:
    """
    Make sure the team and the repository of one group exist and that every
    user is a team member and a collaborator. Idempotent: anything that already
    exists is left alone and only what is missing is added.
    """
    from joint_teapot.utils.logger import logger

    teams = list_all(gitea.gitea.organization_api.org_list_teams, gitea.gitea.org_name)
    repos = list_all(gitea.gitea.organization_api.org_list_repos, gitea.gitea.org_name)
    team_name = repo_name = group

    team = next((t for t in teams if t.name == team_name), None)
    if team is None:
        team = gitea.gitea.organization_api.org_create_team(
            gitea.gitea.org_name,
            body={
                "can_create_org_repo": False,
                "includes_all_repositories": False,
                "name": team_name,
                "permission": permission.value,
                "units": [
                    "repo.code", "repo.issues", "repo.ext_issues", "repo.wiki",
                    "repo.pulls", "repo.releases", "repo.projects", "repo.ext_wiki",
                ],
            },
        )
        logger.info(f"Team {team_name} created")
    else:
        logger.info(f"Team {team_name} already exists")

    if next((r for r in repos if r.name == repo_name), None) is None:
        if template:
            gitea.gitea.repository_api.generate_repo(
                gitea.gitea.org_name,
                template,
                body={
                    "default_branch": settings.default_branch,
                    "git_content": True,
                    "git_hooks": True,
                    "labels": True,
                    "name": repo_name,
                    "owner": gitea.gitea.org_name,
                    "private": True,
                    "protected_branch": True,
                },
            )
        else:
            gitea.gitea.organization_api.create_org_repo(
                gitea.gitea.org_name,
                body={
                    "auto_init": False,
                    "default_branch": settings.default_branch,
                    "name": repo_name,
                    "private": True,
                    "template": False,
                    "trust_model": "default",
                },
            )
        logger.info(f"{gitea.gitea.org_name}/{repo_name} created")
    else:
        logger.info(f"Repository {gitea.gitea.org_name}/{repo_name} already exists")

    try:
        gitea.gitea.organization_api.org_add_team_repository(
            team.id, gitea.gitea.org_name, repo_name
        )
    except Exception as e:  # noqa: BLE001 - already there most of the time
        logger.warning(e)

    for username in usernames:
        try:
            gitea.gitea.organization_api.org_add_team_member(team.id, username)
            gitea.gitea.repository_api.repo_add_collaborator(
                gitea.gitea.org_name, repo_name, username
            )
        except Exception as e:  # noqa: BLE001 - a single bad account must not stop the rest
            logger.error(e)
            continue

    try:
        gitea.gitea.repository_api.repo_delete_branch_protection(
            gitea.gitea.org_name, repo_name, settings.default_branch
        )
    except ApiException as e:
        if e.status != 404:
            raise

    logger.info(f"{gitea.gitea.org_name}/{repo_name} jobs done")
    return True


def repo_plan(
    gitea: Teapot,
    org: str,
    groups: List[List[str]],
    prefix: str,
    start: int,
    end: int,
) -> Tuple[List[int], Dict[int, List[str]], Dict[int, List[str]], List[str]]:
    """
    Work out what would be created.

    Returns:
        (group indices in range, existing accounts per group, missing accounts
        per group, repository names that already exist)
    """
    indices = [i for i in range(1, len(groups) + 1) if start <= i <= end]
    known: Dict[str, bool] = {}
    valid: Dict[int, List[str]] = {}
    missing: Dict[int, List[str]] = {}
    existing: List[str] = []

    for index in indices:
        name = f"{prefix}{index:02d}"
        good: List[str] = []
        bad: List[str] = []
        for account in groups[index - 1]:
            if account.lower() not in known:
                known[account.lower()] = account_exists(gitea, account)
            (good if known[account.lower()] else bad).append(account)
        valid[index] = good
        if bad:
            missing[index] = bad

        try:
            gitea.gitea.repository_api.repo_get(org, name)
            exists = True
        except ApiException as e:
            if e.status != 404:
                raise
            exists = False
        if not exists and team_by_name(gitea, org, name) is not None:
            exists = True
        if exists:
            existing.append(name)
    return indices, valid, missing, existing


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

app = typer.Typer(
    add_completion=False,
    help="Roster to Gitea repositories: parse a sign-up spreadsheet, group the "
         "students, and create one team and repository per group.",
)


@app.command("parse-excel")
def cmd_parse_excel(
    excel: str = typer.Argument("", help="sign-up spreadsheet (default: newest .xlsx)"),
    group_out: str = typer.Option("group.txt", "--group-out"),
    individual_out: str = typer.Option("individual.txt", "--individual-out"),
    enroll: str = typer.Option("enroll.xlsx", "--enroll",
                               help="enrollment spreadsheet, skipped when absent"),
) -> None:
    """Turn the sign-up spreadsheet into group.txt and individual.txt."""
    path = find_spreadsheet(excel)
    if not path:
        typer.echo("Error: no .xlsx found")
        raise typer.Exit(1)
    process_spreadsheet(path, group_out, individual_out, enroll)


@app.command("group")
def cmd_group(
    individual: str = typer.Argument("individual.txt"),
    groups_file: str = typer.Argument("group.txt"),
    size: int = typer.Option(DEFAULT_GROUP_SIZE, "--size", min=1),
    no_gitea: bool = typer.Option(
        False, "--no-gitea",
        help="skip the Gitea registration check, group by student ID only",
    ),
) -> None:
    """Cut the leftover individuals into groups and append them to group.txt."""
    registered: Optional[Set[str]] = None
    if not no_gitea:
        accounts = [a for a, _ in read_individuals(individual)]
        registered, missing = split_registered(teapot(), accounts)
        registered = {a.lower() for a in registered}
        del missing
    group_individuals(individual, groups_file, size, registered)


@app.command("check-accounts")
def cmd_check_accounts(
    files: List[str] = typer.Argument(None, help="default: group.txt individual.txt"),
    out: str = typer.Option("", "--out", help="write the unknown accounts here"),
) -> None:
    """List which accounts exist on Gitea and which do not."""
    accounts, source = read_accounts(files or ["group.txt", "individual.txt"])
    gitea = teapot()
    registered, missing = split_registered(gitea, accounts)
    typer.echo(
        f"Organization: {gitea.gitea.org_name}\n"
        f"Accounts: {len(accounts)}   on Gitea: {len(registered)}   "
        f"not registered: {len(missing)}"
    )
    for account in missing:
        typer.echo(f"  {account:24} <- {source[account.lower()]}")
    if out and missing:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(missing) + "\n")
        typer.echo(f"Wrote {len(missing)} accounts to {out}")


@app.command("detect-typos")
def cmd_detect_typos(
    files: List[str] = typer.Argument(None, help="default: group.txt individual.txt"),
    excel: str = typer.Option("", "--excel", help="spreadsheet for extra context"),
    threshold: float = typer.Option(0.7, "--threshold"),
    probe: bool = typer.Option(
        False, "--probe", help="probe edit-distance-1 variants against Gitea (slower)"
    ),
) -> None:
    """Find accounts that were probably mistyped, by similarity and probing."""
    detect_typos(files or ["group.txt", "individual.txt"], excel, threshold, probe)


@app.command("add-team-members")
def cmd_add_team_members(
    files: List[str] = typer.Argument(None, help="default: group.txt individual.txt"),
    team: str = typer.Option("wksp-support", "--team"),
    org: str = typer.Option("", "--org"),
    apply: bool = typer.Option(False, "--apply", help="actually add (default: dry run)"),
    missing_out: str = typer.Option("", "--missing-out",
                                    help="write the accounts with no Gitea user here"),
) -> None:
    """Add every account to an organization team. Gitea has no API for adding a
    plain organization member, so membership always goes through a team."""
    accounts, source = read_accounts(files or ["group.txt", "individual.txt"])
    gitea = teapot()
    organization = org_name(org)

    found = team_by_name(gitea, organization, team)
    if not found:
        typer.echo(f"Error: team '{team}' not found in {organization}")
        raise typer.Exit(1)

    members = team_members(gitea, found["id"])
    typer.echo(
        f"Organization: {organization}\n"
        f"Team: {team} (id={found['id']}, permission={found.get('permission')}, "
        f"{len(members)} members now)\n"
        f"Accounts to process: {len(accounts)}\n"
        f"Mode: {'APPLY' if apply else 'DRY RUN'}"
    )

    to_add: List[str] = []
    already: List[str] = []
    missing: List[str] = []
    for account in accounts:
        if account.lower() in members:
            already.append(account)
        elif account_exists(gitea, account):
            to_add.append(account)
        else:
            missing.append(account)

    typer.echo(f"\n  already in team: {len(already)}")
    typer.echo(f"  to add         : {len(to_add)}")
    for account in to_add:
        typer.echo(f"    {account}")
    typer.echo(f"  no such user   : {len(missing)}")
    for account in missing:
        typer.echo(f"    {account:24} <- {source[account.lower()]}")

    if missing_out and missing:
        with open(missing_out, "w", encoding="utf-8") as f:
            f.write("\n".join(missing) + "\n")
        typer.echo(f"\nWrote {len(missing)} accounts to {missing_out}")

    if apply and to_add:
        typer.echo(f"\nAdding {len(to_add)} members to {team} ...")
        added = 0
        for account in to_add:
            try:
                gitea.gitea.organization_api.org_add_team_member(found["id"], account)
                added += 1
            except ApiException as e:
                typer.echo(f"  FAILED {account}: HTTP {e.status} {e.reason}")
        typer.echo(f"Added {added}/{len(to_add)}")
    elif not apply:
        typer.echo("\nDry run: nothing was changed. Re-run with --apply to add.")


@app.command("create-repos")
def cmd_create_repos(
    groups_file: str = typer.Argument("group.txt"),
    template: str = typer.Option(DEFAULT_TEMPLATE, "--template"),
    prefix: str = typer.Option(DEFAULT_PREFIX, "--prefix"),
    start: int = typer.Option(1, "--start", help="first group index"),
    end: int = typer.Option(0, "--end", help="last group index, 0 means all"),
    org: str = typer.Option("", "--org"),
    yes: bool = typer.Option(False, "--yes", help="create; without it nothing is written"),
) -> None:
    """Create one team and repository per line of group.txt, from a template.

    The command is idempotent: an existing team or repository is left alone and
    only the missing members and collaborators are added, so it can be re-run
    whenever students register late."""
    groups = read_groups(groups_file)
    if not groups:
        typer.echo(f"Error: no groups in {groups_file}")
        raise typer.Exit(1)
    gitea = teapot()
    organization = org_name(org)
    last = end or len(groups)

    typer.echo(
        f"Organization: {organization}\n"
        f"Template    : {template or '(empty repository)'}\n"
        f"Default branch: {settings.default_branch}\n"
        f"Groups      : {len(groups)} in {groups_file}, range {start}-{last}\n"
        f"Mode        : {'CREATE' if yes else 'CHECK ONLY'}"
    )

    if template:
        try:
            gitea.gitea.repository_api.repo_get(organization, template)
            typer.echo(f"Template {organization}/{template} OK")
        except ApiException as e:
            typer.echo(f"Aborting: template not readable: HTTP {e.status} {e.reason}")
            raise typer.Exit(1)

    indices, valid, missing, existing = repo_plan(
        gitea, organization, groups, prefix, start, last
    )
    collaborators = sum(len(valid.get(i, [])) for i in indices)
    skipped = sum(len(v) for v in missing.values())
    typer.echo(
        f"\nRepositories in range: {len(indices)}\n"
        f"Already existing     : {len(existing)}\n"
        f"Collaborator entries : {collaborators}\n"
        f"Accounts to skip     : {skipped} (not registered)"
    )
    if missing:
        typer.echo("\nGroups with accounts that will be skipped:")
        for index in sorted(missing):
            typer.echo(f"  组{index:02d} {prefix}{index:02d}: {', '.join(missing[index])}")

    typer.echo("\nPlanned repositories:")
    for index in indices:
        typer.echo(
            f"  {prefix}{index:02d}  {len(valid.get(index, []))} collaborators  "
            f"{' '.join(valid.get(index, []))}"
        )

    if not yes:
        typer.echo(f"\nCheck only: nothing was written. Re-run with --yes to "
                   f"create or reconcile {len(indices)} repositories.")
        return

    typer.echo(f"\nReconciling {len(indices)} teams and repositories ...")
    existing_names = set(existing)
    created = 0
    reconciled = 0
    failed: List[Tuple[str, str]] = []
    for index in indices:
        name = f"{prefix}{index:02d}"
        try:
            ok = create_teams_and_repos(
                gitea, name, valid.get(index, []), template=template
            )
        except Exception as e:  # noqa: BLE001 - keep going, report at the end
            failed.append((name, str(e)))
            typer.echo(f"  FAILED {name}: {e}")
            continue
        if not ok:
            failed.append((name, "create_teams_and_repos returned False"))
            typer.echo(f"  FAILED {name}")
            continue
        if name in existing_names:
            reconciled += 1
        else:
            created += 1
        typer.echo(f"  ok {name} ({len(valid.get(index, []))} collaborators)")

    typer.echo(
        f"\nCreated {created}, reconciled {reconciled}, failed {len(failed)}"
    )
    for name, reason in failed:
        typer.echo(f"  {name}: {reason}")
    typer.echo(
        f"https://{settings.gitea_domain_name}{settings.gitea_suffix}/{organization}"
    )


@app.command("verify-repos")
def cmd_verify_repos(
    groups_file: str = typer.Argument("group.txt"),
    prefix: str = typer.Option(DEFAULT_PREFIX, "--prefix"),
    start: int = typer.Option(1, "--start"),
    end: int = typer.Option(0, "--end", help="0 means all"),
    org: str = typer.Option("", "--org"),
) -> None:
    """Check that every repository has exactly the collaborators its group has
    and the expected default branch."""
    groups = read_groups(groups_file)
    gitea = teapot()
    organization = org_name(org)
    last = end or len(groups)

    problems = 0
    indices = [i for i in range(1, len(groups) + 1) if start <= i <= last]
    typer.echo(f"Verifying {len(indices)} repositories in {organization} ...")
    for index in indices:
        name = f"{prefix}{index:02d}"
        expected = {
            a.lower() for a in groups[index - 1] if account_exists(gitea, a)
        }
        try:
            repo = gitea.gitea.repository_api.repo_get(organization, name)
            actual = {c.lower() for c in repo_collaborators(gitea, organization, name)}
        except ApiException as e:
            problems += 1
            typer.echo(f"  {name}: HTTP {e.status} {e.reason}")
            continue
        if actual != expected:
            problems += 1
            typer.echo(f"  {name}: expected {sorted(expected)} got {sorted(actual)}")
        if repo.default_branch != settings.default_branch:
            problems += 1
            typer.echo(
                f"  {name}: default branch {repo.default_branch} "
                f"!= {settings.default_branch}"
            )
    typer.echo(f"\nVerified {len(indices)} repositories, {problems} problem(s)")


@app.command("check-team")
def cmd_check_team(
    team: str = typer.Argument("wksp-support"),
    prefix: str = typer.Option(DEFAULT_PREFIX, "--prefix"),
    org: str = typer.Option("", "--org"),
) -> None:
    """Report collaborators of the <prefix>* repositories that are not members
    of the given team."""
    gitea = teapot()
    organization = org_name(org)
    found = team_by_name(gitea, organization, team)
    if not found:
        typer.echo(f"Error: team '{team}' not found in {organization}")
        raise typer.Exit(1)

    repositories = repo_names_with_prefix(gitea, organization, prefix)
    members = team_members(gitea, found["id"])
    typer.echo(
        f"Organization: {organization}\n"
        f"Repositories: {len(repositories)} matching {prefix}*\n"
        f"Team        : {team} (id={found['id']}, {len(members)} members)\n"
    )

    outside: Dict[str, List[str]] = {}
    total = 0
    for repo_name in repositories:
        for login in repo_collaborators(gitea, organization, repo_name):
            total += 1
            if login.lower() not in members:
                outside.setdefault(login, []).append(repo_name)

    typer.echo(f"Collaborator entries checked: {total}")
    typer.echo(f"Distinct accounts not in {team}: {len(outside)}\n")
    for login in sorted(outside, key=str.lower):
        typer.echo(f"  {login:24} {' '.join(outside[login])}")


@app.command("report")
def cmd_report(
    groups_file: str = typer.Argument("group.txt"),
    excel: str = typer.Option("", "--excel", help="spreadsheet for names and IDs"),
    out: str = typer.Option("groups_report.txt", "--out"),
    unregistered_out: str = typer.Option("unregistered.txt", "--unregistered-out"),
    org: str = typer.Option("", "--org"),
) -> None:
    """Write the grouping, with names and student IDs, and the list of accounts
    that still have no Gitea account."""
    groups = read_groups(groups_file)
    if not groups:
        typer.echo(f"Error: no groups in {groups_file}")
        raise typer.Exit(1)
    gitea = teapot()
    organization = org_name(org)
    df = load_spreadsheet(find_spreadsheet(excel))
    identity = identity_map(df)

    accounts: List[str] = []
    seen: Set[str] = set()
    for members in groups:
        for account in members:
            if account.lower() not in seen:
                seen.add(account.lower())
                accounts.append(account)
    registered, missing = split_registered(gitea, accounts)
    registered_set = {a.lower() for a in registered}

    lines: List[str] = [
        f"Grouping -- organization {organization}",
        f"Source: {groups_file}" + (f" + {excel}" if excel else ""),
        f"{len(groups)} groups / {len(accounts)} accounts, "
        f"{len(registered)} on Gitea, {len(missing)} not registered",
        "",
    ]
    with_unregistered: List[Tuple[int, List[str]]] = []
    small: List[int] = []
    for index, members in enumerate(groups, 1):
        lines.append(f"Group {index:02d}  ({len(members)} members)")
        for account in members:
            name, student_id = identity.get(account.lower(), ("", ""))
            status = "registered" if account.lower() in registered_set else "NOT registered"
            lines.append(
                f"    {account:22} {name or '-':12} {student_id or '-':14} {status}"
            )
        bad = [m for m in members if m.lower() not in registered_set]
        if bad:
            with_unregistered.append((index, bad))
        if len(members) < DEFAULT_GROUP_SIZE:
            small.append(index)
        lines.append("")

    lines += [
        "Summary",
        f"  groups              : {len(groups)}",
        f"  accounts            : {len(accounts)}",
        f"  on Gitea            : {len(registered)}",
        f"  not registered      : {len(missing)}",
        f"  groups with missing : {len(with_unregistered)}",
        f"  groups below 3      : {len(small)} {small}",
        "",
        "Accounts with no Gitea user, by group",
    ]
    for index, bad in with_unregistered:
        lines.append(f"  group {index:02d}: {', '.join(bad)}")

    text = "\n".join(lines)
    typer.echo(text)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        typer.echo(f"\nWrote {out}")

    if unregistered_out:
        out_lines: List[str] = [
            f"Accounts with no Gitea user -- organization {organization}",
            f"Source: {groups_file}",
            "",
            "By group",
            "",
        ]
        self_typed = 0
        teammate_typed = 0
        empty: List[str] = []
        for index, members in enumerate(groups, 1):
            bad = [m for m in members if m.lower() not in registered_set]
            if not bad:
                continue
            others = len(members) - len(bad)
            if others == 0:
                empty.append(f"group {index:02d} ({len(members)} members)")
            out_lines.append(f"group {index:02d}  {len(members)} members, {others} registered")
            for account in bad:
                name, student_id = identity.get(account.lower(), ("", ""))
                if account.lower() in identity:
                    source = "self (from the login, not typed)"
                    self_typed += 1
                else:
                    source = "teammate (typed by hand)"
                    teammate_typed += 1
                out_lines.append(
                    f"    {account:22} {name or '-':12} {student_id or '-':14} {source}"
                )
            out_lines.append("")
        out_lines += [
            "By source",
            f"  self      : {self_typed}",
            f"  teammate  : {teammate_typed}",
            "",
            "Groups where nobody can be added (0 collaborators)",
        ]
        for item in empty:
            out_lines.append(f"  {item}")
        with open(unregistered_out, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + "\n")
        typer.echo(f"Wrote {unregistered_out}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
