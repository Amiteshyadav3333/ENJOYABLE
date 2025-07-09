const socket = io();
let localStream, peerConnection;
let username = "";
let isAdmin = false;
let remoteSid = null;

const config = {
  iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
};

// === Auth Login ===
function login() {
  username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  isAdmin = document.getElementById("adminCheck").checked;

  fetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  })
  .then(res => res.json())
  .then(data => {
    if (data.message.includes("successful")) {
      document.getElementById("login-section").style.display = "none";
      document.getElementById("call-section").style.display = "block";
      joinRoom();
    } else {
      alert(data.message);
    }
  });
}

// === Join Room ===
function joinRoom() {
  socket.emit("join", { username, room: "default", isAdmin });
}

// === Request to Speak ===
function startStream() {
  socket.emit("request_to_speak");
}

// === Chat Functionality ===
function sendMessage() {
  const msg = document.getElementById("msgInput").value.trim();
  if (!msg) return;
  socket.emit("chat_message", { msg });
  document.getElementById("msgInput").value = '';
}

socket.on("chat_message", ({ username, msg }) => {
  const chatBox = document.getElementById("chatBox");
  const div = document.createElement("div");
  div.textContent = `${username}: ${msg}`;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
});

// === WebRTC Offer/Answer Exchange ===
socket.on("approved", async () => {
  localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  document.getElementById("localVideo").srcObject = localStream;

  peerConnection = new RTCPeerConnection(config);
  localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

  peerConnection.onicecandidate = e => {
    if (e.candidate) {
      socket.emit("ice-candidate", { to: remoteSid, candidate: e.candidate });
    }
  };

  peerConnection.ontrack = e => {
    document.getElementById("remoteVideo").srcObject = e.streams[0];
  };

  const offer = await peerConnection.createOffer();
  await peerConnection.setLocalDescription(offer);
  socket.emit("offer", { sdp: offer, to: remoteSid });
});

socket.on("user_joined", ({ sid }) => {
  if (!isAdmin) remoteSid = sid;
});

socket.on("offer", async ({ from, sdp }) => {
  remoteSid = from;
  peerConnection = new RTCPeerConnection(config);

  peerConnection.onicecandidate = e => {
    if (e.candidate) {
      socket.emit("ice-candidate", { to: from, candidate: e.candidate });
    }
  };

  peerConnection.ontrack = e => {
    document.getElementById("remoteVideo").srcObject = e.streams[0];
  };

  localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  document.getElementById("localVideo").srcObject = localStream;
  localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

  await peerConnection.setRemoteDescription(new RTCSessionDescription(sdp));
  const answer = await peerConnection.createAnswer();
  await peerConnection.setLocalDescription(answer);
  socket.emit("answer", { sdp: answer, to: from });
});

socket.on("answer", async ({ sdp }) => {
  await peerConnection.setRemoteDescription(new RTCSessionDescription(sdp));
});

socket.on("ice-candidate", async ({ candidate }) => {
  if (candidate && peerConnection) {
    await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
  }
});

// === Admin Actions ===
function muteUser() {
  if (remoteSid) socket.emit("mute_user", { sid: remoteSid });
}

function kickUser() {
  if (remoteSid) socket.emit("kick_user", { sid: remoteSid });
}

socket.on("muted", () => {
  localStream?.getAudioTracks().forEach(track => track.enabled = false);
});

socket.on("kicked", () => {
  alert("You were kicked!");
  window.location.reload();
});

// === Recording ===
let mediaRecorder;
let recordedChunks = [];

function startRecording() {
  if (!localStream) {
    alert("🎥 Please start stream first.");
    return;
  }

  recordedChunks = [];
  mediaRecorder = new MediaRecorder(localStream);
  mediaRecorder.ondataavailable = e => {
    if (e.data.size > 0) recordedChunks.push(e.data);
  };
  mediaRecorder.onstop = () => {
    const blob = new Blob(recordedChunks, { type: "video/webm" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "recording.webm";
    a.click();
  };

  mediaRecorder.start();
  console.log("Recording started");
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    console.log("Recording stopped");
  }
}

// === Welcome log ===
socket.on("welcome", (data) => {
  console.log(data.msg || "Connected to LiveCast");
});