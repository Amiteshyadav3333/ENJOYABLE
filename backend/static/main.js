const socket = io();
let localStream, screenStream;
let isAdmin = false;
let peers = {};
let recording = false;

function $(id) {
  return document.getElementById(id);
}

const localVideo = $('localVideo');
const remoteVideos = $('videoArea');
const userList = $('userList');
const shareScreen = $('shareScreen');
const adminBadge = $('adminBadge');
const joinBtn = $('joinBtn');
const createBtn = $('createBtn');

joinBtn.onclick = async () => {
  const usernameInput = $('lobbyUsername');
  const roomInput = $('joinRoomId');

  const username = usernameInput?.value.trim();
  const room = roomInput?.value.trim();

  if (!username || !room) return alert('Enter username and room');

  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    localVideo.srcObject = localStream;
  } catch (err) {
    return alert('Camera/Mic access denied');
  }

  socket.emit('join_room', { username, room_id: room });
};

createBtn.onclick = async () => {
  const usernameInput = $('lobbyUsername');
  const roomInput = $('roomName');

  const username = usernameInput?.value.trim();
  const roomName = roomInput?.value.trim();

  if (!username || !roomName) return alert('Enter username and room');

  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    localVideo.srcObject = localStream;
  } catch (err) {
    return alert('Camera/Mic access denied');
  }

  socket.emit('create_room', { username, room_name: roomName });
};

socket.on('room_created', ({ room_id, admin }) => {
  showRoomUI();
  isAdmin = socket.id === admin;
  adminBadge.hidden = !isAdmin;
  $('adminControls').hidden = !isAdmin;
  $('roomHeader').innerText = `Room: ${room_id}`;
});

socket.on('joined_success', ({ room_id, admin }) => {
  showRoomUI();
  isAdmin = socket.id === admin;
  adminBadge.hidden = !isAdmin;
  $('adminControls').hidden = !isAdmin;
  $('roomHeader').innerText = `Room: ${room_id}`;
});

socket.on('user_joined', ({ sid, username }) => {
  console.log(`User joined: ${username} (${sid})`);

  const li = document.createElement('li');
  li.textContent = `${username}${sid === socket.id ? ' (You)' : ''}`;
  li.id = `user-${sid}`;
  userList.appendChild(li);

  if (sid !== socket.id && !peers[sid]) {
    createPeer(sid, socket.id < sid);
  }

  refreshTargetSelect();
});

socket.on('user_left', ({ sid }) => {
  if (peers[sid]) {
    peers[sid].destroy();
    delete peers[sid];
  }
  const video = $(sid);
  if (video) video.remove();

  const userItem = $(`user-${sid}`);
  if (userItem) userItem.remove();
});

socket.on('admin_changed', ({ sid }) => {
  isAdmin = socket.id === sid;
  adminBadge.hidden = !isAdmin;
  $('adminControls').hidden = !isAdmin;
});

socket.on('signal', ({ from, signal }) => {
  if (!peers[from]) {
    createPeer(from, false);
  }
  peers[from].signal(signal);
});

function createPeer(peerId, initiator = false) {
  const peer = new SimplePeer({
    initiator,
    trickle: false,
    stream: localStream,
  });

  peer.on('signal', data => {
    socket.emit('signal', { to: peerId, from: socket.id, signal: data });
  });

  peer.on('stream', stream => {
    addRemoteVideo(peerId, stream);
  });

  peer.on('close', () => {
    const video = $(peerId);
    if (video) video.remove();
  });

  peers[peerId] = peer;
}

function addRemoteVideo(id, stream) {
  let video = $(id);
  if (!video) {
    video = document.createElement('video');
    video.id = id;
    video.autoplay = true;
    video.playsInline = true;
    remoteVideos.appendChild(video);
  }
  video.srcObject = stream;
}

shareScreen.onclick = async () => {
  try {
    screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
    const screenTrack = screenStream.getVideoTracks()[0];
    replaceVideoTrack(screenTrack);

    screenTrack.onended = () => {
      const originalTrack = localStream.getVideoTracks().find(t => t.kind === 'video');
      if (originalTrack) replaceVideoTrack(originalTrack);
    };
  } catch (e) {
    console.error('Screen share failed', e);
  }
};

function replaceVideoTrack(newTrack) {
  Object.values(peers).forEach(peer => {
    const sender = peer._pc.getSenders().find(s => s.track?.kind === 'video');
    if (sender) sender.replaceTrack(newTrack);
  });

  if (localStream) {
    const oldTrack = localStream.getVideoTracks()[0];
    if (oldTrack) localStream.removeTrack(oldTrack);
    localStream.addTrack(newTrack);
    localVideo.srcObject = localStream;
  }
}

function refreshTargetSelect() {
  // Optional: admin dropdown update
}

function showRoomUI() {
  $('lobby').hidden = true;
  $('room').hidden = false;
}