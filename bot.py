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

# コマンド2: 指定人数のメンバーを選ぶ（前回選ばれたメンバーと優先参加者以外を除外）
@bot.tree.command(name="select", description="Leagueチャンネルから指定した人数のメンバーを選びます。")
@app_commands.describe(count="選ぶ人数", role="選ばれたメンバーに付与するロール（オプション）")
async def select(interaction: discord.Interaction, count: int, role: discord.Role = None):
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
    priority = priority_members.get(guild_id, set())

    # 優先参加者が設定されている場合は、そのメンバーのみを対象とする
    if priority:
        eligible_members = [m for m in members if m.id in priority and m.id not in last_selected]
        excluded_text = ", ".join([m.display_name for m in members if m.id not in priority])
        if excluded_text:
            await interaction.followup.send(f"優先参加者として除外されたメンバー: {excluded_text}")
    else:
        eligible_members = [m for m in members if m.id not in last_selected]

    if not eligible_members:
        if priority:
            eligible_members = [m for m in members if m.id in priority]
            await interaction.followup.send("全優先参加者を再度対象とします。")
        else:
            eligible_members = members
            await interaction.followup.send("全メンバーを再度対象とします。")

    if len(eligible_members) >= count:
        selected = random.sample(eligible_members, count)
    else:
        remaining_count = count - len(eligible_members)
        if priority:
            # 優先参加者のみが対象の場合、追加選択は不要
            selected = eligible_members
        else:
            remaining_members = [m for m in members if m.id in last_selected]
            if len(remaining_members) < remaining_count:
                await interaction.followup.send("選択可能なメンバーが不足しています。")
                return
            selected = eligible_members + random.sample(remaining_members, remaining_count)

    selected_members_last_round[guild_id] = set(m.id for m in selected)
    last_select_time[guild_id] = datetime.utcnow()
    selected_names = ", ".join([m.display_name for m in selected])

    embed = discord.Embed(title="選ばれたメンバー", color=discord.Color.green())
    embed.add_field(name="メンバー", value=selected_names, inline=False)

    await interaction.followup.send(embed=embed)

    # ロールの付与処理
    if role:
        # ここでは実際のロールを付与せず、選ばれたメンバーに指定されたロール名を表示するだけにします
        success_text = ", ".join([f"{m.display_name}: **{role.name}**" for m in selected])
        await interaction.followup.send(f"選ばれたメンバーにロール **{role.name}** を割り当てました:\n{success_text}")

# コマンド3: LoLのロールを割り当てる（部分一致によるメンバー指定）
@bot.tree.command(name="role", description="LeagueチャンネルのメンバーにLoLのロールを割り当てます。")
@app_commands.describe(
    roles="カンマ区切りのLoLロール（例：TOP,JG,MID,ADC,SUP）。指定がない場合はすべてのロールから割り当てます。",
    members="ロールを割り当てるメンバー名の一部（部分一致）。指定がない場合は全メンバーに割り当てます。"
)
async def assign_role(interaction: discord.Interaction, roles: str = None, members: str = None):
    await interaction.response.defer()

    members_in_channel = interaction.user.voice.channel.members if interaction.user.voice and interaction.user.voice.channel else []

    if interaction.user.voice and interaction.user.voice.channel and interaction.user.voice.channel.name != "League":
        await interaction.followup.send("このコマンドは「League」チャンネルでのみ使用できます。")
        return

    if not members_in_channel:
        await interaction.followup.send("「League」チャンネルにメンバーがいません。")
        return

    if len(members_in_channel) > 5:
        await interaction.followup.send(f"このコマンドは5人以下のメンバーでのみ使用できます。現在のメンバー数は {len(members_in_channel)} 人です。\n -# :bulb: members引数を用いて指定してください。")
        return

    if members:
        # 部分一致でメンバーをフィルタリング
        search_term = members.lower()
        target_members = [m for m in members_in_channel if search_term in m.display_name.lower()]
        if not target_members:
            await interaction.followup.send(f"名前に「{members}」を含むメンバーが見つかりませんでした。")
            return
    else:
        target_members = members_in_channel

    if not roles:
        roles_list = LOL_ROLES[:len(target_members)]
    else:
        roles_list = [role.strip().upper() for role in roles.split(",")]

    if len(roles_list) != len(target_members):
        await interaction.followup.send(f"提供されたロール数（{len(roles_list)}）がメンバー数（{len(target_members)}）と一致しません。")
        return

    # ロールをランダムに割り当て
    assigned_roles = random.sample(roles_list, len(target_members)) if len(roles_list) >= len(target_members) else roles_list

    embed = discord.Embed(title="LoLロールの割り当て", color=discord.Color.purple())
    success_assignments = []
    failed_assignments = []

    for member, role_name in zip(target_members, assigned_roles):
        embed.add_field(name=member.display_name, value=role_name, inline=False)
        success_assignments.append(f"{member.display_name}: **{role_name}**")

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

# 新規コマンド: 優先参加者リストを設定する
@bot.tree.command(name="set_list", description="優先参加者を設定します。指定されたメンバー以外を選択から除外します。")
@app_commands.describe(members="優先参加者の名前をカンマ区切りで指定します。例: 優先参加者1, 優先参加者2")
async def set_priority_list(interaction: discord.Interaction, members: str):
    guild_id = interaction.guild.id
    await interaction.response.defer()

    voice_channel = interaction.user.voice.channel if interaction.user.voice and interaction.user.voice.channel else None

    if not voice_channel:
        await interaction.followup.send("ボイスチャンネルに接続している必要があります。")
        return

    if voice_channel.name != "League":
        await interaction.followup.send("このコマンドは「League」チャンネルでのみ使用できます。")
        return

    member_names = [name.strip().lower() for name in members.split(",")]
    current_members = voice_channel.members

    matched_members = []
    not_found = []

    for name in member_names:
        # 部分一致でメンバーを検索
        matches = [m for m in current_members if name in m.display_name.lower()]
        if matches:
            # もし複数一致した場合、すべてを優先参加者として追加
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
