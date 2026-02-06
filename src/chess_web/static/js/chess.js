// Chess game client-side logic

class ChessGame {
    constructor() {
        // Get base URL for API calls (supports nested deployments)
        const baseMeta = document.querySelector('meta[name="base-url"]');
        this.baseUrl = baseMeta ? baseMeta.content.replace(/\/$/, '') : '';

        this.selectedSquare = null;
        this.selectedPiece = null;
        this.legalMoves = [];
        this.draggingFrom = null;
        this.draggingPiece = null;
        this.isBusy = false;
        this.dragActive = false;
        this.dragGhost = null;
        this.dragStart = null;
        this.dragMoved = false;
        this.activeDropSquare = null;
        this.suppressClick = false;
        this.stateVersion = 0;
        this.gameId = null;
        this.dragSymbol = null;
        this.pendingLegalMoves = null;
        this.blurHandler = null;
        this.boardFlipped = false;
        this.soundEnabled = true;
        this.timerInterval = null;
        this.whiteTime = 600; // 10 minutes in seconds
        this.blackTime = 600;
        this.reviewMode = false;
        this.reviewStates = [];
        this.reviewIndex = 0;
        this.reviewGames = [];

        // Initialize from DOM data attributes
        const board = document.getElementById('chessboard');
        this.currentTurn = board?.dataset.currentTurn || 'white';
        this.gameOver = board?.dataset.gameOver === 'true';
        this.debugEnabled = board?.dataset.debug === 'true';
        this.debugLog = [];
        this.debugOverlay = null;

        // Load stats and preferences
        this.loadStats();
        this.loadPreferences();
        this.initializeEventListeners();
        this.initializeTimer();
        this.updateStatsDisplay();
        this.refreshStats();
        this.refreshLeaderboard();
        this.refreshHistory();

        // Fetch latest game state to ensure sync
        this.syncGameState();
    }

    loadStats() {
        const stats = localStorage.getItem('chessStats');
        if (stats) {
            const parsed = JSON.parse(stats);
            this.stats = {
                wins: parsed.wins || 0,
                losses: parsed.losses || 0,
                streak: parsed.streak || 0,
                bestStreak: parsed.bestStreak || 0
            };
        } else {
            this.stats = { wins: 0, losses: 0, streak: 0, bestStreak: 0 };
        }
    }

    saveStats() {
        localStorage.setItem('chessStats', JSON.stringify(this.stats));
        this.updateStatsDisplay();
    }

    updateStatsDisplay() {
        const winsEl = document.getElementById('wins-count');
        const lossesEl = document.getElementById('losses-count');
        const streakEl = document.getElementById('streak-count');

        if (winsEl) winsEl.textContent = this.stats.wins;
        if (lossesEl) lossesEl.textContent = this.stats.losses;
        if (streakEl) {
            streakEl.textContent = this.stats.streak;
            // Add fire animation for high streaks
            const streakItem = streakEl.closest('.stat-item');
            if (streakItem) {
                streakItem.classList.toggle('on-fire', this.stats.streak >= 3);
            }
        }
    }

    recordWin() {
        this.stats.wins++;
        this.stats.streak = Math.max(0, this.stats.streak) + 1;
        if (this.stats.streak > this.stats.bestStreak) {
            this.stats.bestStreak = this.stats.streak;
        }
        this.saveStats();
        this.showConfetti();
        setTimeout(() => this.refreshStats(), 1200);
    }

    recordLoss() {
        this.stats.losses++;
        this.stats.streak = Math.min(0, this.stats.streak) - 1;
        this.saveStats();
        setTimeout(() => this.refreshStats(), 1200);
    }

