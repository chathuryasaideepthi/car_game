const apiBase = "http://localhost:5000";

const screens = {
  home: document.getElementById("homeScreen"),
  game: document.getElementById("gameScreen"),
  leaderboard: document.getElementById("leaderboardScreen"),
  gameOver: document.getElementById("gameOverScreen"),
};

const ui = {
  playerNameInput: document.getElementById("playerNameInput"),
  startBtn: document.getElementById("startBtn"),
  instructionBtn: document.getElementById("instructionBtn"),
  leaderboardBtn: document.getElementById("leaderboardBtn"),
  pauseBtn: document.getElementById("pauseBtn"),
  finalScoreValue: document.getElementById("finalScoreValue"),
  finalDistanceValue: document.getElementById("finalDistanceValue"),
  finalCoinsValue: document.getElementById("finalCoinsValue"),
  bestScoreValue: document.getElementById("bestScoreValue"),
  scoreValue: document.getElementById("scoreValue"),
  speedValue: document.getElementById("speedValue"),
  distanceValue: document.getElementById("distanceValue"),
  coinsValue: document.getElementById("coinsValue"),
  leaderboardBody: document.getElementById("leaderboardBody"),
  closeInstructionsBtn: document.getElementById("closeInstructionsBtn"),
  instructionModal: document.getElementById("instructionModal"),
  playAgainBtn: document.getElementById("playAgainBtn"),
  backHomeBtn: document.getElementById("backHomeBtn"),
  homeFromGameOverBtn: document.getElementById("homeFromGameOverBtn"),
};

const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");

const PLAYER_COLOR = "#4ade80";
const ENEMY_COLORS = ["#f87171", "#fbbf24", "#a78bfa", "#22d3ee"];
const COIN_COLOR = "#facc15";

const state = {
  screen: "home",
  gameRunning: false,
  paused: false,
  playerName: "",
  playerId: null,
  bestScore: 0,
  score: 0,
  distance: 0,
  coins: 0,
  speed: 0,
  roadScroll: 0,
  spawnTimer: 0,
  coinTimer: 0,
  lastTime: 0,
  player: {
    x: canvas.width / 2,
    y: canvas.height - 130,
    width: 42,
    height: 72,
    lane: 1,
    moveSpeed: 8,
  },
  enemies: [],
  coinsList: [],
  keys: {
    left: false,
    right: false,
    up: false,
    down: false,
  },
};

const lanePositions = [canvas.width * 0.28, canvas.width * 0.5, canvas.width * 0.72];

function showScreen(name) {
  Object.keys(screens).forEach((key) => {
    screens[key].classList.toggle("active", key === name);
  });
  state.screen = name;
}

function getPlayerName() {
  return (ui.playerNameInput.value || "Player").trim();
}

function showInstructionModal() {
  ui.instructionModal.classList.remove("hidden");
}

function hideInstructionModal() {
  ui.instructionModal.classList.add("hidden");
}

function setPlayerNameInput() {
  const defaultName = getPlayerName() || "Player";
  ui.playerNameInput.value = defaultName;
}

function updateHud() {
  ui.scoreValue.textContent = Math.floor(state.score);
  ui.speedValue.textContent = Math.max(0, Math.round(state.speed * 16));
  ui.distanceValue.textContent = `${Math.floor(state.distance)} m`;
  ui.coinsValue.textContent = state.coins;
}

