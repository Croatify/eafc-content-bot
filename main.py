import os
import sys
import re
import time
import random
import asyncio
import requests
import discord
from discord.ext import commands, tasks

def yesno(v): return "✅" if v else "❌"

# ---------- ENV ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID")
ROLE_MENTION = os.getenv("ROLE_MENTION")
GUILD_ID_RAW = os.getenv("GUILD_ID")

# Optional: prefer this Nitter; otherwise we'll rotate through a list
PREFERRED_NITTER = os.getenv("NITTER_URL", "").strip().rstrip("/")

# Trim
if CHANNEL_ID_RAW: CHANNEL_ID_RAW = CHANNEL_ID_RAW.strip()
if GUILD_ID_RAW:   GUILD_ID_RAW   = GUILD_ID_RAW.strip()
if ROLE_MENTION:   ROLE_MENTION   = ROLE_MENTION.strip()
if DISCORD_TOKEN:  DISCORD_TOKEN  = DISCORD_TOKEN.strip()

print("==== ENV CHECK ====")
print(f"DISCORD_TOKEN present: {yesno(bool(DISCORD_TOKEN))}")
print(f"CHANNEL_ID present:   {yesno(bool(CHANNEL_ID_RAW))}  value={CHANNEL_ID_RAW!r}")
print(f"ROLE_MENTION present: {yesno(bool(ROLE_MENTION))}    value={ROLE_MENTION!r}")
print(f"GUILD_ID present:     {yesno(bool(GUILD_ID_RAW))}    value={GUILD_ID_RAW!r}")
print("====================")

missing = []
if not DISCORD_TOKEN: missing.append("DISCORD_TOKEN")
if not CHANNEL_ID_RAW: missing.append("CHANNEL_ID")
if not ROLE_MENTION: missing.append("ROLE_MENTION")
if not GUILD_ID_RAW: missing.append("GUILD_ID")
if missing:
    print(f"❌ Missing environment variables: {', '.join(missing)}")
    sys.exit(1)

# Cast IDs
try:
    CHANNEL_ID = int(CHANNEL_ID_RAW)
    GUILD_ID = int(GUILD_ID_RAW)
except ValueError:
    print("❌ CHANNEL_ID and GUILD_ID must be numbers only.")
    sys.exit(1)

GUILD = discord.Object(id=GUILD_ID)

# ---------- BOT ----------
intents = discord.Intents.default()
intents.message_content = True  # for prefix command
bot = commands.Bot(command_prefix="!", intents=intents)

last_seen_tweet_id = None

# ---------- Helpers ----------
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
]
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": random.choice(UA_LIST)})

# A rotating list of public Nitter instances (will change over time)
NITTER_POOL = [i.rstrip("/") for i in filter(None, [
    PREFERRED_NITTER,
    "https://nitter.net",
    "https://nitter.fdn.fr",
    "https://nitter.moomoo.me",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.1d4.us",
    "https://ntrqq.com",  # sometimes works, sometimes not
])]

