import time
from db import blacklist_collection

blacklist_cache = {}
CACHE_TTL = 300

async def is_blacklisted(id_: int):
    cached = blacklist_cache.get(id_)
    now = time.time()
    if cached and cached[1] > now:
        return cached[0]

    doc = await blacklist_collection.find_one({"_id": id_})
    is_bl = bool(doc)
    blacklist_cache[id_] = (is_bl, now + CACHE_TTL)
    return is_bl

async def blacklist_check(ctx):
    if await is_blacklisted(ctx.author.id):
        return False
    if ctx.guild and await is_blacklisted(ctx.guild.id):
        await ctx.send("This server is blacklisted from using this bot.")
        return False
    return True