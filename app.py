from flask import Flask, request, jsonify
import json
import asyncio
import binascii
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import aiohttp
import urllib3
from google.protobuf.json_format import MessageToJson
import uid_generator_pb2
import like_count_pb2
import math

app = Flask(__name__)
urllib3.disable_warnings()

# ----------------------
# Token loader (IND only)
# ----------------------
def load_tokens():
    try:
        with open("token_ind.json", "r") as f:
            tokens = json.load(f)
        return tokens
    except:
        return None

# ----------------------
# AES encryption helpers
# ----------------------
def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except:
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except:
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    encrypted_uid = encrypt_message(protobuf_data)
    return encrypted_uid

# ----------------------
# Request sender
# ----------------------
async def make_request_async(encrypt, token, session):
    try:
        url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB48"
        }

        async with session.post(url, data=edata, headers=headers, ssl=False, timeout=10) as response:
            if response.status != 200:
                return None
            hex_data = await response.read()
            binary = bytes.fromhex(hex_data.hex())
            return decode_protobuf(binary)
    except:
        return None

# ----------------------
# Protobuf decoder
# ----------------------
def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except:
        return None

# ----------------------
# Visit endpoint
# ----------------------
@app.route('/visit', methods=['GET'])
async def visit():
    target_uid = request.args.get("uid")
    if not target_uid:
        return jsonify({"error": "Target UID is required"}), 400

    try:
        tokens = load_tokens()
        if not tokens:
            raise Exception("Failed to load tokens.")

        encrypted_target_uid = enc(target_uid)
        if encrypted_target_uid is None:
            raise Exception("Encryption of target UID failed.")

        # Repeat tokens list until it reaches 1000 entries
        required_count = 1000
        repeated_tokens = (tokens * math.ceil(required_count / len(tokens)))[:required_count]

        failed_count = 0
        player_name = None
        player_uid = None

        async with aiohttp.ClientSession() as session:
            tasks = [
                make_request_async(encrypted_target_uid, token['token'], session)
                for token in repeated_tokens
            ]
            results = await asyncio.gather(*tasks)

        for info in results:
            if info is not None:
                if player_name is None:
                    jsone = MessageToJson(info)
                    data_info = json.loads(jsone)
                    player_name = str(data_info.get('AccountInfo', {}).get('PlayerNickname', 'Unknown'))
                    player_uid = int(data_info.get('AccountInfo', {}).get('UID', 0))
            else:
                failed_count += 1

        summary = {
            "Player_Name": player_name or "Unknown",
            "Player_UID": player_uid or target_uid,
            "Success_count": required_count,
            "Failed_count": failed_count
        }
        return jsonify(summary)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------
# Main runner
# ----------------------
if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app.run(debug=True, use_reloader=False)