import json
import os

from discord.ext import commands

from Util import Logging, Utils

MASTER_CONFIG = dict()
SERVER_CONFIGS = dict()
MASTER_LOADED = False
CONFIG_VERSION = 0


def v2(config):
    config["ACTION_CHANNEL"] = 0
    return config

def v3(config):
    for entry in ["RAID_WARNING_AMOUNT", "RAID_WARNING_TIMEFRAME", "RAID_WARNING_MESSAGE", "RAID_ALARM_AMOUNT", "RAID_ALARM_TIMEFRAME"]:
        del config[entry]
    return config

# migrators for the configs, do NOT increase the version here, this is done by the migration loop
# doubt we'll actually need the full flexibility this offers but i made it for gearbot so might as well use it to future proof this bot
MIGRATORS = [v2, v3]


async def on_ready(bot: commands.Bot):
    global CONFIG_VERSION
    CONFIG_VERSION = Utils.fetch_from_disk("config/template")["VERSION"]
    Logging.info(f"Current template config version: {CONFIG_VERSION}")
    Logging.info(f"Loading configurations for {len(bot.guilds)} guilds.")
    for guild in bot.guilds:
        Logging.info(f"Loading info for {guild.name} ({guild.id}).")
        load_config(guild.id)


def load_master():
    global MASTER_CONFIG, MASTER_LOADED
    try:
        with open('config/master.json', 'r') as jsonfile:
            MASTER_CONFIG = json.load(jsonfile)
            MASTER_LOADED = True
    except FileNotFoundError:
        Logging.error("Unable to load config, running with defaults.")
    except Exception as e:
        Logging.error("Failed to parse configuration.")
        print(e)
        raise e


def load_config(guild):
    global SERVER_CONFIGS
    config = Utils.fetch_from_disk(f'config/{guild}')
    if "VERSION" not in config and len(config) < 15:
        Logging.info(f"The config for {guild} is to old to migrate, resetting")
        config = dict()
    else:
        if "VERSION" not in config:
            config["VERSION"] = 0
        SERVER_CONFIGS[guild] = update_config(guild, config)
    if len(config) is 0:
        Logging.info(f"No config available for {guild}, creating a blank one.")
        SERVER_CONFIGS[guild] = Utils.fetch_from_disk("config/template")
        save(guild)


def update_config(guild, config):
    v = config["VERSION"]
    while config["VERSION"] < CONFIG_VERSION:
        Logging.info(f"Upgrading config version from version {v} to {v+1}")
        d = f"config/backups/v{v}"
        if not os.path.isdir(d):
            os.makedirs(d)
        Utils.save_to_disk(f"{d}/{guild}", config)
        config = MIGRATORS[config["VERSION"]-1](config)
        config["VERSION"] += 1
        Utils.save_to_disk(f"config/{guild}", config)

    return config


def get_var(id, key):
    if id is None:
        raise ValueError("Where is this coming from?")
    if id not in SERVER_CONFIGS.keys():
        Logging.info(f"Config entry requested before config was loaded for guild {id}, loading config for it")
        load_config(id)
    return SERVER_CONFIGS[id][key]


def set_var(id, key, value):
    SERVER_CONFIGS[id][key] = value
    save(id)


def save(id):
    global SERVER_CONFIGS
    with open(f'config/{id}.json', 'w') as jsonfile:
        jsonfile.write((json.dumps(SERVER_CONFIGS[id], indent=4, skipkeys=True, sort_keys=True)))


def get_master_var(key, default=None):
    global MASTER_CONFIG, MASTER_LOADED
    if not MASTER_LOADED:
        load_master()
    if key not in MASTER_CONFIG.keys():
        MASTER_CONFIG[key] = default
        save_master()
    return MASTER_CONFIG[key]


def save_master():
    global MASTER_CONFIG
    Utils.save_to_disk("config/master", MASTER_CONFIG)
