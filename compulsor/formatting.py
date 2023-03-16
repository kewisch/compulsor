import datetime
import re

import jira2markdown

RE_FIND_MARKER = re.compile(
    r"PULSEDESC(?:\[(?P<pulse>[^\]]+)\])?:(?P<description>[^\n]+)"
)


def insprint(sprintinfo, dt):
    fmt = "%Y-%m-%d"
    isodt = datetime.datetime.strptime(dt[:10], fmt)
    isostart = datetime.datetime.strptime(sprintinfo["startDate"][:10], fmt)
    isoend = datetime.datetime.strptime(sprintinfo["endDate"][:10], fmt)

    return isodt >= isostart and isodt <= isoend


def formatitem(item, showissue=None):
    descr = jira2markdown.convert(item.strip())
    if showissue:
        return f"* \\[[{showissue.key}]({showissue.permalink()})\\] {descr}"
    else:
        return "* " + descr


def formatrange(start, end):
    if end.year == start.year:
        return f"Dates: {start.strftime('%B')} {start.day} – {end.strftime('%B')} {end.day}"
    else:
        return f"Dates: {start.strftime('%B')} {start.day}, {start.year} – {end.strftime('%B')} {end.day} {end.year}"


def isodate(dt):
    return datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S.%fZ")


def sprintinfo(ctx, sprintid, keys):
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
            if match and match.group("pulse") == sprintid:
                tprint(formatitem(match.group("description"), showissue=showissue))

        for comment in issue.fields.comment.comments:
            match = RE_FIND_MARKER.search(comment.body)
            if match and (
                match.group("pulse") == sprintid
                or (not match.group("pulse") and insprint(sprintinfo, comment.created))
            ):
                tprint(formatitem(match.group("description"), showissue=showissue))

    return text
