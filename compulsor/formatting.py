import datetime
import re
import sys

import jira2markdown

RE_FIND_MARKER = re.compile(
    r"PULSEDESC(?:\[(?P<tags>[^\]]+)\])?:\s*(?P<description>[^\n]+)"
)
RE_FIND_TYPO = re.compile(r"PULSDESC|PULSEDEC|PULSEDESC[^:\[]")


def insprint(sprintinfo, dt):
    fmt = "%Y-%m-%d"
    isodt = datetime.datetime.strptime(dt[:10], fmt)
    isostart = datetime.datetime.strptime(sprintinfo["startDate"][:10], fmt)
    isoend = datetime.datetime.strptime(sprintinfo["endDate"][:10], fmt)

    return isodt >= isostart and isodt <= isoend


def formatitem(item, showissue=None, private=False):
    descr = jira2markdown.convert(item.strip())
    confidential = "[CONFIDENTIAL] " if private else ""
    if showissue:
        return (
            f"* \\[[{showissue.key}]({showissue.permalink()})\\]{confidential}{descr}"
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


def typocheck(match, text, url):
    foundtypo = RE_FIND_TYPO.search(text)
    if foundtypo and not match:
        sys.stderr.write(f"Warning: Potential typo in {url}: {foundtypo.group(0)}\n")


def sprintinfo(ctx, sprintid, keys, showprivate=False):
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
        fields="description,comment",
    )

    for issue in issues:
        showissue = issue if keys else None
        if issue.fields.description:
            match = RE_FIND_MARKER.search(issue.fields.description)
            tags, hasprivate = gettags(match)
            typocheck(match, issue.fields.description, issue.permalink())
            if match and (not hasprivate or showprivate) and sprintid in tags:
                tprint(formatitem(match.group("description"), showissue=showissue))

        for comment in issue.fields.comment.comments:
            match = RE_FIND_MARKER.search(comment.body)
            typocheck(match, comment.body, issue.permalink())
            if not match:
                continue

            tags, hasprivate = gettags(match)
            if not showprivate and hasprivate:
                continue

            if sprintid in tags or (
                not len(tags) and insprint(sprintinfo, comment.created)
            ):
                tprint(
                    formatitem(
                        match.group("description"),
                        showissue=showissue,
                        private=hasprivate,
                    )
                )

    return text
