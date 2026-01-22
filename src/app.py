from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from models.responses import (
    PlayerUUIDResponse,
    GuildResponse,
    PlayerProfileResponse,
    BedwarsResponse,
    ErrorResponse
)
import aiohttp
import uvicorn
import math
from utils import get_rank, get_username, format_timestamp, get_uuid, get_level_info

app = FastAPI(
    docs_url="/swagger_docs",
    redoc_url="/docs",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/uuid/{username_or_uuid}", response_model=PlayerUUIDResponse, responses={404: {"model": ErrorResponse}})
async def get_player_uuid(username_or_uuid: str):
    count = 1
    for i in username_or_uuid:
        count += 1
    if "-" in username_or_uuid or count > 16:
        name = await get_username(username_or_uuid)
        if name == "not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Player not found"
            )
        return {
            "success": True,
            "data": {
                "uuid": username_or_uuid,
                "username": name
            }
        }

    
    uuid = await get_uuid(username_or_uuid)
    if uuid == "not found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    return {
        "success": True,
        "data": {
            "uuid": uuid,
            "username": username_or_uuid
        }
    }

@app.get("/api/profile/{uuid}", response_model=PlayerProfileResponse, responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def get_profile(uuid: str, api_key: str):
    uuid = str(uuid).replace("-", "")
    url = f"https://api.hypixel.net/v2/player?uuid={uuid}"
    headers = {"API-Key": api_key}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            
            if resp.status == 401 or data == {"success": False, "cause": "Invalid API key"}:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )
            elif resp.status == 422 or data == {"success":False,"cause":"Malformed UUID"}:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid UUID"
                )
            elif resp.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Hypixel API error"
                )

    if not data.get("success", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )

    player_data = data.get("player", {})
    if not player_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player data not found"
        )

    # Get player username
    username = await get_username(uuid)
    rank = await get_rank(uuid, data)

    # Get timestamps
    first_login = player_data.get("firstLogin", 0)
    last_login = player_data.get("lastLogin", 0)
    last_logout = player_data.get("lastLogout", 0)
    
    return {
        "success": True,
        "data": {
            "uuid": uuid,
            "username": username,
            "rank": rank,
            "first_login": first_login,
            "first_login_pretty": format_timestamp(first_login),
            "last_login": last_login,
            "last_login_pretty": format_timestamp(last_login),
            "last_logout": last_logout,
            "last_logout_pretty": format_timestamp(last_logout),
            "exp": player_data.get("networkExp", 0),
            "network_level": round((math.sqrt((2 * player_data.get("networkExp", 0)) + 30625) / 50) - 2.5, 2),
            "karma": player_data.get("karma", 0),
            "achievement_points": player_data.get("achievementPoints", 0),
            "total_rewards": player_data.get("totalRewards", 0),
            "total_daily_rewards": player_data.get("totalDailyRewards", 0),
            "reward_streak": player_data.get("rewardStreak", 0),
            "reward_score": player_data.get("rewardScore", 0),
            "reward_high_score": player_data.get("rewardHighScore", 0),
            "most_recent_game": player_data.get("mostRecentGameType", "unknown"),
            "online": player_data.get("lastLogin", 0) > player_data.get("lastLogout", 0),
            "images": {
                "full_skin_image": f"https://crafatar.com/renders/body/{uuid}",
                "3d_head_image": f"https://crafatar.com/renders/head/{uuid}",
                "2d_head_image": f"https://crafatar.com/avatars/{uuid}",
                "network_level_image": f"https://gen.plancke.io/exp/{username}.png",
            }
        }
    }