function resetGame() {
  state.gameRunning = true;
  state.paused = false;
  state.score = 0;
  state.distance = 0;
  state.coins = 0;
  state.speed = 5;
  state.roadScroll = 0;
  state.spawnTimer = 0.85;
  state.coinTimer = 1.3;
  state.enemies = [];
  state.coinsList = [];
  state.player.x = lanePositions[1];
  state.player.y = canvas.height - 130;
  state.player.lane = 1;
  updateHud();
  ui.pauseBtn.textContent = "Pause";
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function playTone(frequency, duration, volume = 0.03, type = "square") {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return;

  const audioContext = new AudioCtx();
  const oscillator = audioContext.createOscillator();
  const gainNode = audioContext.createGain();

  oscillator.type = type;
  oscillator.frequency.value = frequency;
  gainNode.gain.value = volume;

  oscillator.connect(gainNode);
  gainNode.connect(audioContext.destination);

  oscillator.start();
  oscillator.stop(audioContext.currentTime + duration);

  gainNode.gain.exponentialRampToValueAtTime(0.0001, audioContext.currentTime + duration);
}

function createCar(x, y, color) {
  return {
    x,
    y,
    width: 42,
    height: 72,
    color,
    speed: 170 + Math.random() * 140,
  };
}

function createCoin(x, y) {
  return {
    x,
    y,
    radius: 12,
    value: 10,
  };
}

function spawnEnemy() {
  const lane = Math.floor(Math.random() * lanePositions.length);
  const x = lanePositions[lane];
  state.enemies.push(createCar(x, -60, ENEMY_COLORS[Math.floor(Math.random() * ENEMY_COLORS.length)]));
}

function spawnCoin() {
  const lane = Math.floor(Math.random() * lanePositions.length);
  const x = lanePositions[lane];
  state.coinsList.push(createCoin(x, -60));
}

function handleKeys() {
  if (state.keys.left) {
    state.player.x -= state.player.moveSpeed;
  }

  if (state.keys.right) {
    state.player.x += state.player.moveSpeed;
  }

  if (state.keys.up) {
    state.speed = clamp(state.speed + 0.22, 4, 16);
  }

  if (state.keys.down) {
    state.speed = clamp(state.speed - 0.18, 4, 16);
  }

  const roadLeft = canvas.width * 0.2;
  const roadRight = canvas.width * 0.8;
  state.player.x = clamp(state.player.x, roadLeft + 25, roadRight - 25);
}

function rectsOverlap(a, b) {
  const ax = a.x - a.width / 2;
  const ay = a.y - a.height / 2;
  const bx = b.x - b.width / 2;
  const by = b.y - b.height / 2;

  return !(
    ax + a.width < bx ||
    bx + b.width < ax ||
    ay + a.height < by ||
    by + b.height < ay
  );
}

function coinOverlap(player, coin) {
  const dx = player.x - coin.x;
  const dy = player.y - coin.y;
  return Math.hypot(dx, dy) < 30;
}

function updateGame(delta) {
  if (!state.gameRunning || state.paused) return;

  state.speed = clamp(state.speed + delta * 0.06, 4, 16);
  state.distance += state.speed * delta * 6;
  state.score += state.speed * delta * 5;
  state.roadScroll += state.speed * 70 * delta;

  handleKeys();

  state.spawnTimer -= delta;
  if (state.spawnTimer <= 0) {
    spawnEnemy();
    state.spawnTimer = clamp(1.2 - state.speed * 0.04, 0.4, 1.2);
  }

  state.coinTimer -= delta;
  if (state.coinTimer <= 0) {
    spawnCoin();
    state.coinTimer = clamp(2.2 - state.speed * 0.05, 0.9, 2.2);
  }

  for (const enemy of state.enemies) {
    enemy.y += (enemy.speed + state.speed * 35) * delta;
  }

  for (const coin of state.coinsList) {
    coin.y += (120 + state.speed * 38) * delta;
  }

  state.enemies = state.enemies.filter((enemy) => enemy.y < canvas.height + 100);
  state.coinsList = state.coinsList.filter((coin) => coin.y < canvas.height + 50);

  for (const enemy of state.enemies) {
    if (rectsOverlap(state.player, enemy)) {
      endGame();
      return;
    }
  }

  for (let i = state.coinsList.length - 1; i >= 0; i -= 1) {
    const coin = state.coinsList[i];
    if (coinOverlap(state.player, coin)) {
      state.coins += 1;
      state.score += 50;
      playTone(920, 0.08, 0.05, "triangle");
      state.coinsList.splice(i, 1);
    }
  }

  state.player.y = canvas.height - 130;
  updateHud();
}

function drawRoad() {
  const roadLeft = canvas.width * 0.2;
  const roadRight = canvas.width * 0.8;
  const roadWidth = roadRight - roadLeft;

  ctx.fillStyle = "#1e293b";
  ctx.fillRect(roadLeft, 0, roadWidth, canvas.height);

  const stripeOffset = state.roadScroll % 46;
  ctx.fillStyle = "rgba(255,255,255,0.7)";
  for (let y = -46 + stripeOffset; y < canvas.height + 46; y += 46) {
    ctx.fillRect(roadLeft + roadWidth / 2 - 3, y, 6, 26);
  }

  ctx.strokeStyle = "rgba(255,255,255,0.4)";
  ctx.lineWidth = 3;
  ctx.strokeRect(roadLeft, 0, roadWidth, canvas.height);

  ctx.strokeStyle = "rgba(255,255,255,0.18)";
  ctx.beginPath();
  ctx.moveTo(roadLeft + roadWidth / 3, 0);
  ctx.lineTo(roadLeft + roadWidth / 3, canvas.height);
  ctx.moveTo(roadLeft + (roadWidth * 2) / 3, 0);
  ctx.lineTo(roadLeft + (roadWidth * 2) / 3, canvas.height);
  ctx.stroke();
}

function drawCar(car, color = PLAYER_COLOR) {
  const { x, y, width, height } = car;
  const carX = x - width / 2;
  const carY = y - height / 2;

  ctx.fillStyle = color;
  ctx.fillRect(carX, carY, width, height);

  ctx.fillStyle = "rgba(255,255,255,0.2)";
  ctx.fillRect(carX + 8, carY + 16, width - 16, height - 26);

  ctx.fillStyle = "#0f172a";
  ctx.fillRect(carX + 6, carY + 8, 8, 16);
  ctx.fillRect(carX + width - 14, carY + 8, 8, 16);
  ctx.fillRect(carX + 6, carY + height - 24, 8, 16);
  ctx.fillRect(carX + width - 14, carY + height - 24, 8, 16);
}

function drawCoin(coin) {
  const { x, y, radius } = coin;
  ctx.beginPath();
  ctx.fillStyle = COIN_COLOR;
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = "rgba(255,255,255,0.8)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(x, y, radius - 5, 0, Math.PI * 2);
  ctx.stroke();
}

function drawBackground() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  drawRoad();

  for (const coin of state.coinsList) {
    drawCoin(coin);
  }

  for (const enemy of state.enemies) {
    drawCar(enemy, enemy.color);
  }

  drawCar(state.player, PLAYER_COLOR);
}

