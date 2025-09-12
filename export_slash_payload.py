# export_full_slash_payload.py
import json
import inspect
import typing
import enum
import discord
from discord import app_commands
from discord.ext import commands

OPTION_TYPE = {
    "SUB_COMMAND": 1,
    "SUB_COMMAND_GROUP": 2,
    "STRING": 3,
    "INTEGER": 4,
    "BOOLEAN": 5,
    "USER": 6,
    "CHANNEL": 7,
    "ROLE": 8,
    "MENTIONABLE": 9,
    "NUMBER": 10,
    "ATTACHMENT": 11
}

def _truncate(s: str, max_len: int):
    if s is None:
        return ""
    return s if len(s) <= max_len else s[:max_len]

def _unwrap_optional(annot):
    origin = typing.get_origin(annot)
    if origin is typing.Union:
        args = [a for a in typing.get_args(annot) if a is not type(None)]
        if args:
            return _unwrap_optional(args[0])
    return annot

def _pytype_to_option_type(annot) -> int:
    if annot is inspect._empty:
        return OPTION_TYPE["STRING"]
    annot = _unwrap_optional(annot)

    if getattr(annot, "__origin__", None) is typing.Literal:
        first = typing.get_args(annot)[0]
        if isinstance(first, bool):
            return OPTION_TYPE["BOOLEAN"]
        if isinstance(first, int):
            return OPTION_TYPE["INTEGER"]
        if isinstance(first, float):
            return OPTION_TYPE["NUMBER"]
        return OPTION_TYPE["STRING"]

    if isinstance(annot, type) and issubclass(annot, enum.Enum):
        sample = list(annot)[0].value
        if isinstance(sample, int):
            return OPTION_TYPE["INTEGER"]
        if isinstance(sample, float):
            return OPTION_TYPE["NUMBER"]
        if isinstance(sample, bool):
            return OPTION_TYPE["BOOLEAN"]
        return OPTION_TYPE["STRING"]

    if annot in (str,):
        return OPTION_TYPE["STRING"]
    if annot in (int,):
        return OPTION_TYPE["INTEGER"]
    if annot in (float,):
        return OPTION_TYPE["NUMBER"]
    if annot in (bool,):
        return OPTION_TYPE["BOOLEAN"]

    name = getattr(annot, "__name__", str(annot)).lower()
    if "member" in name or "user" in name:
        return OPTION_TYPE["USER"]
    if "role" in name:
        return OPTION_TYPE["ROLE"]
    if "channel" in name:
        return OPTION_TYPE["CHANNEL"]
    if "attachment" in name:
        return OPTION_TYPE["ATTACHMENT"]

    return OPTION_TYPE["STRING"]

def _choices_from_annotation(annot):
    origin = typing.get_origin(annot)
    out = []
    if origin is typing.Literal:
        for v in typing.get_args(annot):
            out.append({"name": str(v), "value": v})
        return out
    if isinstance(annot, type) and issubclass(annot, enum.Enum):
        for member in annot:
            out.append({"name": str(member.name), "value": member.value})
        return out
    return out

def _param_to_option(param: inspect.Parameter) -> dict:
    name = param.name.lower()
    annot = param.annotation
    choices = _choices_from_annotation(annot)
    option_type = _pytype_to_option_type(annot)
    required = param.default is inspect._empty
    description = getattr(param, "description", None) or "No description"

    opt = {
        "name": name[:32],
        "description": _truncate(description, 100) or "No description",
        "type": option_type,
        "required": required
    }

    if choices:
        opt["choices"] = choices[:25]

    if not required:
        opt["default"] = param.default

    return opt

def _command_options_from_callback(cmd: commands.Command) -> list:
    opts = []
    try:
        sig = inspect.signature(cmd.callback)
    except (ValueError, TypeError):
        return opts

    for p in sig.parameters.values():
        if p.name in ("self", "ctx", "interaction"):
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        opts.append(_param_to_option(p))
    return opts

def _subcommand_option_from_command(sub: commands.Command) -> dict:
    return {
        "name": sub.name[:32],
        "description": _truncate(sub.description or (sub.callback.__doc__ or "No description"), 100),
        "type": OPTION_TYPE["SUB_COMMAND"],
        "options": _command_options_from_callback(sub)
    }

def _subcommand_group_option_from_group(group: commands.Group) -> dict:
    # Each child of the group should be a subcommand (not more nested groups ideally).
    children_opts = []
    for child in group.commands:
        if isinstance(child, commands.Group):
            # If library nested a Group inside a Group, convert each inner child's subcommands
            inner_children = []
            for inner in child.commands:
                inner_children.append(_subcommand_option_from_command(inner))
            children_opts.append({
                "name": child.name[:32],
                "description": _truncate(child.description or (child.callback.__doc__ or "No description"), 100),
                "type": OPTION_TYPE["SUB_COMMAND_GROUP"],
                "options": inner_children
            })
        else:
            children_opts.append(_subcommand_option_from_command(child))

    return {
        "name": group.name[:32],
        "description": _truncate(group.description or (group.callback.__doc__ or "No description"), 100),
        "type": OPTION_TYPE["SUB_COMMAND_GROUP"],
        "options": children_opts
    }

