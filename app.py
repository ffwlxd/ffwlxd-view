from flask import Flask, jsonify
import aiohttp
import asyncio
import json
from byte import encrypt_api, Encrypt_ID
from visit_count_pb2 import Info  # Import protobuf class

app = Flask(__name__)

# ------------------------
# Token Loader (Single Region)
# ------------------------
def load_tokens():
    try:
        path = "token_ind.json"  # yaha token_ind.json fix kar diya
        with open(path, "r") as f:
            data = json.load(f)
        tokens = [item["token"] for item in data if "token" in item and item["token"] not in ["", "N/A"]]
        return tokens
    except Exception as e:
        app.logger.error(f"❌ Token load error: {e}")
        return []

# ------------------------
# Static URL (Single Region)
# ------------------------
URL = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"

# ------------------------
# Protobuf Parser
# ------------------------
def parse_protobuf_response(response_data):
    try:
        info = Info()
        info.ParseFromString(response_data)
        return info.AccountInfo.PlayerNickname if info.AccountInfo.PlayerNickname else ""
    except Exception as e:
        app.logger.error(f"❌ Protobuf parsing error: {e}")
        return None

# ------------------------
# Visit Function
# ------------------------
async def visit(session, token, uid, data):
    headers = {
        "ReleaseVersion": "OB50",
        "X-GA": "v1 1",
        "Authorization": f"Bearer {token}",
        "Host": URL.replace("https://", "").split("/")[0]
    }
    try:
        async with session.post(URL, headers=headers, data=data, ssl=False) as resp:
            if resp.status == 200:
                return True, await resp.read()
            else:
                # Agar token region mismatch ya UID invalid
                app.logger.warning(f"⚠️ Visit failed for UID {uid} with status {resp.status}")
                return False, None
    except Exception as e:
        app.logger.error(f"❌ Visit error for UID {uid}: {e}")
        return False, None

# ------------------------
# Main Loop Until 1000 Success
# ------------------------
async def send_until_1000_success(tokens, uid, target_success=1000):
    connector = aiohttp.TCPConnector(limit=0)
    total_success = 0
    total_sent = 0
    nickname = None

    async with aiohttp.ClientSession(connector=connector) as session:
        encrypted = encrypt_api("08" + Encrypt_ID(str(uid)) + "1801")
        data = bytes.fromhex(encrypted)

        while total_success < target_success:
            batch_size = min(target_success - total_success, 1000)
            tasks = [
                asyncio.create_task(visit(session, tokens[(total_sent + i) % len(tokens)], uid, data))
                for i in range(batch_size)
            ]
            results = await asyncio.gather(*tasks)

            if nickname is None:
                for success, response in results:
                    if success and response is not None:
                        nickname = parse_protobuf_response(response)
                        break

            batch_success = sum(1 for r, _ in results if r)
            total_success += batch_success
            total_sent += batch_size

    return total_success, target_success - total_success, nickname

# ------------------------
# API Route
# ------------------------
@app.route('/<int:uid>', methods=['GET'])
def send_visits(uid):
    tokens = load_tokens()
    if not tokens:
        return jsonify({"error": "❌ No valid tokens found"}), 500

    print(f"🚀 Sending visits to UID: {uid} using {len(tokens)} tokens")
    total_success, total_fail, nickname = asyncio.run(send_until_1000_success(tokens, uid))

    return jsonify({
        "player_name": nickname if nickname else "",
        "success": total_success,
        "fail": total_fail
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)