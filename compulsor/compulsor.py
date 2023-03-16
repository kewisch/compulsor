import http.client
import logging
import os.path
import stat
import sys
from functools import cached_property

import click
import yaml
from discourse import CanDiscourseClient
from formatting import sprintinfo
from jira import JIRA


class Context:
    def __init__(self, config, debug=False):
        jconfig = config["services"]["jira"]
        self.jira = JIRA(
            config["services"]["jira"]["url"],
            basic_auth=(jconfig["username"], jconfig["token"]),
        )

        self.toolconfig = config["tools"]["compulsor"]
        self.serviceconfig = config["services"]
        self.debug = debug

        if debug:
            logging.basicConfig()
            logging.getLogger().setLevel(logging.DEBUG)
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True
            http.client.HTTPConnection.debuglevel = 1

    @cached_property
    def sprints(self):
        return self.jira.sprints_by_name(self.toolconfig["board"])


@click.group()
@click.option("--debug", is_flag=True, default=False, help="Enable debugging")
@click.pass_context
def main(ctx, debug):
    ctx.ensure_object(dict)

    configpath = os.path.expanduser("~/.canonicalrc")
    statinfo = os.stat(configpath, dir_fd=None, follow_symlinks=True)
    if (statinfo.st_mode & (stat.S_IROTH | stat.S_IRGRP)) != 0:
        print("Credentials file is not chmod 600")
        sys.exit(1)

    with open(configpath) as fd:
        config = yaml.safe_load(fd)

    ctx.obj = Context(config, debug)


@main.command(help="Display a formatted pulse report")
@click.argument("pulse", nargs=-1)
@click.option("-k", "--keys", is_flag=True, help="Show Jira keys in the report")
@click.pass_context
def showpulse(ctx, pulse, keys):
    ctx = ctx.obj

    if not len(pulse):
        pulse = ["latest"]

    print("\n".join(map(lambda sprintid: sprintinfo(ctx, sprintid, keys), pulse)))


@main.command(help="Post pulse reports to discourse")
@click.argument("pulse", default="latest")
@click.argument("discourses", nargs=-1)
@click.option(
    "-a",
    "--all",
    "alldiscourse",
    is_flag=True,
    help="Post pulse report to all configured discourses",
)
@click.pass_context
def postpulse(ctx, discourses, pulse, alldiscourse):
    ctx = ctx.obj

    if alldiscourse:
        discourses = ctx.toolconfig["discourse"].keys()
    if not len(discourses):
        discourses = ["ubuntu"]

    for discourse in discourses:
        keys = ctx.toolconfig["discourse"][discourse]["keys"]
        topic = ctx.toolconfig["discourse"][discourse]["topic"]

        client = CanDiscourseClient(ctx.serviceconfig["discourse"][discourse])
        info = sprintinfo(ctx, pulse, keys)
        info = click.edit(info)

        if not info.startswith("## Pulse"):
            print(f"Error: Text is invalid, skipping {discourse} discourse")
            continue

        res = client.create_post(topic_id=topic, content=info)
        print(
            f'{ctx.serviceconfig["discourse"][discourse]["url"]}/t/{res["topic_slug"]}/{res["topic_id"]}/{res["post_number"]}'
        )


if __name__ == "__main__":
    main()
