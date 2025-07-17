const peers = {};
let localStream;
let currentRoomId = null;

function $(id) {
  return document.getElementById(id);
}

window.startStream = async function () {
  if (!navigator.mediaDevices?.getUserMedia) {
    return alert("❌ Browser does not support camera/mic access.");
  }
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    $('localVideo').srcObject = localStream;
    $('localVideo').play();
  } catch (err) {
    console.error("🚫 Media access error:", err);
    alert("Please allow camera and mic access.");
  }
};

async function startLocalMedia() {
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    $('localVideo').srcObject = localStream;
    $('localVideo').play();
  } catch (err) {
    console.error('Media access error:', err);
    alert('🚫 Please allow camera and microphone access.');
  }
}

$('createBtn')?.addEventListener('click', () => {
  const usernameInput = $('lobbyUsername');
  const roomInput = $('roomName');

  if (!usernameInput || !roomInput) return alert("Form missing.");
  
  const username = usernameInput.value?.trim() || 'Anonymous';
  const roomName = roomInput.value?.trim();
  if (!roomName) return alert('Room name required');
  socket.emit('create_room', { username, room_name: roomName });
});

$('joinBtn')?.addEventListener('click', () => {
  const usernameInput = $('lobbyUsername');
  const roomInput = $('joinRoomId');

  if (!usernameInput || !roomInput) return alert("Form missing.");

  const username = usernameInput.value?.trim() || 'Anonymous';
  const roomId = roomInput.value?.trim();
  if (!roomId) return alert('Room ID required');
  socket.emit('join_room', { room_id: roomId, username });
});

function createPeer(remoteSid, initiator) {
  if (!localStream) {
    alert("Stream not started yet. Please allow camera/mic.");
    return;
  }

  if (peers[remoteSid]) return;

  const peer = new SimplePeer({
    initiator,
    stream: localStream,
    config: {
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    }
  });

  peer.on('signal', data => {
    socket.emit('signal', {
      room_id: currentRoomId,
      target: remoteSid,
      signal: data
    });
  });

  peer.on('stream', stream => {
    addRemoteVideo(remoteSid, stream);
  });

  peer.on('close', () => removeRemoteVideo(remoteSid));
  peer.on('error', err => {
    console.error("Peer error", err);
    alert("⚠️ Connection issue with peer.");
    removeRemoteVideo(remoteSid);
  });

  peers[remoteSid] = peer;
}

function addRemoteVideo(sid, stream) {
  let vid = document.getElementById(sid);
  if (!vid) {
    vid = document.createElement('video');
    vid.id = sid;
    vid.autoplay = true;
    vid.playsInline = true;
    vid.className = 'remote-video';
    $('videoArea')?.appendChild(vid);
  }
  vid.srcObject = stream;
  vid.play();
}

function removeRemoteVideo(sid) {
  const el = document.getElementById(sid);
  if (el) el.remove();
  if (peers[sid]) {
    peers[sid].destroy();
    delete peers[sid];
  }
}

function refreshTargetSelect() {
  const select = $('target');
  if (!select) return;

  select.innerHTML = '<option value="all">Everyone</option>';
  Object.keys(peers).forEach(sid => {
    const opt = document.createElement('option');
    opt.value = sid;
    opt.textContent = sid;
    select.appendChild(opt);
  });
}

$('sendChat')?.addEventListener('click', () => {
  const input = $('chatInput');
  if (!input) return;
  const text = input.value?.trim();
  if (!text) return;
  socket.emit('chat', { room_id: currentRoomId, message: text });
  input.value = '';
});

document.querySelectorAll('.reaction').forEach(btn => {
  btn.onclick = () => socket.emit('reaction', { room_id: currentRoomId, emoji: btn.textContent });
});

$('toggleMic')?.addEventListener('click', () => toggleTrack('audio'));
$('toggleCam')?.addEventListener('click', () => toggleTrack('video'));

function toggleTrack(kind, state) {
  if (!localStream) return;
  localStream.getTracks().forEach(track => {
    if (track.kind === kind) {
      track.enabled = state ?? !track.enabled;
    }
  });
}

$('shareScreen')?.addEventListener('click', async () => {
  try {
    const screen = await navigator.mediaDevices.getDisplayMedia({ video: true });
    replaceVideoTrack(screen.getVideoTracks()[0]);

    screen.getVideoTracks()[0].onended = () => {
      if (localStream) replaceVideoTrack(localStream.getVideoTracks()[0]);
    };
  } catch (err) {
    alert("❌ Screen share denied or failed.");
  }
});

function replaceVideoTrack(newTrack) {
  if (!localStream) return;
  const sender = Object.values(peers).find(peer => {
    const stream = peer.streams?.[0];
    return stream?.getVideoTracks()?.[0];
  });

  Object.values(peers).forEach(peer => {
    const sender = peer._pc.getSenders().find(s => s.track?.kind === 'video');
    if (sender) sender.replaceTrack(newTrack);
  });

  $('localVideo').srcObject.getVideoTracks()[0].stop();
  $('localVideo').srcObject = new MediaStream([newTrack]);
  $('localVideo').play();
}

$('recordBtn')?.addEventListener('click', () => {
  if (!localStream) return alert('🎙️ Please enable mic/camera first.');
  if (mediaRecorder?.state === 'recording') {
    mediaRecorder.stop();
    return;
  }
  startRecording();
});