@app.get("/api/guild/{uuid}", response_model=GuildResponse, responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def get_guild(uuid: str, api_key: str):
    uuid = str(uuid).replace("-", "")
    url = f"https://api.hypixel.net/v2/guild?player={uuid}"
    headers = {"API-Key": api_key}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            guild_data = await resp.json()
            
            if resp.status == 401 or guild_data == {"success": False, "cause": "Invalid API key"}:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )
            elif resp.status == 422 or guild_data == {"success":False,"cause":"Malformed UUID"}:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid UUID"
                )
            elif resp.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Hypixel API error"
                )

    # Process Guild Data
    guild = guild_data.get("guild")
    if not guild:
        return {
            "success": True,
            "data": {
                "in_guild": False
            }
        }

    # Get player username
    username = await get_username(uuid)

    # Get timestamps
    created = guild.get("created", 0)

    guild_info = {
        "uuid": uuid,
        "username": username,
        "in_guild": True,
        "name": guild.get("name", "not found"),
        "tag": guild.get("tag", "not found"),
        "tag_color": guild.get("tagColor", "not found"),
        "exp": guild.get("exp", 0),
        "created": created,
        "created_pretty": format_timestamp(created)
    }
    
    # Process Guild Members
    guild_members = guild.get("members", [])
    formatted_members = []
    current_member_data = {}

    for member in guild_members:
        member_uuid = member.get("uuid")
        if not member_uuid:
            continue

        # Get member username
        try:
            member_username = await get_username(member_uuid)
        except:
            member_username = "Unknown"

        # Get timestamps
        joined = member.get("joined", 0)

        member_info = {
            "uuid": member_uuid,
            "username": member_username,
            "joined": joined,
            "joined_pretty": format_timestamp(joined),
            "quests": member.get("questParticipation", 0),
            "rank": member.get("rank", "not found"),
            "weekly_exp": member.get("expHistory", {}).get("weekly", 0),
            "daily_exp": member.get("expHistory", {}).get("daily", 0),
            "role": member.get("role", "not found")
        }
        formatted_members.append(member_info)
        
        if member_uuid == uuid:
            current_member_data = member

    # Get timestamps for current member
    joined = current_member_data.get("joined", 0)

    # Add member data to guild info
    guild_info.update({
        "quests": current_member_data.get("quests", 0),
        "joined": joined,
        "joined_pretty": format_timestamp(joined),
        "weekly_exp": current_member_data.get("weekly_exp", 0),
        "daily_exp": current_member_data.get("daily_exp", 0),
        "role": current_member_data.get("role", "not found"),
        "members": formatted_members
    })

    return {
        "success": True,
        "data": guild_info
    }
    