    loadPreferences() {
        const theme = localStorage.getItem('chessTheme') || 'dark';
        const sound = localStorage.getItem('chessSound') !== 'false';

        this.soundEnabled = sound;
        this.applyTheme(theme);
        this.updateSoundIcon();
    }

    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('chessTheme', theme);
        this.updateThemeIcon();
    }

    toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        const next = current === 'dark' ? 'light' : 'dark';
        this.applyTheme(next);
        this.playSound('click');
    }

    updateThemeIcon() {
        const theme = document.documentElement.getAttribute('data-theme') || 'dark';
        document.body.classList.toggle('light-theme', theme === 'light');
    }

    toggleSound() {
        this.soundEnabled = !this.soundEnabled;
        localStorage.setItem('chessSound', this.soundEnabled);
        this.updateSoundIcon();
        if (this.soundEnabled) {
            this.playSound('click');
        }
    }

    updateSoundIcon() {
        document.body.classList.toggle('sound-off', !this.soundEnabled);
    }

    playSound(type) {
        if (!this.soundEnabled) return;

        // Create audio context for simple sounds
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioCtx.destination);

            const sounds = {
                move: { freq: 300, duration: 0.1 },
                capture: { freq: 200, duration: 0.15 },
                check: { freq: 400, duration: 0.2 },
                click: { freq: 500, duration: 0.05 },
                win: { freq: 523, duration: 0.3 },
                lose: { freq: 150, duration: 0.4 }
            };

            const sound = sounds[type] || sounds.click;
            oscillator.frequency.value = sound.freq;
            oscillator.type = 'sine';
            gainNode.gain.value = 0.1;

            oscillator.start();
            oscillator.stop(audioCtx.currentTime + sound.duration);
        } catch (e) {
            // Audio not supported
        }
    }

    async fetchJson(path, options = {}) {
        const response = await fetch(`${this.baseUrl}${path}`, options);
        if (response.status === 401) {
            const nextValue = `${window.location.pathname}${window.location.search || ''}` || '/';
            const nextPath = encodeURIComponent(nextValue);
            window.location.href = `${this.baseUrl}/login?next=${nextPath}`;
            throw new Error('Unauthorized');
        }
        return response;
    }

    async refreshStats() {
        try {
            const response = await this.fetchJson('/api/records/stats', { cache: 'no-store' });
            if (!response.ok) {
                return;
            }
            const data = await response.json();
            this.stats.wins = data.wins || 0;
            this.stats.losses = data.losses || 0;
            this.stats.streak = data.streak || 0;
            this.saveStats();
        } catch (error) {
            // Keep local stats on failure
        }
    }

    initializeTimer() {
        this.updateTimerDisplay();
    }

    startTimer() {
        if (this.timerInterval) return;

        this.timerInterval = setInterval(() => {
            if (this.gameOver) {
                this.stopTimer();
                return;
            }

            if (this.currentTurn === 'white') {
                this.whiteTime = Math.max(0, this.whiteTime - 1);
            } else {
                this.blackTime = Math.max(0, this.blackTime - 1);
            }

            this.updateTimerDisplay();

            // Check for timeout
            if (this.whiteTime === 0 || this.blackTime === 0) {
                this.handleTimeout();
            }
        }, 1000);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    resetTimer() {
        this.stopTimer();
        this.whiteTime = 600;
        this.blackTime = 600;
        this.updateTimerDisplay();
    }

    updateTimerDisplay() {
        const formatTime = (seconds) => {
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            return `${mins}:${secs.toString().padStart(2, '0')}`;
        };

        const whiteTimerEl = document.querySelector('#white-timer .timer-value');
        const blackTimerEl = document.querySelector('#black-timer .timer-value');

        if (whiteTimerEl) {
            whiteTimerEl.textContent = formatTime(this.whiteTime);
            whiteTimerEl.closest('.timer').classList.toggle('active', this.currentTurn === 'white' && !this.gameOver);
            whiteTimerEl.closest('.timer').classList.toggle('low-time', this.whiteTime < 60);
        }
        if (blackTimerEl) {
            blackTimerEl.textContent = formatTime(this.blackTime);
            blackTimerEl.closest('.timer').classList.toggle('active', this.currentTurn === 'black' && !this.gameOver);
            blackTimerEl.closest('.timer').classList.toggle('low-time', this.blackTime < 60);
        }
    }

    async handleTimeout() {
        this.stopTimer();
        const loser = this.whiteTime === 0 ? 'white' : 'black';
        try {
            const response = await this.fetchJson('/timeout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ color: loser })
            });
            const data = await response.json();
            if (data.success) {
                this.gameOver = true;
                if (data.game_state) {
                    this.updateBoard(data.game_state);
                }
                this.updateGameStatus({
                    message: data.message || 'Time out',
                    in_check: false
                });
                this.showGameOverModal(data);
            } else {
                this.showGameOverModal({
                    message: `${loser.charAt(0).toUpperCase() + loser.slice(1)} ran out of time!`,
                    game_over: true
                });
                this.gameOver = true;
            }
        } catch (error) {
            console.error('Error handling timeout:', error);
            this.showGameOverModal({
                message: `${loser.charAt(0).toUpperCase() + loser.slice(1)} ran out of time!`,
                game_over: true
            });
            this.gameOver = true;
        }

        if (loser === 'black') {
            this.recordWin();
        } else {
            this.recordLoss();
        }
    }

    showConfetti() {
        const colors = ['#e94560', '#4ade80', '#fbbf24', '#60a5fa', '#c084fc'];
        const confettiCount = 100;

        for (let i = 0; i < confettiCount; i++) {
            setTimeout(() => {
                const confetti = document.createElement('div');
                confetti.className = 'confetti';
                confetti.style.left = Math.random() * 100 + 'vw';
                confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
                confetti.style.animationDuration = (Math.random() * 2 + 2) + 's';
                confetti.style.animationDelay = Math.random() * 0.5 + 's';
                document.body.appendChild(confetti);

                setTimeout(() => confetti.remove(), 4000);
            }, i * 20);
        }
    }

    flipBoard() {
        this.boardFlipped = !this.boardFlipped;
        const board = document.getElementById('chessboard');
        if (board) {
            board.classList.toggle('flipped', this.boardFlipped);
        }
        this.playSound('click');
    }

    async syncGameState() {
        try {
            const version = ++this.stateVersion;
            this.debug('syncGameState:start', { version });
            const response = await this.fetchJson('/game-state', { cache: 'no-store' });
            const gameState = await response.json();
            this.debug('syncGameState:response', {
                version,
                game_id: gameState.game_id,
                moves: (gameState.move_history || []).length
            });
            if (version !== this.stateVersion) {
                return;
            }
            if (this.gameId && gameState.game_id && gameState.game_id !== this.gameId) {
                return;
            }
            this.currentTurn = gameState.current_turn;
            this.gameOver = gameState.game_over;
            this.updateBoard(gameState);
            this.updateGameStatus({
                message: gameState.status_message || '',
                in_check: gameState.in_check || false,
            });
        } catch (error) {
            console.error('Error syncing game state:', error);
        }
    }

    initializeEventListeners() {
        // Board square clicks
        const squares = document.querySelectorAll('.square');
        squares.forEach(square => {
            square.addEventListener('click', (e) => this.handleSquareClick(e));
        });

        // Mouse and touch drag events (event delegation)
        const board = document.getElementById('chessboard');
        if (board) {
            board.style.touchAction = 'none';
            board.addEventListener('mousedown', (e) => this.handlePointerDown(e));
            board.addEventListener('touchstart', (e) => this.handlePointerDown(e), { passive: false });
        }

        // New game button
        const newGameBtn = document.getElementById('new-game-btn');
        if (newGameBtn) {
            newGameBtn.addEventListener('click', () => this.startNewGame());
        }

        // Modal new game button
        const modalNewGameBtn = document.getElementById('new-game-modal-btn');
        if (modalNewGameBtn) {
            modalNewGameBtn.addEventListener('click', () => this.startNewGame());
        }

        // Resign button
        const resignBtn = document.getElementById('resign-btn');
        if (resignBtn) {
            resignBtn.addEventListener('click', () => this.resign());
        }

        // Save game button
        const saveBtn = document.getElementById('save-game-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveGame());
        }

        // Load game button
        const loadBtn = document.getElementById('load-game-btn');
        if (loadBtn) {
            loadBtn.addEventListener('click', () => this.showLoadGameModal());
        }

        // Load game file input
        const loadInput = document.getElementById('load-game-input');
        if (loadInput) {
            loadInput.addEventListener('change', (e) => this.loadGameFile(e));
        }

        // Theme toggle
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Sound toggle
        const soundToggle = document.getElementById('sound-toggle');
        if (soundToggle) {
            soundToggle.addEventListener('click', () => this.toggleSound());
        }

        // Undo button
        const undoBtn = document.getElementById('undo-btn');
        if (undoBtn) {
            undoBtn.addEventListener('click', () => this.undoMove());
        }

        // Flip board button
        const flipBtn = document.getElementById('flip-board-btn');
        if (flipBtn) {
            flipBtn.addEventListener('click', () => this.flipBoard());
        }

        const reviewPrevBtn = document.getElementById('review-prev-btn');
        if (reviewPrevBtn) {
            reviewPrevBtn.addEventListener('click', () => this.stepReview(-1));
        }

        const reviewNextBtn = document.getElementById('review-next-btn');
        if (reviewNextBtn) {
            reviewNextBtn.addEventListener('click', () => this.stepReview(1));
        }

        const reviewExitBtn = document.getElementById('review-exit-btn');
        if (reviewExitBtn) {
            reviewExitBtn.addEventListener('click', () => this.exitReviewMode());
        }
    }

    async refreshLeaderboard() {
        const list = document.getElementById('leaderboard-list');
        if (!list) return;

        try {
            const response = await this.fetchJson('/api/records/leaderboard', { cache: 'no-store' });
            if (!response.ok) {
                throw new Error('Failed leaderboard');
            }
            const data = await response.json();
            const leaders = data.leaders || [];
            if (!leaders.length) {
                list.innerHTML = '<p class="no-moves">No leaderboard data</p>';
                return;
            }
            list.innerHTML = '';
            leaders.forEach((entry) => {
                const row = document.createElement('div');
                row.className = 'leaderboard-entry';
                row.innerHTML = `
                    <div class="leaderboard-rank">${entry.rank}</div>
                    <div class="leaderboard-name">${entry.player_name || 'Anonymous'}</div>
                    <div class="leaderboard-points">${entry.points} pts</div>
                `;
                list.appendChild(row);
            });
        } catch (error) {
            list.innerHTML = '<p class="no-moves">Leaderboard unavailable</p>';
        }
    }

    async refreshHistory() {
        const list = document.getElementById('review-list');
        if (!list) return;

        try {
            const response = await this.fetchJson('/api/records/history', { cache: 'no-store' });
            if (!response.ok) {
                throw new Error('Unauthorized');
            }
            const data = await response.json();
            this.reviewGames = data.games || [];
            if (!this.reviewGames.length) {
                list.innerHTML = '<p class="no-moves">No finished games</p>';
                return;
            }
            list.innerHTML = '';
            this.reviewGames.forEach((game) => {
                const item = document.createElement('div');
                item.className = 'review-item';
                item.dataset.gameId = game.game_id;
                const result = (game.result || 'draw').toUpperCase();
                const dateLabel = game.finished_at ? new Date(game.finished_at).toLocaleString() : 'Unknown date';
                item.innerHTML = `
                    <div class="review-meta">
                        <div class="review-result">${result}</div>
                        <div class="review-date">${dateLabel}</div>
                    </div>
                    <div>${game.moves_count || 0} moves</div>
                `;
                item.addEventListener('click', () => this.loadReviewGame(game.game_id));
                list.appendChild(item);
            });
        } catch (error) {
            list.innerHTML = '<p class="no-moves">History unavailable</p>';
        }
    }

    async loadReviewGame(gameId) {
        if (!gameId) return;
        try {
            const response = await this.fetchJson(`/api/records/history/${gameId}`, { cache: 'no-store' });
            if (!response.ok) {
                throw new Error('Review failed');
            }
            const data = await response.json();
            const replay = data.replay || [];
            if (!replay.length) {
                this.showNotification('No replay data', 'error');
                return;
            }
            this.reviewStates = replay;
            this.reviewIndex = 0;
            this.reviewMode = true;
            this.stopTimer();
            this.updateBoard(this.reviewStates[0]);
            this.updateReviewProgress();
            this.highlightReviewItem(gameId);
            const summary = data.game || {};
            this.updateGameStatus({
                message: summary.status_message || 'Review mode',
                in_check: false
            });
        } catch (error) {
            this.showNotification('Failed to load review', 'error');
        }
    }

    highlightReviewItem(gameId) {
        const items = document.querySelectorAll('.review-item');
        items.forEach((item) => {
            item.classList.toggle('active', item.dataset.gameId === gameId);
        });
    }

    stepReview(direction) {
        if (!this.reviewMode || !this.reviewStates.length) {
            return;
        }
        const nextIndex = Math.max(0, Math.min(this.reviewStates.length - 1, this.reviewIndex + direction));
        if (nextIndex === this.reviewIndex) {
            return;
        }
        this.reviewIndex = nextIndex;
        this.updateBoard(this.reviewStates[this.reviewIndex]);
        this.updateReviewProgress();
    }

    updateReviewProgress() {
        const progress = document.getElementById('review-progress');
        const prevBtn = document.getElementById('review-prev-btn');
        const nextBtn = document.getElementById('review-next-btn');
        if (progress) {
            if (!this.reviewMode || !this.reviewStates.length) {
                progress.textContent = 'No game loaded';
            } else {
                progress.textContent = `Move ${this.reviewIndex} / ${this.reviewStates.length - 1}`;
            }
        }
        if (prevBtn) {
            prevBtn.disabled = !this.reviewMode || this.reviewIndex <= 0;
        }
        if (nextBtn) {
            nextBtn.disabled = !this.reviewMode || this.reviewIndex >= this.reviewStates.length - 1;
        }
    }

    exitReviewMode() {
        if (!this.reviewMode) return;
        this.reviewMode = false;
        this.reviewStates = [];
        this.reviewIndex = 0;
        this.updateReviewProgress();
        this.syncGameState();
        this.showNotification('Review mode exited', 'info');
    }

    async handleSquareClick(event) {
        if (this.suppressClick) {
            this.suppressClick = false;
            return;
        }
        if (this.reviewMode || this.gameOver || this.isBusy) {
            return;
        }

        const square = event.currentTarget;
        const row = parseInt(square.dataset.row);
        const col = parseInt(square.dataset.col);

        // If a piece is already selected
        if (this.selectedSquare) {
            // Check if clicked square is a legal move
            const isLegalMove = this.legalMoves.some(
                move => move[0] === row && move[1] === col
            );

            if (isLegalMove) {
                // Check if this is a pawn promotion
                const [fromRow, fromCol] = this.selectedSquare;
                const fromSquare = document.querySelector(
                    `.square[data-row="${fromRow}"][data-col="${fromCol}"]`
                );
                const piece = fromSquare.querySelector('.piece');

                if (piece && piece.dataset.pieceType === 'pawn' && (row === 0 || row === 7)) {
                    // Show promotion modal
                    this.showPromotionModal(this.selectedSquare, [row, col]);
                } else {
                    // Make the move
                    await this.makeMove(this.selectedSquare, [row, col]);
                }
            } else {
                // Check if clicking on own piece to select it
                const piece = square.querySelector('.piece');
                if (piece && piece.dataset.pieceColor === this.currentTurn) {
                    this.selectSquare(square, row, col);
                } else {
                    // Deselect
                    this.deselectSquare();
                }
            }
        } else {
            // Select a piece
            const piece = square.querySelector('.piece');
            if (piece) {
                if (piece.dataset.pieceColor === this.currentTurn) {
                    this.selectSquare(square, row, col);
                } else {
                    // Show message when trying to move opponent's piece
                    this.showTurnWarning();
                }
            }
        }
    }

    async selectSquare(square, row, col) {
        // Deselect previous square
        this.deselectSquare();

        // Select new square
        this.selectedSquare = [row, col];
        square.classList.add('selected');

        await this.fetchLegalMoves(row, col, true);
    }

    deselectSquare() {
        if (this.selectedSquare) {
            const [row, col] = this.selectedSquare;
            const square = document.querySelector(
                `.square[data-row="${row}"][data-col="${col}"]`
            );
            if (square) {
                square.classList.remove('selected');
            }
        }

        this.selectedSquare = null;
        this.draggingFrom = null;
        this.legalMoves = [];
        this.removeHighlights();
    }

    async fetchLegalMoves(row, col, highlight) {
        try {
            this.debug('legalMoves:request', { row, col });
            const response = await this.fetchJson('/legal-moves', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ position: [row, col] }),
            });

            const data = await response.json();
            this.debug('legalMoves:response', { ok: data.success, count: (data.legal_moves || []).length });
            if (data.success) {
                this.legalMoves = data.legal_moves;
                if (highlight) {
                    this.highlightLegalMoves();
                }
            }
        } catch (error) {
            console.error('Error fetching legal moves:', error);
        }
    }

    highlightLegalMoves() {
        this.legalMoves.forEach(([row, col]) => {
            const square = document.querySelector(
                `.square[data-row="${row}"][data-col="${col}"]`
            );
            if (square) {
                square.classList.add('legal-move');
                if (square.querySelector('.piece')) {
                    square.classList.add('has-piece');
                }
            }
        });
    }

    removeHighlights() {
        const highlightedSquares = document.querySelectorAll('.legal-move');
        highlightedSquares.forEach(square => {
            square.classList.remove('legal-move', 'has-piece');
        });
    }

    async makeMove(fromPos, toPos, promotionPiece = 'queen') {
        try {
            this.isBusy = true;
            this.debug('move:request', { from: fromPos, to: toPos, promotion: promotionPiece });
            const response = await this.fetchJson('/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    from: fromPos,
                    to: toPos,
                    promotion_piece: promotionPiece,
                }),
            });

            const data = await response.json();
            this.debug('move:response', {
                ok: data.success,
                game_over: data.game_over,
                moves: data.game_state?.move_history?.length
            });

            if (data.success) {
                // Start timer on first move
                if (!this.timerInterval) {
                    this.startTimer();
                }

                // Play appropriate sound
                if (data.captured) {
                    this.playSound('capture');
                } else {
                    this.playSound('move');
                }

                if (data.in_check) {
                    this.playSound('check');
                }

                // Update the board
                this.updateBoard(data.game_state);
                this.updateGameStatus(data);

                // Check if game is over
                if (data.game_over) {
                    this.gameOver = true;
                    this.stopTimer();
                    this.showGameOverModal(data);

                    // Record win/loss based on result
                    if (data.message && data.message.includes('wins')) {
                        if (data.message.includes('White wins')) {
                            this.recordWin();
                            this.playSound('win');
                        } else {
                            this.recordLoss();
                            this.playSound('lose');
                        }
                    }
                } else {
                    this.maybeRequestAiMove(data.game_state);
                }
            } else {
                alert(data.message || 'Invalid move');
            }

            this.deselectSquare();
        } catch (error) {
            console.error('Error making move:', error);
            alert('Error making move. Please try again.');
        } finally {
            this.isBusy = false;
        }
    }

    async maybeRequestAiMove(gameState) {
        if (!gameState || !gameState.ai_enabled || gameState.game_over) {
            return;
        }
        if (gameState.current_turn !== gameState.ai_color) {
            return;
        }

        this.isBusy = true;
        this.updateGameStatus({ message: 'AI thinking...', in_check: false });
        this.debug('aiMove:request', {});

        try {
            const response = await this.fetchJson('/ai-move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const data = await response.json();
            this.debug('aiMove:response', {
                ok: data.success,
                moves: data.game_state?.move_history?.length
            });
            if (data.success) {
                this.updateBoard(data.game_state);
                this.updateGameStatus(data);
                if (data.game_over) {
                    this.gameOver = true;
                    this.showGameOverModal(data);
                }
            } else {
                this.updateGameStatus({ message: data.message || 'AI move failed', in_check: false });
            }
        } catch (error) {
            console.error('Error making AI move:', error);
            this.updateGameStatus({ message: 'AI move failed', in_check: false });
        } finally {
            this.isBusy = false;
        }
    }

    updateBoard(gameState) {
        const board = gameState.board.board;
        const moveHistory = Array.isArray(gameState.move_history) ? gameState.move_history : [];
        if (gameState.game_id) {
            this.gameId = gameState.game_id;
        }

        // Clear all pieces
        document.querySelectorAll('.piece').forEach(piece => piece.remove());

        // Place pieces according to new state
        for (let row = 0; row < 8; row++) {
            for (let col = 0; col < 8; col++) {
                const pieceData = board[row][col];
                if (pieceData) {
                    const square = document.querySelector(
                        `.square[data-row="${row}"][data-col="${col}"]`
                    );
                    if (square) {
                        const pieceElement = this.createPieceElement(pieceData);
                        square.appendChild(pieceElement);
                    }
                }
            }
        }

        // Update current turn
        this.currentTurn = gameState.current_turn;

        // Update move history
        this.updateMoveHistory(moveHistory);

        // Update captured pieces
        this.updateCapturedPieces(gameState.captured_pieces);
    }

    createPieceElement(pieceData) {
        const piece = document.createElement('div');
        piece.className = `piece ${pieceData.color} ${pieceData.type}`;
        piece.dataset.pieceType = pieceData.type;
        piece.dataset.pieceColor = pieceData.color;
        piece.draggable = false;
        return piece;
    }

    updateGameStatus(data) {
        const statusMessage = document.getElementById('status-message');
        const turnIndicator = document.getElementById('turn-indicator');

        if (statusMessage) {
            statusMessage.textContent = data.message;
            if (data.in_check) {
                statusMessage.classList.add('check');
            } else {
                statusMessage.classList.remove('check');
            }
        }

        if (turnIndicator) {
            const turnColor = this.currentTurn;
            turnIndicator.innerHTML = `Current Turn: <span class="turn-color ${turnColor}">${turnColor.charAt(0).toUpperCase() + turnColor.slice(1)}</span>`;
        }
    }

    showTurnWarning() {
        const statusMessage = document.getElementById('status-message');
        if (statusMessage) {
            const originalText = statusMessage.textContent;
            statusMessage.textContent = `It's ${this.currentTurn}'s turn!`;
            statusMessage.classList.add('check');

            // Revert after 2 seconds
            setTimeout(() => {
                statusMessage.textContent = originalText;
                if (!this.gameOver) {
                    statusMessage.classList.remove('check');
                }
            }, 2000);
        }
    }

    updateMoveHistory(moveHistory) {
        const moveHistoryDiv = document.getElementById('move-history');
        if (!moveHistoryDiv) return;

        if (moveHistory.length === 0) {
            moveHistoryDiv.innerHTML = '<div class="no-moves">No moves yet</div>';
        } else {
            const container = document.createElement('div');
            container.className = 'move-list';

            // Pair moves: white and black together with move numbers
            for (let i = 0; i < moveHistory.length; i += 2) {
                const moveNum = Math.floor(i / 2) + 1;
                const whiteMove = moveHistory[i].notation;
                const blackMove = i + 1 < moveHistory.length ? moveHistory[i + 1].notation : '';

                const row = document.createElement('div');
                row.className = 'move-row';

                const numSpan = document.createElement('span');
                numSpan.className = 'move-number';
                numSpan.textContent = `${moveNum}.`;

                const whiteSpan = document.createElement('span');
                whiteSpan.className = 'move-white';
                whiteSpan.textContent = whiteMove;

                const blackSpan = document.createElement('span');
                blackSpan.className = 'move-black';
                blackSpan.textContent = blackMove || '';

                row.appendChild(numSpan);
                row.appendChild(whiteSpan);
                row.appendChild(blackSpan);
                container.appendChild(row);
            }

            moveHistoryDiv.innerHTML = '';
            moveHistoryDiv.appendChild(container);

            // Scroll to bottom
            moveHistoryDiv.scrollTop = moveHistoryDiv.scrollHeight;
        }
    }

    updateCapturedPieces(capturedPieces) {
        const whiteList = document.querySelector('.captured-white .captured-list');
        const blackList = document.querySelector('.captured-black .captured-list');
        if (!whiteList || !blackList) return;

        const renderList = (target, pieces) => {
            target.innerHTML = '';
            if (!pieces || !pieces.length) {
                target.innerHTML = '<span class="none">None</span>';
                return;
            }
            pieces.forEach((pieceData) => {
                if (!pieceData || !pieceData.type || !pieceData.color) return;
                const piece = document.createElement('div');
                piece.className = `captured-piece piece ${pieceData.color} ${pieceData.type}`;
                piece.dataset.pieceType = pieceData.type;
                piece.dataset.pieceColor = pieceData.color;
                target.appendChild(piece);
            });
        };

        renderList(whiteList, capturedPieces?.white || []);
        renderList(blackList, capturedPieces?.black || []);
    }

    showPromotionModal(fromPos, toPos) {
        const modal = document.getElementById('promotion-modal');
        if (!modal) return;

        // Show the modal
        modal.style.display = 'flex';

        // Add click handlers to promotion buttons
        const promotionButtons = modal.querySelectorAll('.promotion-btn');
        promotionButtons.forEach(btn => {
            // Remove any existing listeners by cloning
            const newBtn = btn.cloneNode(true);
            btn.parentNode.replaceChild(newBtn, btn);

            newBtn.addEventListener('click', async () => {
                const piece = newBtn.dataset.piece;
                modal.style.display = 'none';

                // Make the move with the selected promotion piece
                await this.makeMove(fromPos, toPos, piece);
            });
        });
    }

    showGameOverModal(data) {
        const modal = document.getElementById('game-over-modal');
        const title = document.getElementById('game-over-title');
        const message = document.getElementById('game-over-message');

        if (modal && title && message) {
            title.textContent = 'Game Over!';
            message.textContent = data.message;
            modal.style.display = 'flex';
        }
    }

    hideGameOverModal() {
        const modal = document.getElementById('game-over-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    async startNewGame() {
        try {
            if (this.reviewMode) {
                this.exitReviewMode();
            }
            this.stateVersion += 1;
            this.gameId = null;
            this.debug('newGame:request', {});
            const response = await this.fetchJson('/new-game', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });

            const data = await response.json();
            this.debug('newGame:response', {
                ok: data.success,
                game_id: data.game_state?.game_id,
                moves: data.game_state?.move_history?.length
            });

            if (data.success) {
                this.gameOver = false;
                this.resetTimer();
                this.updateBoard(data.game_state);
                this.updateGameStatus({
                    message: data.message || "New game started",
                    in_check: false,
                });
                this.updateMoveHistory([]);
                this.hideGameOverModal();
                this.deselectSquare();
                this.playSound('click');
            }
        } catch (error) {
            console.error('Error starting new game:', error);
            alert('Error starting new game. Please try again.');
        }
    }

    async resign() {
        if (this.gameOver) {
            return;
        }

        const confirmed = confirm(`Are you sure you want to resign as ${this.currentTurn}?`);
        if (!confirmed) {
            return;
        }

        try {
            const response = await this.fetchJson('/resign', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    color: this.currentTurn,
                }),
            });

            const data = await response.json();

            if (data.success) {
                this.gameOver = true;
                this.stopTimer();
                this.recordLoss();
                this.playSound('lose');
                this.showGameOverModal(data);
            }
        } catch (error) {
            console.error('Error resigning:', error);
            alert('Error processing resignation. Please try again.');
        }
    }

    clearDragOver() {
        document.querySelectorAll('.square.drag-over').forEach(square => {
            square.classList.remove('drag-over');
        });
    }

    cleanupDragState() {
        // Remove event listeners
        if (this.pointerMoveHandler) {
            document.removeEventListener('mousemove', this.pointerMoveHandler);
            document.removeEventListener('touchmove', this.pointerMoveHandler);
        }
        if (this.pointerUpHandler) {
            document.removeEventListener('mouseup', this.pointerUpHandler);
            document.removeEventListener('touchend', this.pointerUpHandler);
            document.removeEventListener('touchcancel', this.pointerUpHandler);
        }
        this.pointerMoveHandler = null;
        this.pointerUpHandler = null;

        // Remove dragging class from source piece
        if (this.draggingPiece) {
            this.draggingPiece.classList.remove('dragging');
            this.draggingPiece = null;
        }

        // Clear visual states
        this.clearDragGhost();
        this.clearDragOver();
        if (this.activeDropSquare) {
            this.activeDropSquare.classList.remove('drag-over');
            this.activeDropSquare = null;
        }

        // Reset drag state
        this.dragActive = false;
        this.dragMoved = false;
        this.dragStart = null;
        this.dragSymbol = null;
        this.pendingLegalMoves = null;
    }

    handlePointerDown(event) {
        // Handle both mouse and touch events
        const isTouch = event.type === 'touchstart';
        const clientX = isTouch ? event.touches[0].clientX : event.clientX;
        const clientY = isTouch ? event.touches[0].clientY : event.clientY;

        // Only handle left mouse button for mouse events
        if (!isTouch && event.button !== 0) {
            return;
        }

        if (this.reviewMode || this.gameOver || this.isBusy) {
            return;
        }

        const piece = event.target.closest('.piece');
        if (!piece) {
            return;
        }

        if (piece.dataset.pieceColor !== this.currentTurn) {
            this.showTurnWarning();
            return;
        }

        // Prevent default to avoid text selection and scrolling
        event.preventDefault();

        const square = piece.parentElement;
        const row = parseInt(square.dataset.row);
        const col = parseInt(square.dataset.col);

        this.debug('drag:start', { row, col, type: event.type });
        this.dragActive = true;
        this.dragMoved = false;
        this.dragStart = { x: clientX, y: clientY };
        this.draggingFrom = [row, col];
        this.dragSymbol = piece.textContent;
        this.draggingPiece = piece;
        this.pendingLegalMoves = null;

        // Bind event handlers
        this.pointerMoveHandler = (e) => this.handlePointerMove(e);
        this.pointerUpHandler = (e) => this.handlePointerUp(e);

        // Add listeners for both mouse and touch
        document.addEventListener('mousemove', this.pointerMoveHandler);
        document.addEventListener('mouseup', this.pointerUpHandler);
        document.addEventListener('touchmove', this.pointerMoveHandler, { passive: false });
        document.addEventListener('touchend', this.pointerUpHandler);
        document.addEventListener('touchcancel', this.pointerUpHandler);

        // Handle cleanup if window loses focus
        this.blurHandler = () => this.cleanupDragState();
        window.addEventListener('blur', this.blurHandler, { once: true });
    }

    handlePointerMove(event) {
        if (!this.dragActive || this.isBusy) {
            return;
        }

        // Handle both mouse and touch events
        const isTouch = event.type === 'touchmove';
        const clientX = isTouch ? event.touches[0].clientX : event.clientX;
        const clientY = isTouch ? event.touches[0].clientY : event.clientY;

        // Prevent scrolling on touch devices
        if (isTouch) {
            event.preventDefault();
        }

        if (!this.dragMoved) {
            const dx = clientX - this.dragStart.x;
            const dy = clientY - this.dragStart.y;
            // Dead zone of 4 pixels (16 = 4^2)
            if ((dx * dx) + (dy * dy) < 16) {
                return;
            }
            this.dragMoved = true;
            this.suppressClick = true;
            this.createDragGhost(this.draggingPiece);

            // Add dragging class to source piece for visual feedback
            if (this.draggingPiece) {
                this.draggingPiece.classList.add('dragging');
            }

            if (this.draggingFrom) {
                const [row, col] = this.draggingFrom;
                const fromSquare = document.querySelector(
                    `.square[data-row="${row}"][data-col="${col}"]`
                );
                // Save draggingFrom before deselectSquare clears it
                const savedDraggingFrom = this.draggingFrom;
                this.deselectSquare();
                // Restore draggingFrom since we're still dragging
                this.draggingFrom = savedDraggingFrom;
                if (fromSquare) {
                    this.selectedSquare = [row, col];
                    fromSquare.classList.add('selected');
                }
                // Store the promise so we can await it in handlePointerUp if needed
                this.pendingLegalMoves = this.fetchLegalMoves(row, col, true);
            }
        }

        if (this.dragMoved) {
            this.moveDragGhost(clientX, clientY);
        }

        const square = document.elementFromPoint(clientX, clientY)?.closest('.square');
        if (square === this.activeDropSquare) {
            return;
        }

        if (this.activeDropSquare) {
            this.activeDropSquare.classList.remove('drag-over');
        }

        if (square) {
            const row = parseInt(square.dataset.row);
            const col = parseInt(square.dataset.col);
            const isLegal = this.legalMoves.some(
                move => move[0] === row && move[1] === col
            );
            if (isLegal) {
                square.classList.add('drag-over');
                this.activeDropSquare = square;
            } else {
                this.activeDropSquare = null;
            }
        } else {
            this.activeDropSquare = null;
        }
    }

    async handlePointerUp(event) {
        if (!this.dragActive) {
            return;
        }

        // Remove blur handler since we're handling the end properly
        if (this.blurHandler) {
            window.removeEventListener('blur', this.blurHandler);
            this.blurHandler = null;
        }

        // Handle both mouse and touch events
        const isTouch = event.type === 'touchend' || event.type === 'touchcancel';
        let clientX, clientY;

        if (isTouch) {
            // For touchend, use changedTouches since touches array is empty
            if (event.changedTouches && event.changedTouches.length > 0) {
                clientX = event.changedTouches[0].clientX;
                clientY = event.changedTouches[0].clientY;
            } else {
                // Fallback to last known position from dragStart
                clientX = this.dragStart?.x || 0;
                clientY = this.dragStart?.y || 0;
            }
        } else {
            clientX = event.clientX;
            clientY = event.clientY;
        }

        // Remove event listeners
        document.removeEventListener('mousemove', this.pointerMoveHandler);
        document.removeEventListener('mouseup', this.pointerUpHandler);
        document.removeEventListener('touchmove', this.pointerMoveHandler);
        document.removeEventListener('touchend', this.pointerUpHandler);
        document.removeEventListener('touchcancel', this.pointerUpHandler);
        this.pointerMoveHandler = null;
        this.pointerUpHandler = null;

        // Remove dragging class from source piece
        if (this.draggingPiece) {
            this.draggingPiece.classList.remove('dragging');
            this.draggingPiece = null;
        }

        const square = document.elementFromPoint(clientX, clientY)?.closest('.square');

        if (!this.dragMoved) {
            this.dragActive = false;
            this.dragStart = null;
            this.draggingFrom = null;
            this.dragSymbol = null;
            this.pendingLegalMoves = null;
            this.clearDragGhost();
            return;
        }

        this.debug('drag:drop', {
            to: square ? [parseInt(square.dataset.row), parseInt(square.dataset.col)] : null
        });

        if (square && this.draggingFrom) {
            // Wait for pending legal moves fetch to complete
            if (this.pendingLegalMoves) {
                await this.pendingLegalMoves;
                this.pendingLegalMoves = null;
            }

            // If still no legal moves, fetch them now
            if (this.legalMoves.length === 0) {
                await this.fetchLegalMoves(this.draggingFrom[0], this.draggingFrom[1], false);
            }

            const row = parseInt(square.dataset.row);
            const col = parseInt(square.dataset.col);
            const isLegalMove = this.legalMoves.some(
                move => move[0] === row && move[1] === col
            );

            if (isLegalMove) {
                const [fromRow, fromCol] = this.draggingFrom;
                const fromSquare = document.querySelector(
                    `.square[data-row="${fromRow}"][data-col="${fromCol}"]`
                );
                const piece = fromSquare?.querySelector('.piece');

                if (piece && piece.dataset.pieceType === 'pawn' && (row === 0 || row === 7)) {
                    this.showPromotionModal(this.draggingFrom, [row, col]);
                } else {
                    await this.makeMove(this.draggingFrom, [row, col]);
                }
            }
        }

        if (this.activeDropSquare) {
            this.activeDropSquare.classList.remove('drag-over');
            this.activeDropSquare = null;
        }

        this.dragActive = false;
        this.dragMoved = false;
        this.pendingLegalMoves = null;
        this.clearDragGhost();
        this.clearDragOver();
        this.deselectSquare();
    }

    createDragGhost(pieceElement) {
        if (!pieceElement) {
            return;
        }
        this.clearDragGhost();
        const ghost = pieceElement.cloneNode(true);
        ghost.className = pieceElement.className + ' drag-ghost';
        ghost.classList.remove('dragging');
        document.body.appendChild(ghost);
        this.dragGhost = ghost;
    }

    moveDragGhost(x, y) {
        if (!this.dragGhost) {
            return;
        }
        this.dragGhost.style.left = `${x}px`;
        this.dragGhost.style.top = `${y}px`;
    }

    clearDragGhost() {
        if (this.dragGhost) {
            this.dragGhost.remove();
            this.dragGhost = null;
        }
    }

    async saveGame() {
        try {
            const response = await this.fetchJson('/game-state', { cache: 'no-store' });
            const gameState = await response.json();

            const saveData = {
                version: 1,
                timestamp: new Date().toISOString(),
                gameState: gameState
            };

            const blob = new Blob([JSON.stringify(saveData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = url;
            const date = new Date().toISOString().slice(0, 10);
            const moveCount = (gameState.move_history || []).length;
            a.download = `chess-game-${date}-${moveCount}moves.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.showNotification('Game saved!', 'success');
        } catch (error) {
            console.error('Error saving game:', error);
            this.showNotification('Failed to save game', 'error');
        }
    }

    showLoadGameModal() {
        const input = document.getElementById('load-game-input');
        if (input) {
            input.click();
        }
    }

    async loadGameFile(event) {
        const file = event.target.files[0];
        if (!file) return;

        try {
            const text = await file.text();
            const saveData = JSON.parse(text);

            if (!saveData.gameState) {
                throw new Error('Invalid save file format');
            }

            const response = await this.fetchJson('/load-game', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ game_state: saveData.gameState })
            });

            const data = await response.json();

            if (data.success) {
                this.gameOver = data.game_state.game_over;
                this.currentTurn = data.game_state.current_turn;
                this.updateBoard(data.game_state);
                this.updateGameStatus({
                    message: data.message || 'Game loaded',
                    in_check: data.game_state.in_check || false
                });
                this.hideGameOverModal();
                this.deselectSquare();
                this.showNotification('Game loaded!', 'success');
            } else {
                throw new Error(data.message || 'Failed to load game');
            }
        } catch (error) {
            console.error('Error loading game:', error);
            this.showNotification('Failed to load game: ' + error.message, 'error');
        }

        // Reset file input
        event.target.value = '';
    }

    showNotification(message, type = 'info') {
        // Remove existing notification
        const existing = document.querySelector('.notification');
        if (existing) existing.remove();

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);

        // Trigger animation
        setTimeout(() => notification.classList.add('show'), 10);

        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    async undoMove() {
        if (this.gameOver || this.isBusy) return;

        try {
            const response = await this.fetchJson('/undo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();

            if (data.success) {
                this.updateBoard(data.game_state);
                this.updateGameStatus({
                    message: 'Move undone',
                    in_check: data.game_state.in_check || false
                });
                this.deselectSquare();
                this.playSound('click');
                this.showNotification('Move undone', 'info');
            } else {
                this.showNotification(data.message || 'Cannot undo', 'error');
            }
        } catch (error) {
            console.error('Error undoing move:', error);
            this.showNotification('Failed to undo move', 'error');
        }
    }

    debug(event, data) {
        if (!this.debugEnabled) return;
        const entry = { t: new Date().toISOString(), event, data };
        this.debugLog.push(entry);
        if (this.debugLog.length > 50) {
            this.debugLog.shift();
        }
        if (!this.debugOverlay) {
            this.debugOverlay = document.createElement('pre');
            this.debugOverlay.id = 'debug-overlay';
            this.debugOverlay.style.position = 'fixed';
            this.debugOverlay.style.right = '10px';
            this.debugOverlay.style.bottom = '10px';
            this.debugOverlay.style.width = '360px';
            this.debugOverlay.style.maxHeight = '40vh';
            this.debugOverlay.style.overflow = 'auto';
            this.debugOverlay.style.padding = '8px';
            this.debugOverlay.style.background = 'rgba(0,0,0,0.8)';
            this.debugOverlay.style.color = '#fff';
            this.debugOverlay.style.fontSize = '11px';
            this.debugOverlay.style.zIndex = '2000';
            this.debugOverlay.style.borderRadius = '6px';
            document.body.appendChild(this.debugOverlay);
        }
        this.debugOverlay.textContent = this.debugLog
            .map(item => `${item.event} ${JSON.stringify(item.data)}`)
            .join('\n');
    }
}

// Initialize the game when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.chessGame = new ChessGame();
});
