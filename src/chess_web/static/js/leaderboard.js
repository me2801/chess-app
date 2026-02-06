// Leaderboard page logic

class LeaderboardPage {
    constructor() {
        const baseMeta = document.querySelector('meta[name="base-url"]');
        this.baseUrl = baseMeta ? baseMeta.content.replace(/\/$/, '') : '';
        this.initTheme();
        this.loadLeaderboard();
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

    async loadLeaderboard() {
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
}

document.addEventListener('DOMContentLoaded', () => {
    new LeaderboardPage();
});
