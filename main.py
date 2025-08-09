import os
import re
import asyncio
import discord
from discord.ext import commands, tasks

# ====== ENV ======
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ROLE_MENTION = os.getenv("ROLE_MENTION")  # e.g. "<@&1397029826568781997>"
GUILD_ID = os.getenv("GUILD_ID")          # optional: your server ID as string for instant slash sync

# ====== INTENTS / BOT ======
intents = discord.Intents.default()
intents.message_content = True  # needed for prefix commands like !ping
bot = commands.Bot(command_prefix="!", intents=intents)

# ====== FUTBIN CHECK (snscrape) ======
last_seen_tweet_id = None

def extract_6pm_content(text: str) -> str | None:
    m = re.match(r"^🚨\s*6pm\s*Content:\s*(.*)$", text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None

@tasks.loop(minutes=2)
async def check_for_tweets():
    """Poll @FUTBIN tweets every 2 minutes using snscrape."""
    global last_seen_tweet_id
    await bot.wait_until_ready()

    try:
        import snscrape.modules.twitter as sntwitter
    except Exception as e:
        print(f"❌ snscrape not available: {e}")
        return

    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel is None:
            print("❌ Could not resolve CHANNEL_ID. Check the env var.")
            return

        scraper = sntwitter.TwitterUserScraper("FUTBIN")
        count = 0
        async for tweet in scraper.get_items():
            if count >= 10:
                break
            count += 1

            content = tweet.content or ""
            if content.startswith("🚨 6pm Content:"):
                if last_seen_tweet_id != tweet.id:
                    last_seen_tweet_id = tweet.id
                    cleaned = extract_6pm_content(content) or content
                    msg = f"{ROLE_MENTION}\n**6pm Content:**\n\n{cleaned}"
                    await channel.send(msg[:2000])
                    print("✅ Posted new 6pm content.")
                else:
                    print("ℹ️ 6pm content already posted.")
                break
        else:
            print("🔍 No matching 6pm Content tweet found.")

    except Exception as e:
        print(f"Error checking tweets: {e}")

# ====== EVENTS ======
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def setup_hook():
    # Sync slash commands (guild-scoped if GUILD_ID set, else global)
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            synced = await bot.tree.sync(guild=guild)
        else:
            synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

    check_for_tweets.start()

# ====== PREFIX COMMAND ======
@bot.command(name="ping", help="Check if the bot is alive (prefix: !ping)")
async def ping_prefix(ctx: commands.Context):
    await ctx.send("🏓 Pong! Bot is online (prefix).")

# ====== SLASH COMMAND ======
@bot.tree.command(name="ping", description="Check if the bot is alive (slash)")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    await interaction.followup.send("🏓 Pong! Bot is online (slash).")

# ====== STARTUP ======
async def main():
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())


















    
















