// Review page logic

class ReviewPage {
    constructor() {
        const baseMeta = document.querySelector('meta[name="base-url"]');
        this.baseUrl = baseMeta ? baseMeta.content.replace(/\/$/, '') : '';
        this.reviewGames = [];
        this.reviewStates = [];
        this.reviewMoves = [];
        this.activeGameId = null;
        this.activeMoveIndex = 0;

        this.initTheme();
        this.loadHistory();
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

    initTheme() {
        const theme = localStorage.getItem('chessTheme') || 'dark';
        this.applyTheme(theme);

        const toggle = document.getElementById('theme-toggle');
        if (toggle) {
            toggle.addEventListener('click', () => {
                const current = document.documentElement.getAttribute('data-theme') || 'dark';
                const next = current === 'dark' ? 'light' : 'dark';
                this.applyTheme(next);
            });
        }
    }

    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.body.classList.toggle('light-theme', theme === 'light');
        localStorage.setItem('chessTheme', theme);
    }

    async loadHistory() {
        const list = document.getElementById('review-list');
        if (!list) return;

        try {
            const response = await this.fetchJson('/api/records/history', { cache: 'no-store' });
            if (!response.ok) {
                throw new Error('Failed to load history');
            }
            const data = await response.json();
            this.reviewGames = data.games || [];
            if (!this.reviewGames.length) {
                list.innerHTML = '<p class="no-moves">No games yet</p>';
                return;
            }
            list.innerHTML = '';
            this.reviewGames.forEach((game) => {
                const item = document.createElement('div');
                item.className = 'review-item';
                item.dataset.gameId = game.game_id;
                const finished = Boolean(game.game_over);
                const result = finished ? (game.result || 'draw').toUpperCase() : 'IN PROGRESS';
                const dateLabel = game.finished_at ? new Date(game.finished_at).toLocaleString() : 'In progress';
                const statusLabel = finished ? 'Finished' : 'In progress';
                item.innerHTML = `
                    <div class="review-meta">
                        <div class="review-result">${result}</div>
                        <div class="review-date">${dateLabel}</div>
                    </div>
                    <div class="review-status">
                        <span>${statusLabel}</span>
                        <span>${game.moves_count || 0} moves</span>
                    </div>
                `;
                if (!finished) {
                    const resumeBtn = document.createElement('button');
                    resumeBtn.type = 'button';
                    resumeBtn.className = 'review-resume';
                    resumeBtn.textContent = 'Resume';
                    resumeBtn.addEventListener('click', (event) => {
                        event.stopPropagation();
                        this.resumeGame(game.game_id);
                    });
                    item.appendChild(resumeBtn);
                }
                item.addEventListener('click', () => this.loadGame(game.game_id));
                list.appendChild(item);
            });
        } catch (error) {
            list.innerHTML = '<p class="no-moves">History unavailable</p>';
        }
    }

    async loadGame(gameId) {
        if (!gameId) return;
        try {
            const response = await this.fetchJson(`/api/records/history/${gameId}`, { cache: 'no-store' });
            if (!response.ok) {
                throw new Error('Failed to load review');
            }
            const data = await response.json();
            this.reviewStates = data.replay || [];
            this.reviewMoves = data.moves || [];
            this.activeGameId = gameId;
            this.activeMoveIndex = 0;

            this.updateBoard(this.reviewStates[0] || null);
            this.renderMoveList();
            this.updateProgress();
            this.highlightGameItem();
        } catch (error) {
            this.showMessage('review-moves', 'Failed to load game');
        }
    }

    resumeGame(gameId) {
        if (!gameId) return;
        window.location.href = `${this.baseUrl}/resume/${gameId}`;
    }

    highlightGameItem() {
        const items = document.querySelectorAll('.review-item');
        items.forEach((item) => {
            item.classList.toggle('active', item.dataset.gameId === this.activeGameId);
        });
    }

    renderMoveList() {
        const movesContainer = document.getElementById('review-moves');
        if (!movesContainer) return;

        if (!this.reviewMoves.length) {
            movesContainer.innerHTML = '<p class="no-moves">No moves recorded</p>';
            return;
        }

        const container = document.createElement('div');
        container.className = 'move-list review-move-list';

        for (let i = 0; i < this.reviewMoves.length; i += 2) {
            const moveNum = Math.floor(i / 2) + 1;
            const whiteMove = this.reviewMoves[i];
            const blackMove = i + 1 < this.reviewMoves.length ? this.reviewMoves[i + 1] : null;

            const row = document.createElement('div');
            row.className = 'move-row review-move-row';

            const numSpan = document.createElement('span');
            numSpan.className = 'move-number';
            numSpan.textContent = `${moveNum}.`;

            const whiteSpan = document.createElement('span');
            whiteSpan.className = 'move-white review-move';
            whiteSpan.textContent = whiteMove?.notation || '';
            whiteSpan.dataset.moveIndex = `${i + 1}`;

            const blackSpan = document.createElement('span');
            blackSpan.className = 'move-black review-move';
            blackSpan.textContent = blackMove?.notation || '';
            if (blackMove) {
                blackSpan.dataset.moveIndex = `${i + 2}`;
            } else {
                blackSpan.classList.add('empty');
            }

            row.appendChild(numSpan);
            row.appendChild(whiteSpan);
            row.appendChild(blackSpan);
            container.appendChild(row);
        }

        movesContainer.innerHTML = '';
        movesContainer.appendChild(container);

        container.addEventListener('click', (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const idx = target.dataset.moveIndex;
            if (!idx) return;
            const moveIndex = parseInt(idx, 10);
            if (Number.isNaN(moveIndex)) return;
            this.showMove(moveIndex);
        });

        this.highlightMove();
    }

    showMove(moveIndex) {
        if (!this.reviewStates.length) return;
        const clamped = Math.max(0, Math.min(this.reviewStates.length - 1, moveIndex));
        this.activeMoveIndex = clamped;
        this.updateBoard(this.reviewStates[clamped] || null);
        this.updateProgress();
        this.highlightMove();
    }

    highlightMove() {
        const moveEls = document.querySelectorAll('.review-move');
        moveEls.forEach((el) => {
            const idxRaw = el.dataset.moveIndex;
            if (!idxRaw) {
                el.classList.remove('active');
                return;
            }
            const idx = parseInt(idxRaw, 10);
            el.classList.toggle('active', idx === this.activeMoveIndex);
        });
    }

    updateProgress() {
        const progress = document.getElementById('review-progress');
        if (!progress) return;
        if (!this.reviewMoves.length) {
            progress.textContent = 'No game selected';
            return;
        }
        progress.textContent = this.activeMoveIndex === 0
            ? 'Start position'
            : `Move ${this.activeMoveIndex} / ${this.reviewMoves.length}`;
    }

    updateBoard(gameState) {
        if (!gameState || !gameState.board || !gameState.board.board) {
            return;
        }
        const board = gameState.board.board;
        document.querySelectorAll('.piece').forEach(piece => piece.remove());

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
    }

    createPieceElement(pieceData) {
        const piece = document.createElement('div');
        piece.className = `piece ${pieceData.color} ${pieceData.type}`;
        piece.dataset.pieceType = pieceData.type;
        piece.dataset.pieceColor = pieceData.color;
        piece.draggable = false;
        return piece;
    }

    showMessage(targetId, message) {
        const target = document.getElementById(targetId);
        if (target) {
            target.innerHTML = `<p class="no-moves">${message}</p>`;
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ReviewPage();
});
