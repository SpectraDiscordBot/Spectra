import motor.motor_asyncio
import os
from dotenv import load_dotenv

load_dotenv()

client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("MONGO_URI"))
db = client["Spectra"]
autorole_collection = db["AutoRole"]
welcome_messages_collection = db["WelcomeMessages"]
antispam_collection = db["AntiSpam"]
toxicity_collection = db["ToxicitySettings"]
warning_collection = db["Warnings"]
modlog_collection = db["ModLogs"]
cases_collection = db["Cases"]
custom_cmds_collection = db["CustomCommands"]
custom_prefix_collection = db["CustomPrefixes"]
report_collection = db["Reports"]
button_roles_collection = db["ButtonRoles"]
button_settings_collection = db["ButtonRoleSettings"]
reaction_roles_collection = db["ReactionRoles"]
note_collection = db["Notes"]
verification_collection = db["Verification"]
anti_ping_collection = db["AntiPing"]
ban_appeal_collection = db["BanAppeals"]
server_stats_collection = db["ServerStats"]