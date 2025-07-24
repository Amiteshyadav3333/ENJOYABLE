const socket = io();
const peers = {};
let localStream;
let mediaRecorder;
let recordedChunks = [];
let currentRoomId = '';

function $(id) {
  return document.getElementById(id);
}

// Start camera and mic
async function startLocalMedia() {
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    $('localVideo').srcObject = localStream;
    $('localVideo').play();
  } catch (err) {
    console.error("🚫 Media access error:", err);
    alert("Please allow camera and mic access.");
  }
}

// Create room
$('createBtn').onclick = () => {
  const username = $('lobbyUsername').value.trim() || 'Anonymous';
  const roomName = $('roomName').value.trim();
  if (!roomName) return alert('Room name required');
  socket.emit('create_room', { username, room_name: roomName });
};

// Join room
$('joinBtn').onclick = () => {
  const username = $('lobbyUsername').value.trim() || 'Anonymous';
  const roomId = $('joinRoomId').value.trim();
  if (!roomId) return alert('Room ID required');
  socket.emit('join_room', { room_id: roomId, username });
};

// Leave room
$('leaveBtn').onclick = () => {
  socket.emit('leave_room', { room_id: currentRoomId });
  window.location.reload();
};

// Peer connection
function createPeer(remoteSid, initiator) {
  if (!localStream) return alert("Start stream first");

  if (peers[remoteSid]) return;

  const peer = new SimplePeer({
    initiator,
    trickle: false,
    stream: localStream,
    config: {
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    }
  });

  peers[remoteSid] = peer;

  peer.on('signal', data => {
    socket.emit('signal', { room_id: currentRoomId, target: remoteSid, signal: data });
  });

  peer.on('stream', stream => addRemoteVideo(remoteSid, stream));
  peer.on('close', () => removeRemoteVideo(remoteSid));
  peer.on('error', err => {
    console.error("Peer error", err);
    removeRemoteVideo(remoteSid);
  });
}

// Add remote video
function addRemoteVideo(sid, stream) {
  let vid = document.getElementById(sid);
  if (!vid) {
    vid = document.createElement('video');
    vid.id = sid;
    vid.autoplay = true;
    vid.playsInline = true;
    vid.className = 'remoteVideo';
    $('videoArea').appendChild(vid);
  }
  vid.srcObject = stream;
  vid.play();
}

// Remove remote video
function removeRemoteVideo(sid) {
  if (peers[sid]) peers[sid].destroy();
  delete peers[sid];
  const vid = document.getElementById(sid);
  if (vid) vid.remove();
}

// Room created
socket.on('room_created', async ({ room_id }) => {
  currentRoomId = room_id;
  await startLocalMedia();
  $('lobby').style.display = 'none';
  $('liveArea').style.display = 'block';
});

// Room joined
socket.on('room_joined', async ({ room_id }) => {
  currentRoomId = room_id;
  await startLocalMedia();
  $('lobby').style.display = 'none';
  $('liveArea').style.display = 'block';
});

// User list
socket.on('user_list', users => {
  users.forEach(({ sid }) => {
    if (sid !== socket.id && !peers[sid]) {
      createPeer(sid, socket.id < sid);
    }
  });
});

// Signal received
socket.on('signal', ({ source, signal }) => {
  if (!peers[source]) {
    createPeer(source, false);
  }
  peers[source].signal(signal);
});

// Chat send
$('sendChat').onclick = () => {
  const msg = $('chatMsg').value.trim();
  if (msg && currentRoomId) {
    socket.emit('chat', { room_id: currentRoomId, message: msg });
    $('chatMsg').value = '';
  }
};

// Chat receive
socket.on('chat', ({ username, message }) => {
  const p = document.createElement('p');
  p.textContent = `${username}: ${message}`;
  $('chatBox').appendChild(p);
});

// Emoji reaction
document.querySelectorAll('.reaction').forEach(btn => {
  btn.onclick = () => {
    socket.emit('reaction', { room_id: currentRoomId, emoji: btn.textContent });
  };
});

// Reaction receive
socket.on('reaction', ({ emoji }) => {
  const el = document.createElement('div');
  el.textContent = emoji;
  el.className = 'reactionBubble';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1500);
});

// Toggle mic / cam
$('toggleMic').onclick = () => toggleTrack('audio');
$('toggleCam').onclick = () => toggleTrack('video');

function toggleTrack(kind) {
  const track = localStream?.getTracks().find(t => t.kind === kind);
  if (track) track.enabled = !track.enabled;
}

// Screen sharing
$('shareScreen').onclick = async () => {
  try {
    const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
    replaceVideoTrack(screenStream.getVideoTracks()[0]);
    screenStream.getVideoTracks()[0].onended = () => {
      if (localStream) replaceVideoTrack(localStream.getVideoTracks()[0]);
    };
  } catch (err) {
    console.error('Screen share error:', err);
  }
};

function replaceVideoTrack(newTrack) {
  Object.values(peers).forEach(peer => {
    const sender = peer._pc.getSenders().find(s => s.track.kind === 'video');
    if (sender) sender.replaceTrack(newTrack);
  });
}

// Start/Stop recording
$('recordBtn').onclick = () => {
  if (!localStream) return alert("Enable mic/cam first");

  if (mediaRecorder?.state === 'recording') {
    mediaRecorder.stop();
    $('recordBtn').textContent = "Start Recording";
    return;
  }

  recordedChunks = [];
  mediaRecorder = new MediaRecorder(localStream);
  mediaRecorder.ondataavailable = e => {
    if (e.data.size > 0) recordedChunks.push(e.data);
  };

  mediaRecorder.onstop = () => {
    const blob = new Blob(recordedChunks, { type: 'video/webm' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'recording.webm';
    a.click();
  };

  const socket = io();
const peers = {};
let localStream;

function $(id) {
  return document.getElementById(id);
}

$('createBtn').onclick = async () => {
  const roomName = $('roomName').value.trim();
  const username = $('lobbyUsername').value.trim();
  if (!roomName || !username) return alert("Please enter room name and your name.");

  await startLocalMedia(); // Access camera/mic
  socket.emit('createRoom', { room: roomName, username });
  showLiveArea(roomName);
};

function showLiveArea(roomName) {
  $('lobby').style.display = 'none';
  $('liveArea').style.display = 'block';
  $('roomTitle').innerText = `Room: ${roomName}`;
}

  mediaRecorder.start();
  $('recordBtn').textContent = "Stop Recording";
};