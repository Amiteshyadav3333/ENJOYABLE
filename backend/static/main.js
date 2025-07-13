const socket = io();
const $ = id => document.getElementById(id);

const lobby = $('lobby');
const roomSection = $('room');
const roomHeader = $('roomHeader');
const adminBadge = $('adminBadge');
const userList = $('userList');
const chatWindow = $('chatWindow');
const chatInput = $('chatInput');
const targetSelect = $('targetSelect');
const localVideo = $('localVideo');
const videoArea = $('videoArea');

let localStream;
let mediaRecorder;
let recordedBlobs = [];
let currentRoomId;
let isAdmin = false;
const peers = {};

window.startStream = async function () {
  if (!navigator.mediaDevices?.getUserMedia) {
    return alert("❌ Browser does not support camera/mic access.");
  }
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    localVideo.srcObject = localStream;
    localVideo.play();
  } catch (err) {
    console.error("🚫 Media access error:", err);
    alert("Please allow camera and mic access.");
  }
};

async function startLocalMedia() {
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    localVideo.srcObject = localStream;
    localVideo.play();
  } catch (err) {
    console.error('Media error:', err);
    alert('Please allow camera/microphone access.');
  }
}

function createPeer(remoteSid, initiator) {
  const peer = new SimplePeer({ initiator, trickle: false, stream: localStream });

  peer.on('signal', data => {
    socket.emit('signal', {
      room_id: currentRoomId,
      target: remoteSid,
      signal: data
    });
  });

  peer.on('stream', stream => {
    console.log("Received remote stream from", remoteSid);
    addRemoteVideo(remoteSid, stream);
  });

  peer.on('close', () => removeRemoteVideo(remoteSid));
  peer.on('error', err => {
    console.error("Peer error", err);
    removeRemoteVideo(remoteSid);
  });

  peers[remoteSid] = peer;
}

function addRemoteVideo(sid, stream) {
  let vid = document.getElementById(`video-${sid}`);
  if (!vid) {
    vid = document.createElement('video');
    vid.id = `video-${sid}`;
    vid.autoplay = true;
    vid.playsInline = true;
    videoArea.appendChild(vid);
  }
  vid.srcObject = stream;
  vid.play();
}

function removeRemoteVideo(sid) {
  const vid = document.getElementById(`video-${sid}`);
  if (vid) vid.remove();
  if (peers[sid]) peers[sid].destroy();
  delete peers[sid];
  refreshTargetSelect();
}

function refreshTargetSelect() {
  targetSelect.innerHTML = '<option value="">Select user</option>';
  Object.keys(peers).forEach(sid => {
    const opt = document.createElement('option');
    opt.value = sid;
    opt.textContent = sid;
    targetSelect.appendChild(opt);
  });
}

$('createBtn').onclick = () => {
  const username = $('lobbyUsername').value.trim() || 'Anonymous';
  const roomName = $('roomName').value.trim();
  if (!roomName) return alert('Room name required');
  socket.emit('create_room', { username, room_name: roomName });
};

$('joinBtn').onclick = () => {
  const username = $('lobbyUsername').value.trim() || 'Anonymous';
  const roomId = $('joinRoomId').value.trim();
  if (!roomId) return alert('Room ID required');
  socket.emit('join_room', { room_id: roomId, username });
};

socket.on('room_created', async ({ room_id }) => {
  await startLocalMedia();
  enterRoom(room_id, true);
});

socket.on('joined_success', async ({ room_id, admin }) => {
  await startLocalMedia();
  enterRoom(room_id, admin);
});

function enterRoom(roomId, adminFlag) {
  currentRoomId = roomId;
  isAdmin = adminFlag;
  lobby.hidden = true;
  roomSection.hidden = false;
  roomHeader.textContent = `Room ID: ${roomId}`;
  adminBadge.hidden = !isAdmin;
  $('adminControls').hidden = !isAdmin;
}

socket.on('user_list', users => {
  userList.innerHTML = '';
  users.forEach(({ sid, username }) => {
    const li = document.createElement('li');
    li.textContent = `${username}${sid === socket.id ? ' (You)' : ''}`;
    userList.appendChild(li);
  });

  users.forEach(({ sid }) => {
    if (sid !== socket.id && !peers[sid]) createPeer(sid, socket.id < sid);
  });

  refreshTargetSelect();
});

socket.on('user_left', ({ sid }) => removeRemoteVideo(sid));

socket.on('signal', ({ sid, signal }) => {
  if (!peers[sid]) createPeer(sid, false);
  peers[sid].signal(signal);
});

socket.on('chat_message', ({ sid, text }) => {
  const div = document.createElement('div');
  div.textContent = `${sid === socket.id ? 'You' : sid}: ${text}`;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
});

socket.on('reaction', ({ sid, emoji }) => {
  const div = document.createElement('div');
  div.textContent = `${sid === socket.id ? 'You' : sid}: ${emoji}`;
  chatWindow.appendChild(div);
});

socket.on('admin_action', ({ action }) => {
  if (action === 'mute_audio') toggleTrack('audio', false);
  if (action === 'mute_video') toggleTrack('video', false);
});

socket.on('kicked', () => window.location.reload());

$('sendChat').onclick = () => {
  const text = chatInput.value.trim();
  if (!text) return;
  socket.emit('chat_message', { room_id: currentRoomId, text });
  chatInput.value = '';
};

document.querySelectorAll('.reaction').forEach(btn => {
  btn.onclick = () => {
    socket.emit('reaction', { room_id: currentRoomId, emoji: btn.textContent });
  };
});

$('toggleMic').onclick = () => toggleTrack('audio');
$('toggleCam').onclick = () => toggleTrack('video');

function toggleTrack(kind, state) {
  localStream?.getTracks().forEach(t => {
    if (t.kind === kind) t.enabled = state !== undefined ? state : !t.enabled;
  });
}

$('shareScreen').onclick = async () => {
  try {
    const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
    replaceVideoTrack(screenStream.getVideoTracks()[0]);

    screenStream.getVideoTracks()[0].onended = () => {
      if (localStream) replaceVideoTrack(localStream.getVideoTracks()[0]);
    };
  } catch (err) {
    alert('🚫 Screen sharing denied.');
    console.error(err);
  }
};

function replaceVideoTrack(newTrack) {
  const sender = Object.values(peers)
    .map(p => p._pc.getSenders().find(s => s.track?.kind === 'video'))
    .find(Boolean);

  if (sender) sender.replaceTrack(newTrack);
  localStream?.removeTrack(localStream.getVideoTracks()[0]);
  localStream?.addTrack(newTrack);
  localVideo.srcObject = localStream;
}

$('recordBtn').onclick = () => {
  if (!localStream) return alert('🎙️ Enable mic/camera first.');
  if (mediaRecorder?.state === 'recording') {
    mediaRecorder.stop();
    return;
  }

  recordedBlobs = [];
  mediaRecorder = new MediaRecorder(localStream, { mimeType: 'video/webm' });
  mediaRecorder.ondataavailable = e => e.data.size && recordedBlobs.push(e.data);
  mediaRecorder.onstop = () => {
    const url = URL.createObjectURL(new Blob(recordedBlobs, { type: 'video/webm' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'recording.webm';
    a.click();
  };

  mediaRecorder.start();
};

$('leaveBtn').onclick = () => window.location.reload();

$('adminControls').onclick = e => {
  if (e.target.tagName !== 'BUTTON') return;
  const action = e.target.dataset.action;
  const target = targetSelect.value;
  if (!target) return alert('Select a user first');
  socket.emit('admin_action', { room_id: currentRoomId, action, target });
};