def build_payload_from_hybrid(cmd: commands.Command) -> dict:
    obj = {
        "name": cmd.name[:32],
        "type": 1,
        "description": _truncate(cmd.description or (getattr(cmd.callback, "__doc__", "") or "No description"), 100)
    }

    options = []

    # If command is a group, handle children
    if isinstance(cmd, commands.Group):
        # Two buckets: direct subcommands, and subcommand groups
        for child in cmd.commands:
            if isinstance(child, commands.Group):
                options.append(_subcommand_group_option_from_group(child))
            else:
                options.append(_subcommand_option_from_command(child))

        # Also allow the group itself having parameters (rare: group callback used)
        group_params = _command_options_from_callback(cmd)
        if group_params:
            # Prepend group params as regular options before subcommands (not typical for discord app command design)
            options = group_params + options
    else:
        options = _command_options_from_callback(cmd)

    if options:
        obj["options"] = options

    return obj

def _serialize_app_command(acmd: app_commands.AppCommand) -> dict:
    # Defensive: app_commands.Command has .name, .description, .type, .options
    data = {
        "name": getattr(acmd, "name", "")[:32],
        "type": getattr(acmd, "type", 1),
        "description": _truncate(getattr(acmd, "description", "") or "No description", 100)
    }

    opts = []
    for o in getattr(acmd, "options", []) or []:
        # o may be app_commands.AppCommandOption
        opt = {
            "name": getattr(o, "name", "")[:32],
            "description": _truncate(getattr(o, "description", "") or "No description", 100),
            "type": getattr(o, "type", OPTION_TYPE["STRING"]),
            "required": getattr(o, "required", False)
        }
        if getattr(o, "choices", None):
            choices = []
            for c in o.choices:
                # c may be AppCommandChoice or similar
                choices.append({"name": getattr(c, "name", str(getattr(c, "value", c)))[:100], "value": getattr(c, "value", c)})
            opt["choices"] = choices[:25]
        # sub-options (subcommands / groups)
        if getattr(o, "options", None):
            # recurse (these are already in app command shapes)
            subopts = []
            for so in o.options:
                subopts.append(_serialize_app_command_option_like(so))
            opt["options"] = subopts
        opts.append(opt)

    if opts:
        data["options"] = opts
    return data

def _serialize_app_command_option_like(o) -> dict:
    opt = {
        "name": getattr(o, "name", "")[:32],
        "description": _truncate(getattr(o, "description", "") or "No description", 100),
        "type": getattr(o, "type", OPTION_TYPE["STRING"]),
        "required": getattr(o, "required", False)
    }
    if getattr(o, "choices", None):
        choices = []
        for c in o.choices:
            choices.append({"name": getattr(c, "name", str(getattr(c, "value", c)))[:100], "value": getattr(c, "value", c)})
        opt["choices"] = choices[:25]
    if getattr(o, "options", None):
        sub = []
        for so in o.options:
            sub.append(_serialize_app_command_option_like(so))
        opt["options"] = sub
    return opt

async def export_all_slash_commands(bot: commands.Bot, filename: str = "slash_payload.json", guild_id: int = None):
    """
    Export a combined payload list of application commands.
    If guild_id is provided it will try to fetch guild commands from bot.tree.fetch_commands(guild=discord.Object(id=guild_id))
    Otherwise it will use bot.tree.get_commands() (cached global commands).
    Missing commands (hybrids not in tree) are constructed from code introspection.
    """
    payloads = []
    seen_names = set()

    # 1) Try to get the real registered app commands from the tree (most accurate)
    try:
        if guild_id:
            tree_cmds = await bot.tree.fetch_commands(guild=discord.Object(id=guild_id))
        else:
            # bot.tree.get_commands() returns list; use that if fetch not needed
            tree_cmds = list(bot.tree.get_commands())
    except Exception:
        tree_cmds = list(bot.tree.get_commands())

    # Serialize tree commands
    for ac in tree_cmds:
        try:
            payloads.append(_serialize_app_command(ac))
            seen_names.add(ac.name)
        except Exception:
            # fallback: minimal capture
            payloads.append({"name": getattr(ac, "name", ""), "type": getattr(ac, "type", 1), "description": getattr(ac, "description", "")})
            seen_names.add(getattr(ac, "name", ""))

    # 2) Inspect code-defined HybridCommands for any not present in the tree (unsynced / not yet registered)
    for cmd in list(bot.commands):
        # include HybridCommand or HybridGroup
        try:
            is_hybrid = isinstance(cmd, commands.HybridCommand)
        except Exception:
            is_hybrid = False

        if not is_hybrid:
            continue

        if cmd.name in seen_names:
            continue

        # build from definition
        try:
            obj = build_payload_from_hybrid(cmd)
            payloads.append(obj)
            seen_names.add(cmd.name)
        except Exception:
            # ignore broken commands
            continue

    # write file
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payloads, f, indent=2, ensure_ascii=False)

    print(f"Exported {len(payloads)} application command payload(s) to {filename}")