function togglePause() {
  if (!state.gameRunning) return;
  state.paused = !state.paused;
  ui.pauseBtn.textContent = state.paused ? "Resume" : "Pause";
}

async function saveScoreToApi() {
  if (!state.playerName) return;

  try {
    const response = await fetch(`${apiBase}/api/scores`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        player_name: state.playerName,
        score: Math.floor(state.score),
        distance: Math.floor(state.distance),
        coins: state.coins,
      }),
    });

    const result = await response.json();
    if (result && result.best_score !== undefined) {
      state.bestScore = result.best_score;
    }
  } catch (error) {
    console.error("Failed to save score:", error);
  }
}

async function loadLeaderboard() {
  try {
    const response = await fetch(`${apiBase}/api/scores/top`);
    const data = await response.json();
    const scores = data && data.leaderboard ? data.leaderboard : [];

    if (!scores.length) {
      ui.leaderboardBody.innerHTML = '<tr><td colspan="6" class="empty-state">No scores yet. Start racing!</td></tr>';
      return;
    }

    ui.leaderboardBody.innerHTML = scores
      .map(
        (entry) => `
          <tr>
            <td>${entry.rank}</td>
            <td>${entry.player_name}</td>
            <td>${entry.score}</td>
            <td>${entry.distance} m</td>
            <td>${entry.coins}</td>
            <td>${entry.date}</td>
          </tr>
        `,
      )
      .join("");
  } catch (error) {
    console.error("Failed to load leaderboard:", error);
    ui.leaderboardBody.innerHTML = '<tr><td colspan="6" class="empty-state">Leaderboard unavailable.</td></tr>';
  }
}

async function registerOrLoginPlayer() {
  const name = getPlayerName();
  if (!name) {
    alert("Please enter a player name before starting.");
    ui.playerNameInput.focus();
    return;
  }

  state.playerName = name;

  try {
    const response = await fetch(`${apiBase}/api/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });

    const result = await response.json();
    if (!result.success) {
      alert(result.message || "Unable to register player.");
      return;
    }

    state.playerId = result.player.id;
  } catch (error) {
    console.error("Registration failed:", error);
    alert("Could not connect to the server. Make sure Flask is running on port 5000.");
    return;
  }

  resetGame();
  showScreen("game");
}

function endGame() {
  state.gameRunning = false;
  ui.finalScoreValue.textContent = Math.floor(state.score);
  ui.finalDistanceValue.textContent = `${Math.floor(state.distance)} m`;
  ui.finalCoinsValue.textContent = state.coins;
  ui.bestScoreValue.textContent = state.bestScore || Math.floor(state.score);
  saveScoreToApi();
  showScreen("gameOver");
}

function gameLoop(timestamp) {
  const delta = (timestamp - (state.lastTime || timestamp)) / 1000;
  state.lastTime = timestamp;

  updateGame(delta);
  drawBackground();
  requestAnimationFrame(gameLoop);
}

function attachEvents() {
  ui.startBtn.addEventListener("click", registerOrLoginPlayer);
  ui.leaderboardBtn.addEventListener("click", async () => {
    await loadLeaderboard();
    showScreen("leaderboard");
  });
  ui.backHomeBtn.addEventListener("click", () => showScreen("home"));
  ui.homeFromGameOverBtn.addEventListener("click", () => showScreen("home"));
  ui.playAgainBtn.addEventListener("click", async () => {
    await registerOrLoginPlayer();
  });
  ui.instructionBtn.addEventListener("click", showInstructionModal);
  ui.closeInstructionsBtn.addEventListener("click", hideInstructionModal);
  ui.pauseBtn.addEventListener("click", togglePause);

  document.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase();

    if (key === "arrowleft" || key === "a") {
      state.keys.left = true;
    }
    if (key === "arrowright" || key === "d") {
      state.keys.right = true;
    }
    if (key === "arrowup" || key === "w") {
      state.keys.up = true;
    }
    if (key === "arrowdown" || key === "s") {
      state.keys.down = true;
    }
    if (event.code === "Space") {
      event.preventDefault();
      togglePause();
    }
  });

  document.addEventListener("keyup", (event) => {
    const key = event.key.toLowerCase();

    if (key === "arrowleft" || key === "a") {
      state.keys.left = false;
    }
    if (key === "arrowright" || key === "d") {
      state.keys.right = false;
    }
    if (key === "arrowup" || key === "w") {
      state.keys.up = false;
    }
    if (key === "arrowdown" || key === "s") {
      state.keys.down = false;
    }
  });
}

function init() {
  setPlayerNameInput();
  attachEvents();
  showScreen("home");
  requestAnimationFrame(gameLoop);
}

init();
