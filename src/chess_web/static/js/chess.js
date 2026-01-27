// Chess game client-side logic

class ChessGame {
    constructor() {
        this.selectedSquare = null;
        this.selectedPiece = null;
        this.legalMoves = [];
        this.draggingFrom = null;
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

        // Initialize from DOM data attributes
        const board = document.getElementById('chessboard');
        this.currentTurn = board?.dataset.currentTurn || 'white';
        this.gameOver = board?.dataset.gameOver === 'true';
        this.debugEnabled = board?.dataset.debug === 'true';
        this.debugLog = [];
        this.debugOverlay = null;

        this.initializeEventListeners();

        // Fetch latest game state to ensure sync
        this.syncGameState();
    }

    async syncGameState() {
        try {
            const version = ++this.stateVersion;
            this.debug('syncGameState:start', { version });
            const response = await fetch('/game-state', { cache: 'no-store' });
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

        // Mouse-based drag events (event delegation)
        const board = document.getElementById('chessboard');
        if (board) {
            board.style.touchAction = 'none';
            board.addEventListener('mousedown', (e) => this.handlePointerDown(e));
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
    }

    async handleSquareClick(event) {
        if (this.suppressClick) {
            this.suppressClick = false;
            return;
        }
        if (this.gameOver || this.isBusy) {
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
            const response = await fetch('/legal-moves', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
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
            const response = await fetch('/move', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
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
                // Update the board
                this.updateBoard(data.game_state);
                this.updateGameStatus(data);

                // Check if game is over
                if (data.game_over) {
                    this.gameOver = true;
                    this.showGameOverModal(data);
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
            const response = await fetch('/ai-move', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
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
        piece.className = `piece ${pieceData.color}`;
        piece.dataset.pieceType = pieceData.type;
        piece.dataset.pieceColor = pieceData.color;
        piece.draggable = false;

        // Unicode symbols for pieces
        const symbols = {
            'pawn': { 'white': '♙', 'black': '♟' },
            'rook': { 'white': '♖', 'black': '♜' },
            'knight': { 'white': '♘', 'black': '♞' },
            'bishop': { 'white': '♗', 'black': '♝' },
            'queen': { 'white': '♕', 'black': '♛' },
            'king': { 'white': '♔', 'black': '♚' },
        };

        piece.textContent = symbols[pieceData.type][pieceData.color];
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
            moveHistoryDiv.innerHTML = '<p class="no-moves">No moves yet</p>';
        } else {
            const ol = document.createElement('ol');
            ol.start = 1;

            // Pair moves: white and black together
            for (let i = 0; i < moveHistory.length; i += 2) {
                const li = document.createElement('li');
                const whiteMove = moveHistory[i].notation;
                const blackMove = i + 1 < moveHistory.length ? moveHistory[i + 1].notation : '';

                if (blackMove) {
                    li.textContent = `${whiteMove}  ${blackMove}`;
                } else {
                    li.textContent = whiteMove;
                }
                ol.appendChild(li);
            }

            moveHistoryDiv.innerHTML = '';
            moveHistoryDiv.appendChild(ol);

            // Scroll to bottom
            moveHistoryDiv.scrollTop = moveHistoryDiv.scrollHeight;
        }
    }

    updateCapturedPieces(capturedPieces) {
        // This is a simplified version - ideally would show actual piece symbols
        // For now, the server-side rendering handles this better
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
            this.stateVersion += 1;
            this.gameId = null;
            this.debug('newGame:request', {});
            const response = await fetch('/new-game', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            const data = await response.json();
            this.debug('newGame:response', {
                ok: data.success,
                game_id: data.game_state?.game_id,
                moves: data.game_state?.move_history?.length
            });

            if (data.success) {
                this.gameOver = false;
                this.updateBoard(data.game_state);
                this.updateGameStatus({
                    message: data.message || "New game started",
                    in_check: false,
                });
                this.updateMoveHistory([]);
                this.hideGameOverModal();
                this.deselectSquare();
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
            const response = await fetch('/resign', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    color: this.currentTurn,
                }),
            });

            const data = await response.json();

            if (data.success) {
                this.gameOver = true;
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

    handlePointerDown(event) {
        if (event.button !== 0 || this.gameOver || this.isBusy) {
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

        const square = piece.parentElement;
        const row = parseInt(square.dataset.row);
        const col = parseInt(square.dataset.col);

        this.debug('drag:start', { row, col, type: event.type });
        this.dragActive = true;
        this.dragMoved = false;
        this.dragStart = { x: event.clientX, y: event.clientY };
        this.draggingFrom = [row, col];
        this.dragSymbol = piece.textContent;

        this.pointerMoveHandler = (e) => this.handlePointerMove(e);
        this.pointerUpHandler = (e) => this.handlePointerUp(e);
        document.addEventListener('mousemove', this.pointerMoveHandler);
        document.addEventListener('mouseup', this.pointerUpHandler);
    }

    handlePointerMove(event) {
        if (!this.dragActive || this.isBusy) {
            return;
        }

        if (!this.dragMoved) {
            const dx = event.clientX - this.dragStart.x;
            const dy = event.clientY - this.dragStart.y;
            if ((dx * dx) + (dy * dy) < 16) {
                return;
            }
            this.dragMoved = true;
            this.suppressClick = true;
            this.createDragGhost(this.dragSymbol);
            if (this.draggingFrom) {
                const [row, col] = this.draggingFrom;
                const fromSquare = document.querySelector(
                    `.square[data-row="${row}"][data-col="${col}"]`
                );
                this.deselectSquare();
                if (fromSquare) {
                    this.selectedSquare = [row, col];
                    fromSquare.classList.add('selected');
                }
                this.fetchLegalMoves(row, col, true);
            }
        }
        if (this.dragMoved) {
            this.moveDragGhost(event.clientX, event.clientY);
        }

        const square = document.elementFromPoint(event.clientX, event.clientY)?.closest('.square');
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

        document.removeEventListener('mousemove', this.pointerMoveHandler);
        document.removeEventListener('mouseup', this.pointerUpHandler);
        this.pointerMoveHandler = null;
        this.pointerUpHandler = null;

        const square = document.elementFromPoint(event.clientX, event.clientY)?.closest('.square');
        if (!this.dragMoved) {
            this.dragActive = false;
            this.dragStart = null;
            this.draggingFrom = null;
            this.dragSymbol = null;
            this.clearDragGhost();
            return;
        }
        this.debug('drag:drop', {
            to: square ? [parseInt(square.dataset.row), parseInt(square.dataset.col)] : null
        });
        if (square && this.draggingFrom) {
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
        this.clearDragGhost();
        this.clearDragOver();
        this.deselectSquare();
    }

    createDragGhost(symbol) {
        if (!symbol) {
            return;
        }
        this.clearDragGhost();
        const ghost = document.createElement('div');
        ghost.className = 'drag-ghost';
        ghost.textContent = symbol;
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
