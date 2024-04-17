import datetime
import re
import sys

import jira2markdown
from spellchecker import SpellChecker

RE_FIND_MARKER = re.compile(
    r"PULSEDESC(?:\[(?P<tags>[^\]]+)\])?:\s*(?P<description>[^\n]+)"
)
RE_FIND_TYPO = re.compile(
    "|".join(map(lambda word: word.upper(), SpellChecker().candidates("confidential")))
)
RE_STRIP_ISSUE = re.compile(r"\\\[\[\w+-\d+\]\([^)]+\)\\\] (.*)")
CONFIDENTIAL_TAG = "\\[CONFIDENTIAL\\]"


def insprint(sprintinfo, dt):
    fmt = "%Y-%m-%d"
    isodt = datetime.datetime.strptime(dt[:10], fmt)
    isostart = datetime.datetime.strptime(sprintinfo["startDate"][:10], fmt)
    isoend = datetime.datetime.strptime(sprintinfo["endDate"][:10], fmt)

    return isodt >= isostart and isodt <= isoend


def formatitem(item, showissue=None, private=False):
    markdown = jira2markdown.convert(item.strip())
    descr = (
        "\n".join(map(lambda line: line + "\\", markdown.splitlines()))
        .rstrip("\\")
        .strip()
    )

    confidential = CONFIDENTIAL_TAG if private else ""

    if private:
        descr = descr.replace("CONFIDENTIAL", "", 1).strip("\\ \t\n")

    if showissue:
        return (
            f"* \\[[{showissue.key}]({showissue.permalink()})\\]{confidential} {descr}"
        )
    else:
        return f"* {confidential}{descr}"


def formatrange(start, end):
    if end.year == start.year:
        return f"Dates: {start.strftime('%B')} {start.day} – {end.strftime('%B')} {end.day}"
    else:
        return f"Dates: {start.strftime('%B')} {start.day}, {start.year} – {end.strftime('%B')} {end.day} {end.year}"


def isodate(dt):
    return datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S.%fZ")


def gettags(match):
    tags = set(
        map(lambda x: x.strip(), (match.group("tags") or "").split(","))
        if match
        else []
    )
    private = "private" in tags

    if private:
        tags.remove("private")

    return tags, private


def typocheck(text, url):
    for typo in re.finditer(RE_FIND_TYPO, text):
        if typo.group(0) == "CONFIDENTIAL":
            continue
        sys.stderr.write(f"Warning: Potential typo in {url}: {typo.group(0)}\n")


def stripinfo(string, private, keys=True):
    lines = []
    stripcontinue = False
    for line in string.splitlines():
        if stripcontinue or (not private and CONFIDENTIAL_TAG in line):
            stripcontinue = False
            if line[-1] == "\\":
                stripcontinue = True
            continue

        if keys:
            lines.append(line)
        else:
            lines.append(re.sub(RE_STRIP_ISSUE, r"\1", line))

    return "\n".join(lines)


def sprintinfo(ctx, sprintid, keys, reportnamefield, showprivate=False):
    text = ""

    def tprint(*args):
        nonlocal text
        text += " ".join(map(str, args)) + "\n"

    sprints = ctx.sprints

    if sprintid == "latest":
        activesprints = ctx.jira.sprints(ctx.toolconfig["board"], state="active")
        sprintid = activesprints[0].name.split(" ")[-1]

    sprint = f"Pulse {sprintid}"
    if sprint not in sprints:
        raise Exception(f"Could not find sprint {sprint}")

    sprintinfo = sprints[sprint]

    tprint(f"## {sprintinfo['name']}")
    tprint(
        formatrange(isodate(sprintinfo["startDate"]), isodate(sprintinfo["endDate"]))
    )
    if sprintinfo["goal"]:
        tprint(sprintinfo["goal"])

    tprint("")

    issues = ctx.jira.search_issues(
        f'project = "{ctx.toolconfig["project"]}" AND sprint = "{sprint}"',
        fields="summary,status,parent," + reportnamefield,
    )

    for issue in sorted(
        issues, key=lambda x: x.fields.parent.key if hasattr(x.fields, "parent") else ""
    ):
        showissue = issue if keys else None
        reportfield = getattr(issue.fields, reportnamefield, None)

        if reportfield:
            if reportfield.strip() == "SKIP":
                sys.stderr.write(
                    f"Warning: Skipping {issue.permalink()} ({issue.fields.summary}) as it was marked SKIP\n"
                )
                continue

            typocheck(reportfield, issue.permalink())
            hasprivate = "CONFIDENTIAL" in reportfield

            if not hasprivate or showprivate:
                tprint(formatitem(reportfield, showissue=showissue, private=hasprivate))
        else:
            sys.stderr.write(
                f"Warning: Issue {issue.permalink()} ('{issue.fields.summary}' - {issue.fields.status}) has no pulse description\n"
            )

    return text