@app.get("/api/bedwars/{uuid}", response_model=BedwarsResponse, responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def bedwars_stats(uuid: str, api_key: str):
    uuid = str(uuid).replace("-", "")
    url = f"https://api.hypixel.net/v2/player?uuid={uuid}"
    headers = {"API-Key": api_key}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            
            if resp.status == 401 or data == {"success": False, "cause": "Invalid API key"}:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )
            elif resp.status == 422 or data == {"success":False,"cause":"Malformed UUID"}:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid UUID"
                )
            elif resp.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Hypixel API error"
                )

    if not data.get("success", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )

    player_data = data.get("player", {})
    if not player_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player data not found"
        )
    
    xp = player_data["stats"]["Bedwars"]["Experience"]
    level, prestige, xp_to_next_level, progress_percentage = get_level_info(xp)
    
    bedwars_data = player_data.get("stats", {}).get("Bedwars", {})
    if not bedwars_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BedWars data not found"
        )
    

    slumber_tickets_max = 0
    if bedwars_data.get("slumber", {}).get("bag_type", None) == "MINI_WALLET":
        slumber_tickets_max = 25
    elif bedwars_data.get("slumber", {}).get("bag_type", None) == "LIGHT_SLUMBERS_WALLET":
        slumber_tickets_max = 99
    elif bedwars_data.get("slumber", {}).get("bag_type", None) == "LIGHT_IMPERIAL_WALLET":
        slumber_tickets_max = 500
    elif bedwars_data.get("slumber", {}).get("bag_type", None) == "EXPLORERS_WALLET":
        slumber_tickets_max = 5_000
    elif bedwars_data.get("slumber", {}).get("bag_type", None) == "HOTEL_STAFF_WALLET":
        slumber_tickets_max = 10_000
    elif bedwars_data.get("slumber", {}).get("bag_type", None) == "PLATINUM_MEMBERSHIP_WALLET":
        slumber_tickets_max = 100_000
    elif bedwars_data.get("slumber", {}).get("bag_type", None):
        slumber_tickets_max = 0
    
    # Global tickets and tokens
    resources = {
        "tokens": bedwars_data.get("coins", 0),
        "slumber_tickets": bedwars_data.get("slumber", {}).get("tickets", 0),
        "slumber_tickets_max": slumber_tickets_max,
        "slumber_tickets_total": bedwars_data.get("slumber", {}).get("total_tickets_earned", 0),
    }
    
    # Define combined gamemode mappings
    combined_modes = {
        "ultimate": ["eight_two_ultimate_", "four_four_ultimate_"],
        "lucky": ["eight_two_lucky_", "four_four_lucky_"],
        "rush": ["eight_two_rush_", "four_four_rush_"],
        "swap": ["eight_two_swap_", "four_four_swap_"]
    }
    
    gamemodes = {
        "overall": "",                                   # ALl gamemodes
        "core": None,                                    # Special case: will sum up solo, doubles, threes, fours
        "eight_one": "eight_one_",                       # Solo
        "eight_two": "eight_two_",                       # Doubles 
        "four_three": "four_three_",                     # Threes
        "four_four": "four_four_",                       # Fours
        "two_four": "two_four_",                         # 4v4
        "four_four_armed": "four_four_armed_",           # Fours armed
        "castle": "castle_",                             # Castle 40v40
        "four_four_lucky": "four_four_lucky_",           # Fours lucky
        "eight_two_lucky": "eight_two_lucky_",           # Doubles lucky
        "eight_two_rush": "eight_two_rush_",             # Doubles rush
        "four_four_rush": "four_four_rush_",             # Fours rush
        "eight_two_swap": "eight_two_swap_",             # Doubles swap
        "four_four_swap": "four_four_swap_",             # Fours swap
        "eight_two_ultimate": "eight_two_ultimate_",     # Doubles ultimate
        "four_four_ultimate": "four_four_ultimate_",     # Fours ultimate
        "four_four_underworld": "four_four_underworld_", # Fours underworld
        "four_four_voidless": "four_four_voidless_"      # Fours voidless
    }
    
    # Add combined modes to gamemodes dictionary
    gamemodes.update({
        "ultimate": None,  # Will combine eight_two_ultimate and four_four_ultimate
        "lucky": None,     # Will combine eight_two_lucky and four_four_lucky
        "rush": None,      # Will combine eight_two_rush and four_four_rush
        "swap": None       # Will combine eight_two_swap and four_four_swap
    })
    
    core_modes = ["eight_one_", "eight_two_", "four_three_", "four_four_"]
    
    stats = {}
    bedwars_data = player_data.get("stats", {}).get("Bedwars", {})
    
    for mode_key, mode_prefix in gamemodes.items():
        if mode_key in combined_modes:
            # Get stats for combined modes (like ultimate, lucky, etc)
            prefixes = combined_modes[mode_key]
            wins = sum(bedwars_data.get(f"{prefix}wins_bedwars", 0) for prefix in prefixes)
            losses = sum(bedwars_data.get(f"{prefix}losses_bedwars", 0) for prefix in prefixes)
            final_kills = sum(bedwars_data.get(f"{prefix}final_kills_bedwars", 0) for prefix in prefixes)
            final_deaths = sum(bedwars_data.get(f"{prefix}final_deaths_bedwars", 0) for prefix in prefixes)
            kills = sum(bedwars_data.get(f"{prefix}kills_bedwars", 0) for prefix in prefixes)
            deaths = sum(bedwars_data.get(f"{prefix}deaths_bedwars", 0) for prefix in prefixes)
            beds_broken = sum(bedwars_data.get(f"{prefix}beds_broken_bedwars", 0) for prefix in prefixes)
            beds_lost = sum(bedwars_data.get(f"{prefix}beds_lost_bedwars", 0) for prefix in prefixes)
            
            mode_stats = {
                # Resources
                f"{mode_key}_emeralds": sum(bedwars_data.get(f"{prefix}emerald_resources_collected_bedwars", 0) for prefix in prefixes),
                f"{mode_key}_diamonds": sum(bedwars_data.get(f"{prefix}diamond_resources_collected_bedwars", 0) for prefix in prefixes),
                f"{mode_key}_gold": sum(bedwars_data.get(f"{prefix}gold_resources_collected_bedwars", 0) for prefix in prefixes),
                f"{mode_key}_iron": sum(bedwars_data.get(f"{prefix}iron_resources_collected_bedwars", 0) for prefix in prefixes),
                
                # Standard stats
                f"{mode_key}_wins": wins,
                f"{mode_key}_losses": losses,
                f"{mode_key}_final_kills": final_kills,
                f"{mode_key}_final_deaths": final_deaths,
                f"{mode_key}_kills": kills,
                f"{mode_key}_deaths": deaths,
                f"{mode_key}_beds_broken": beds_broken,
                f"{mode_key}_beds_lost": beds_lost,
                
                # Ratios
                f"{mode_key}_wlr": round(wins / losses if losses > 0 else wins, 2),
                f"{mode_key}_kdr": round(kills / deaths if deaths > 0 else kills, 2),
                f"{mode_key}_fkdr": round(final_kills / final_deaths if final_deaths > 0 else final_kills, 2),
                f"{mode_key}_bblr": round(beds_broken / beds_lost if beds_lost > 0 else beds_broken, 2)
            }
        elif mode_key == "core":
            # Get stats for core modes
            wins = sum(bedwars_data.get(f"{prefix}wins_bedwars", 0) for prefix in core_modes)
            losses = sum(bedwars_data.get(f"{prefix}losses_bedwars", 0) for prefix in core_modes)
            final_kills = sum(bedwars_data.get(f"{prefix}final_kills_bedwars", 0) for prefix in core_modes)
            final_deaths = sum(bedwars_data.get(f"{prefix}final_deaths_bedwars", 0) for prefix in core_modes)
            kills = sum(bedwars_data.get(f"{prefix}kills_bedwars", 0) for prefix in core_modes)
            deaths = sum(bedwars_data.get(f"{prefix}deaths_bedwars", 0) for prefix in core_modes)
            beds_broken = sum(bedwars_data.get(f"{prefix}beds_broken_bedwars", 0) for prefix in core_modes)
            beds_lost = sum(bedwars_data.get(f"{prefix}beds_lost_bedwars", 0) for prefix in core_modes)
            
            mode_stats = {
                # Resources
                f"{mode_key}_emeralds": sum(bedwars_data.get(f"{prefix}emerald_resources_collected_bedwars", 0) for prefix in core_modes),
                f"{mode_key}_diamonds": sum(bedwars_data.get(f"{prefix}diamond_resources_collected_bedwars", 0) for prefix in core_modes),
                f"{mode_key}_gold": sum(bedwars_data.get(f"{prefix}gold_resources_collected_bedwars", 0) for prefix in core_modes),
                f"{mode_key}_iron": sum(bedwars_data.get(f"{prefix}iron_resources_collected_bedwars", 0) for prefix in core_modes),
                
                # Standard stats
                f"{mode_key}_wins": wins,
                f"{mode_key}_losses": losses,
                f"{mode_key}_final_kills": final_kills,
                f"{mode_key}_final_deaths": final_deaths,
                f"{mode_key}_kills": kills,
                f"{mode_key}_deaths": deaths,
                f"{mode_key}_beds_broken": beds_broken,
                f"{mode_key}_beds_lost": beds_lost,
                
                # Ratios
                f"{mode_key}_wlr": round(wins / losses if losses > 0 else wins, 2),
                f"{mode_key}_kdr": round(kills / deaths if deaths > 0 else kills, 2),
                f"{mode_key}_fkdr": round(final_kills / final_deaths if final_deaths > 0 else final_kills, 2),
                f"{mode_key}_bblr": round(beds_broken / beds_lost if beds_lost > 0 else beds_broken, 2)
            }
        else:
            # Get stats for individual mode
            wins = bedwars_data.get(f"{mode_prefix}wins_bedwars", 0)
            losses = bedwars_data.get(f"{mode_prefix}losses_bedwars", 0)
            final_kills = bedwars_data.get(f"{mode_prefix}final_kills_bedwars", 0)
            final_deaths = bedwars_data.get(f"{mode_prefix}final_deaths_bedwars", 0)
            kills = bedwars_data.get(f"{mode_prefix}kills_bedwars", 0)
            deaths = bedwars_data.get(f"{mode_prefix}deaths_bedwars", 0)
            beds_broken = bedwars_data.get(f"{mode_prefix}beds_broken_bedwars", 0)
            beds_lost = bedwars_data.get(f"{mode_prefix}beds_lost_bedwars", 0)
            
            mode_stats = {
                # Resources
                f"{mode_key}_emeralds": bedwars_data.get(f"{mode_prefix}emerald_resources_collected_bedwars", 0),
                f"{mode_key}_diamonds": bedwars_data.get(f"{mode_prefix}diamond_resources_collected_bedwars", 0),
                f"{mode_key}_gold": bedwars_data.get(f"{mode_prefix}gold_resources_collected_bedwars", 0),
                f"{mode_key}_iron": bedwars_data.get(f"{mode_prefix}iron_resources_collected_bedwars", 0),
                
                # Standard stats
                f"{mode_key}_wins": wins,
                f"{mode_key}_losses": losses,
                f"{mode_key}_final_kills": final_kills,
                f"{mode_key}_final_deaths": final_deaths,
                f"{mode_key}_kills": kills,
                f"{mode_key}_deaths": deaths,
                f"{mode_key}_beds_broken": beds_broken,
                f"{mode_key}_beds_lost": beds_lost,
                
                # Ratios
                f"{mode_key}_wlr": round(wins / losses if losses > 0 else wins, 2),
                f"{mode_key}_kdr": round(kills / deaths if deaths > 0 else kills, 2),
                f"{mode_key}_fkdr": round(final_kills / final_deaths if final_deaths > 0 else final_kills, 2),
                f"{mode_key}_bblr": round(beds_broken / beds_lost if beds_lost > 0 else beds_broken, 2)
            }
        stats[mode_key] = mode_stats
    
    try:
        next_level = int(str(level).split(".")[0]) + 1
    except KeyError:
        next_level = level + 1
        
    return {
        "success": True,
        "data": {
            "uuid": uuid,
            "username": player_data.get("displayname", "not found"),
            "xp": xp,
            "level": level,
            "prestige": prestige,
            "next_level": next_level,
            "xp_to_next_level": xp_to_next_level,
            "progress_to_next_level_percentage": progress_percentage,
            "resources": resources,
            "stats": stats
        }
    }
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)