def extract_6pm_content(text: str) -> str | None:
    m = re.match(r"^🚨\s*6pm\s*Content:\s*(.*)$", text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None

def try_snscrape():
    """Return (tweet_id, body) or (None, None) using snscrape; raise on import error."""
    try:
        import snscrape.modules.twitter as sntwitter  # type: ignore
    except Exception as e:
        # Bubble up so caller can switch to fallback
        raise RuntimeError(f"snscrape import failed: {e}")

    scraper = sntwitter.TwitterUserScraper("FUTBIN")
    count = 0
    # snscrape returns an async generator in recent builds
    async def _scan():
        nonlocal count
        async for tweet in scraper.get_items():
            if count >= 10:
                break
            count += 1
            text = tweet.content or ""
            if text.startswith("🚨 6pm Content:"):
                return str(tweet.id), text
        return None, None
    return _scan()

def fetch_via_nitter():
    """Rotate through Nitter instances with backoff; return (tweet_id, body) or (None, None)."""
    pool = list(dict.fromkeys(NITTER_POOL))  # unique & keep order
    random.shuffle(pool)  # distribute load
    for base in pool:
        rss_url = f"{base}/FUTBIN/rss"
        backoff = 3
        for attempt in range(3):
            try:
                r = SESSION.get(rss_url, timeout=15)
                status = r.status_code
                if status == 200:
                    text = r.text
                    items = text.split("<item>")
                    for raw in items[1:10]:  # scan first ~9
                        def tag(name):
                            s = raw.find(f"<{name}>"); e = raw.find(f"</{name}>")
                            if s == -1 or e == -1: return ""
                            return raw[s+len(name)+2:e].strip()
                        title = tag("title")
                        desc  = tag("description")
                        link  = tag("link")
                        guid  = tag("guid")
                        body = title or desc or ""
                        if body.startswith("🚨 6pm Content:"):
                            m = re.search(r"/status/(\d+)", link or guid or "")
                            tw_id = m.group(1) if m else (guid or link or "")
                            print(f"✅ Nitter hit: {base}")
                            return tw_id, body
                    print(f"🔍 No 6pm item on {base}")
                    break  # break attempts; move to next instance
                elif status in (403, 429, 502, 503, 520, 522):
                    print(f"⚠ Nitter {base} status {status}, retry {attempt+1}/3 after {backoff}s")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                else:
                    print(f"⚠ Nitter {base} unexpected status {status}, moving on")
                    break
            except Exception as e:
                print(f"⚠ Nitter {base} error: {e}, moving on")
                break
    return None, None

@tasks.loop(minutes=2)
async def check_for_tweets():
    """Try snscrape first; if it fails, use robust Nitter rotation with backoff."""
    global last_seen_tweet_id
    await bot.wait_until_ready()

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"❌ Could not resolve CHANNEL_ID={CHANNEL_ID}. Is the bot in that server and can it view the channel?")
        return

    # Try snscrape
    try:
        tw_id, body = await try_snscrape()
        if body and body.startswith("🚨 6pm Content:"):
            if last_seen_tweet_id != tw_id:
                last_seen_tweet_id = tw_id
                cleaned = extract_6pm_content(body) or body
                msg = f"{ROLE_MENTION}\n**6pm Content:**\n\n{cleaned}"
                await channel.send(msg[:2000])
                print("✅ Posted new 6pm content (snscrape).")
            else:
                print("ℹ️ 6pm content already posted (snscrape).")
            return
        else:
            print("🔍 No matching 6pm Content tweet found (snscrape).")
            return
    except Exception as e:
        print(f"❌ snscrape import/usage failed: {e}")

    # Fallback to Nitter rotation
    tw_id, body = fetch_via_nitter()
    if body and body.startswith("🚨 6pm Content:"):
        if last_seen_tweet_id != tw_id:
            last_seen_tweet_id = tw_id
            cleaned = extract_6pm_content(body) or body
            msg = f"{ROLE_MENTION}\n**6pm Content:**\n\n{cleaned}"
            await channel.send(msg[:2000])
            print("✅ Posted new 6pm content (Nitter fallback).")
        else:
            print("ℹ️ 6pm content already posted (Nitter fallback).")
    else:
        print("🔍 No matching 6pm Content tweet found (fallback).")

# ----- events & commands -----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

# Register slash command at module level (guild-scoped) so sync sees it
@bot.tree.command(name="ping", description="Check if the bot is alive (slash)", guild=GUILD)
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    await interaction.followup.send("🏓 Pong! Bot is online (slash).")

@bot.event
async def setup_hook():
    try:
        synced = await bot.tree.sync(guild=GUILD)
        print(f"✅ Synced {len(synced)} slash command(s) to guild {GUILD_ID}.")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

    # Prefix command too
    @bot.command(name="ping", help="Check if the bot is alive (prefix: !ping)")
    async def ping_prefix(ctx: commands.Context):
        await ctx.send("🏓 Pong! Bot is online (prefix).")

    check_for_tweets.start()

async def main():
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())











    
















