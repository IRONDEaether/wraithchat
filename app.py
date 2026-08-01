import random
import string
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'twraithchat_ghost_ephemeral_2026'

# FIX AUDIO/VIDÉO : Limite de transfert maintenue (relai fallback au besoin)
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='eventlet', 
    max_http_buffer_size=52428800
)

# Stockage en RAM : { user_id: { sid, profile } }
online_users = {}

def generate_unique_id():
    """Génère un ID unique à 8 chiffres."""
    while True:
        uid = ''.join(random.choices(string.digits, k=8))
        if uid not in online_users:
            return uid

@app.route('/')
def index():
    return render_template('index.html')

# --- ÉVÉNEMENTS SOCKET.IO ---

@socketio.on('register_user')
def handle_register(data):
    """Enregistre l'utilisateur et rejoint sa room privée."""
    user_id = data.get('user_id')
    profile = data.get('profile', {})

    if not user_id:
        user_id = generate_unique_id()

    online_users[user_id] = {
        'sid': request.sid,
        'profile': profile
    }

    join_room(user_id)
    emit('registered', {'status': 'ok', 'user_id': user_id})


@socketio.on('check_online')
def handle_check_online(data):
    """Vérifie le statut en ligne du correspondant."""
    target_id = data.get('target_id')
    is_online = target_id in online_users
    emit('online_status', {'target_id': target_id, 'is_online': is_online})


@socketio.on('send_message')
def handle_send_message(data):
    """Gère le texte, les médias (vidéo/audio) et les fichiers."""
    sender_id = data.get('sender_id')
    target_id = data.get('target_id')
    msg_type = data.get('type', 'text')

    if target_id in online_users:
        emit('receive_message', {
            'type': msg_type,
            'sender_id': sender_id,
            'content': data.get('content'),
            'file_name': data.get('file_name'),
            'file_type': data.get('file_type')
        }, room=target_id)
        
        emit('message_sent_confirm', {'status': 'success'})
    else:
        emit('message_sent_confirm', {'status': 'failed', 'reason': 'Utilisateur hors ligne'})


@socketio.on('sync_profile')
def handle_sync_profile(data):
    """Met à jour les détails du profil auprès des contacts."""
    sender_id = data.get('sender_id')
    target_ids = data.get('target_ids', [])
    profile = data.get('profile', {})

    if sender_id in online_users:
        online_users[sender_id]['profile'] = profile

    for tid in target_ids:
        if tid in online_users:
            emit('profile_updated', {
                'sender_id': sender_id,
                'profile': profile
            }, room=tid)


# --- SIGNALISATION WEBRTC POUR P2P DIRECT (VIDÉOS & SONS LOURDS) ---

@socketio.on('webrtc_offer')
def handle_webrtc_offer(data):
    """Transmet l'offre WebRTC pour ouvrir le canal P2P direct."""
    target_id = data.get('target_id')
    if target_id in online_users:
        emit('webrtc_offer', {
            'sender_id': data.get('sender_id'),
            'sdp': data.get('sdp'),
            'file_meta': data.get('file_meta')
        }, room=target_id)


@socketio.on('webrtc_answer')
def handle_webrtc_answer(data):
    """Transmet la réponse WebRTC de l'autre pair."""
    target_id = data.get('target_id')
    if target_id in online_users:
        emit('webrtc_answer', {
            'sender_id': data.get('sender_id'),
            'sdp': data.get('sdp')
        }, room=target_id)


@socketio.on('webrtc_ice_candidate')
def handle_webrtc_ice(data):
    """Transmet les adresses/candidats ICE pour la connexion directe."""
    target_id = data.get('target_id')
    if target_id in online_users:
        emit('webrtc_ice_candidate', {
            'sender_id': data.get('sender_id'),
            'candidate': data.get('candidate')
        }, room=target_id)


@socketio.on('disconnect')
def handle_disconnect():
    """Nettoyage de la connexion."""
    for uid, user_data in list(online_users.items()):
        if user_data['sid'] == request.sid:
            del online_users[uid]
            break

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)