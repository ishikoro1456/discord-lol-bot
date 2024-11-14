import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import os
from datetime import datetime, timedelta

TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# インテントの定義
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True
intents.message_content = True  # 必要に応じてTrueに設定

# ボットの初期化
bot = commands.Bot(command_prefix='!', intents=intents)

# LoLのロール定義
LOL_ROLES = ["TOP", "JG", "MID", "ADC", "SUP"]

# サーバーごとの前回選ばれたメンバーのIDを保持する辞書
selected_members_last_round = {}

# サーバーごとの最後にselectコマンドが実行された時間を保持する辞書
last_select_time = {}

# コマンド1: ランダムに2チームに分ける
@bot.tree.command(name="team", description="Leagueチャンネルのメンバーをランダムに2チームに分けます。")
async def team(interaction: discord.Interaction):
    await interaction.response.defer()

    # ボイスチャンネルのメンバーを取得
    members = interaction.user.voice.channel.members if interaction.user.voice and interaction.user.voice.channel else []

    if interaction.user.voice and interaction.user.voice.channel and interaction.user.voice.channel.name != "League":
        await interaction.followup.send("このコマンドは「League」チャンネルでのみ使用できます。")
        return

    if len(members) < 2:
        await interaction.followup.send("チームに分けるには、2人以上のメンバーが必要です。")
        return

    random.shuffle(members)
    midpoint = len(members) // 2
    team1 = members[:midpoint]
    team2 = members[midpoint:]

    team1_names = ", ".join([m.display_name for m in team1])
    team2_names = ", ".join([m.display_name for m in team2])

    embed = discord.Embed(title="チーム分け", color=discord.Color.blue())
    embed.add_field(name="チーム1", value=team1_names, inline=False)
    embed.add_field(name="チーム2", value=team2_names, inline=False)

    await interaction.followup.send(embed=embed)

# コマンド2: 指定人数のメンバーを選ぶ（前回選ばれたメンバーを除外）
@bot.tree.command(name="select", description="Leagueチャンネルから指定した人数のメンバーを選びます。")
@app_commands.describe(count="選ぶ人数")
async def select(interaction: discord.Interaction, count: int):
    global selected_members_last_round, last_select_time
    await interaction.response.defer()

    guild_id = interaction.guild.id

    members = interaction.user.voice.channel.members if interaction.user.voice and interaction.user.voice.channel else []

    if interaction.user.voice and interaction.user.voice.channel and interaction.user.voice.channel.name != "League":
        await interaction.followup.send("このコマンドは「League」チャンネルでのみ使用できます。")
        return

    if count > len(members):
        await interaction.followup.send(f"{count}人を選ぶことはできません。現在のメンバー数は {len(members)} 人です。")
        return

    if guild_id not in selected_members_last_round:
        selected_members_last_round[guild_id] = set()
        last_select_time[guild_id] = datetime.utcnow()

    last_selected = selected_members_last_round[guild_id]

    eligible_members = [m for m in members if m.id not in last_selected]

    if not eligible_members:
        eligible_members = members
        await interaction.followup.send("全メンバーを再度対象とします。")

    if len(eligible_members) >= count:
        selected = random.sample(eligible_members, count)
    else:
        remaining_count = count - len(eligible_members)
        remaining_members = [m for m in members if m.id in last_selected]
        selected = eligible_members + random.sample(remaining_members, remaining_count)

    selected_members_last_round[guild_id] = set(m.id for m in selected)
    last_select_time[guild_id] = datetime.utcnow()
    selected_names = ", ".join([m.display_name for m in selected])

    embed = discord.Embed(title="選ばれたメンバー", color=discord.Color.green())
    embed.add_field(name="メンバー", value=selected_names, inline=False)

    await interaction.followup.send(embed=embed)

# コマンド3: LoLのロールを割り当てる
@bot.tree.command(name="role", description="LeagueチャンネルのメンバーにLoLのロールを割り当てます。")
@app_commands.describe(roles="カンマ区切りのLoLロール（例：TOP,JG,MID,ADC,SUP）。指定がない場合はすべてのロールから割り当て")
async def role(interaction: discord.Interaction, roles: str = None):
    await interaction.response.defer()

    members = interaction.user.voice.channel.members if interaction.user.voice and interaction.user.voice.channel else []

    if interaction.user.voice and interaction.user.voice.channel and interaction.user.voice.channel.name != "League":
        await interaction.followup.send("このコマンドは「League」チャンネルでのみ使用できます。")
        return

    if len(members) > 5:
        await interaction.followup.send("このコマンドは5人以下のメンバーでのみ使用できます。現在のメンバー数は {} 人です。".format(len(members)))
        return

    if not roles:
        roles_list = LOL_ROLES[:len(members)]
    else:
        roles_list = [role.strip().upper() for role in roles.split(",")]

    if len(roles_list) != len(members):
        await interaction.followup.send(f"提供されたロール数（{len(roles_list)}）がメンバー数（{len(members)}）と一致しません。")
        return

    random.shuffle(roles_list)

    embed = discord.Embed(title="LoLロールの割り当て", color=discord.Color.purple())
    for member, role_name in zip(members, roles_list):
        embed.add_field(name=member.display_name, value=role_name, inline=False)

    await interaction.followup.send(embed=embed)

# コマンド4: 選択履歴をリセットする（全ユーザー用）
@bot.tree.command(name="reset_selection", description="選択履歴をリセットします。")
async def reset_selection(interaction: discord.Interaction):
    global selected_members_last_round, last_select_time
    guild_id = interaction.guild.id

    await interaction.response.defer(ephemeral=True)

    if guild_id in selected_members_last_round:
        selected_members_last_round[guild_id].clear()
    if guild_id in last_select_time:
        del last_select_time[guild_id]

    await interaction.followup.send("選択履歴をリセットしました。", ephemeral=True)

# 背景タスク: 1.5時間の非操作後に選択履歴をリセット
@tasks.loop(minutes=5)
async def auto_reset_selection():
    current_time = datetime.utcnow()
    reset_guilds = []

    for guild_id, last_time in list(last_select_time.items()):
        if current_time - last_time >= timedelta(hours=1, minutes=30):
            reset_guilds.append(guild_id)

    for guild_id in reset_guilds:
        selected_members_last_round[guild_id].clear()
        del last_select_time[guild_id]
        print(f"{datetime.utcnow()} - Guild ID {guild_id} の選択履歴を自動リセットしました。")

@bot.event
async def on_ready():
    print(f'ログインしました: {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'{len(synced)}個のコマンドを同期しました。')
    except Exception as e:
        print(f'コマンドの同期に失敗しました: {e}')
    auto_reset_selection.start()

bot.run(TOKEN)

from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()
