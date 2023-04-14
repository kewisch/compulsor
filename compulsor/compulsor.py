import http.client
import logging
import os.path
import stat
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
@click.option("--config", default="~/.canonicalrc", help="Config file location.")
@click.pass_context
def main(ctx, debug, config):
    ctx.ensure_object(dict)

    configpath = os.path.expanduser(config)

    # Check if the config file is locked to mode 600. Add a loophole in case it is being passed in
    # via pipe, it appears on macOS the pipes are mode 660 instead.
    statinfo = os.stat(configpath, dir_fd=None, follow_symlinks=True)
    if (statinfo.st_mode & (stat.S_IROTH | stat.S_IRGRP)) != 0 and not stat.S_ISFIFO(
        statinfo.st_mode
    ):
        raise click.ClickException(f"Credentials file {config} is not chmod 600")

    with open(configpath) as fd:
        config = yaml.safe_load(fd)

    if not config:
        raise click.ClickException(f"Could not load config file {configpath}")

    ctx.obj = Context(config, debug)


@main.command(help="Display a formatted pulse report")
@click.argument("pulse", nargs=-1)
@click.option("-k", "--keys", is_flag=True, help="Show Jira keys in the report")
@click.option("-p", "--private", is_flag=True, help="Show private items in the report")
@click.pass_obj
def showpulse(ctx, pulse, keys, private):
    if not len(pulse):
        pulse = ["latest"]

    print(
        "\n".join(
            map(
                lambda sprintid: sprintinfo(ctx, sprintid, keys, showprivate=private),
                pulse,
            )
        )
    )


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
@click.pass_obj
def postpulse(ctx, discourses, pulse, alldiscourse):
    if alldiscourse:
        discourses = ctx.toolconfig["discourse"].keys()
    if not len(discourses):
        discourses = ["ubuntu"]

    for discourse in discourses:
        keys = ctx.toolconfig["discourse"][discourse]["keys"]
        topic = ctx.toolconfig["discourse"][discourse]["topic"]
        showprivate = ctx.toolconfig["discourse"][discourse]["private"]

        client = CanDiscourseClient(ctx.serviceconfig["discourse"][discourse])
        info = sprintinfo(ctx, pulse, keys, showprivate=showprivate)
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
