# Read-only terminal display helper for manual HW6 screenshot capture.
# It never sends chat requests and never writes to MongoDB. The visible output
# is intentionally human-readable so an instructor can inspect both roles.

$python = 'C:\Projects\data260-8844\.venv-hw6\Scripts\python.exe'
$code = @'
import os
from pymongo import MongoClient

print("Student: Vrishin KunnathamParambath | SID4: 8844")
print("Conversation display: read-only existing HW6 messages")

uri = os.getenv("HW6_MONGODB_URI", "mongodb://127.0.0.1:27017")
database_name = os.getenv("HW6_MONGODB_DATABASE", "s8844_doc")
user_id = os.getenv("HW6_CONVERSATION_USER", "hw6-user-8844")
session_id = os.getenv("HW6_CONVERSATION_SESSION", "hw6-session-4")

client = MongoClient(uri, serverSelectionTimeoutMS=3000)
try:
    collection = client[database_name]["messages"]
    messages = list(collection.find(
        {"user_id": user_id, "session_id": session_id},
        {"_id": 0, "role": 1, "content": 1, "created_at": 1},
    ).sort("created_at", 1).limit(20))
    print(f"Session: {session_id}")
    print(f"Messages displayed: {min(len(messages), 10)}")
    for index, message in enumerate(messages[:10], start=1):
        role = str(message.get("role", "unknown")).upper()
        content = " ".join(str(message.get("content", "")).split())
        if len(content) > 240:
            content = content[:237] + "..."
        print(f"{index:02d}. {role}: {content}")
finally:
    client.close()

# Capture the terminal output as a screenshot only after reviewing that it
# contains at least ten messages and both USER and ASSISTANT roles.
'@
# Feed the literal here-string through stdin so PowerShell does not reinterpret
# Python quotes while building a -c command-line argument.
$code | & $python -
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
