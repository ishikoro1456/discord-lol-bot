import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import os
from datetime import datetime, timedelta

TOKEN = os.getenv('TOKEN')

if TOKEN is None:
    raise ValueError("DISCORD_BOT_TOKENが設定されていません。")


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

# サーバーごとの優先参加者のIDを保持する辞書
priority_members = {}

# コマンド1: ランダムに2チームに分ける
@bot.tree.command(name="team", description="Leagueチャンネルのメンバーをランダムに2チームに分けます。")
async def team(interaction: discord.Interaction):
    await interaction.response.defer()

    # ボイスチャンネルのメンバーを取得
    members = interaction.user.voice.channel.members if interaction.user.voice and interaction.user.voice.channel else []

    if not interaction.user.voice or not interaction.user.voice.channel or interaction.user.voice.channel.name != "League":
        await interaction.followup.send("LeagueチャンネルのVCに入り、そこからコマンドを使用してください。")
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

# コマンドの新規実装: ロール割り当て
@bot.tree.command(name="role", description="Leagueチャンネルにいる人にLoLロールを割り当てます。")
async def role(interaction: discord.Interaction):
    await interaction.response.defer()

    members_in_channel = interaction.user.voice.channel.members if interaction.user.voice and interaction.user.voice.channel else []

    if not interaction.user.voice or not interaction.user.voice.channel or interaction.user.voice.channel.name != "League":
        await interaction.followup.send("LeagueチャンネルのVCに入り、そこからコマンドを使用してください。")
        return

    if not members_in_channel:
        await interaction.followup.send("現在Leagueチャンネルに人がいません。")
        return

    # セレクトメニュー作成
    options = [
        discord.SelectOption(label=member.display_name, value=str(member.id))
        for member in members_in_channel
    ]

    select_menu = discord.ui.Select(placeholder="割り当たいたいメンバーを選択", options=options)

    async def select_callback(interaction: discord.Interaction):
        selected_ids = select_menu.values
        selected_members = [member for member in members_in_channel if str(member.id) in selected_ids]

        if len(selected_members) > 5:
            await interaction.response.send_message("5人までしか選択できません。", ephemeral=True)
            return

        # 割り当て
        assigned_roles = random.sample(LOL_ROLES, len(selected_members))
        role_assignment = "\n".join([f"{member.display_name}: {role}" for member, role in zip(selected_members, assigned_roles)])

        embed = discord.Embed(title="LoLロール割り当て", color=discord.Color.purple())
        embed.add_field(name="割り当て結果", value=role_assignment, inline=False)

        await interaction.response.send_message(embed=embed)

    select_menu.callback = select_callback
    view = discord.ui.View()
    view.add_item(select_menu)

    await interaction.followup.send("Leagueチャンネルの人を選択してください。", view=view)

# set_listコマンドの更新
@bot.tree.command(name="set_list", description="優先参加者を設定します。前の設定を上書きします。")
@app_commands.describe(members="優先参加者の名前をカンマ区切りで指定します。例: 優先参加者1, 優先参加者2")
async def set_priority_list(interaction: discord.Interaction, members: str):
    guild_id = interaction.guild.id
    await interaction.response.defer()

    voice_channel = interaction.user.voice.channel if interaction.user.voice and interaction.user.voice.channel else None

    if not voice_channel:
        await interaction.followup.send("ボイスチャンネルに接続している必要があります。")
        return

    if voice_channel.name != "League":
        await interaction.followup.send("このコマンドは「League」チャンネルでのみ使用可能です。")
        return

    member_names = [name.strip().lower() for name in members.split(",")]
    current_members = voice_channel.members

    matched_members = []
    not_found = []

    for name in member_names:
        # 部分一致でメンバーを検索
        matches = [m for m in current_members if name in m.display_name.lower()]
        if matches:
            matched_members.extend(matches)
        else:
            not_found.append(name)

    if not matched_members:
        await interaction.followup.send("指定された優先参加者が見つかりませんでした。")
        return

    priority_members[guild_id] = set(m.id for m in matched_members)

    success_text = ", ".join([m.display_name for m in matched_members])

    if not_found:
        not_found_text = ", ".join(not_found)
        await interaction.followup.send(f"以下の名前のメンバーが見つかりませんでした: {not_found_text}")

    await interaction.followup.send(f"優先参加者として以下のメンバーを設定しました: {success_text}")

@bot.event
def on_ready():
    print(f'ログインしました: {bot.user}')
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
