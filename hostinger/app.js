/**
 * JC Algos Signal - Frontend Application
 * Trading Signal Analysis Platform
 */

// API Configuration
const API_BASE = 'https://signal.srv1295571.hstgr.cloud';

// State Management
let state = {
    isAuthenticated: false,
    email: '',
    token: '',
    signals: [],
    statistics: {},
    currentExchange: 'HKEX'
};

// DOM Elements
const elements = {
    app: document.getElementById('app'),
    userEmail: document.getElementById('userEmail'),
    logoutBtn: document.getElementById('logoutBtn'),
    exchangeSelect: document.getElementById('exchangeSelect'),
    daysAgo: document.getElementById('daysAgo'),
    fromDate: document.getElementById('fromDate'),
    toDate: document.getElementById('toDate'),
    daysInput: document.getElementById('daysInput'),
    dateRangeInput: document.getElementById('dateRangeInput'),
    sortBySentiment: document.getElementById('sortBySentiment'),
    sortByPL: document.getElementById('sortByPL'),
    plSortOrder: document.getElementById('plSortOrder'),
    plSortSelect: document.getElementById('plSortSelect'),
    fetchBtn: document.getElementById('fetchBtn'),
    exportBtn: document.getElementById('exportBtn'),
    loading: document.getElementById('loading'),
    statsSection: document.getElementById('statsSection'),
    signalsSection: document.getElementById('signalsSection'),
    emptyState: document.getElementById('emptyState'),
    signalsTableBody: document.getElementById('signalsTableBody'),
    historyTableBody: document.getElementById('historyTableBody'),
    historyEmpty: document.getElementById('historyEmpty'),
    historyExchange: document.getElementById('historyExchange')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initializeDates();
    checkAuth();
    setupEventListeners();
});

// Initialize default dates
function initializeDates() {
    const today = new Date();
    const lastWeek = new Date(today);
    lastWeek.setDate(lastWeek.getDate() - 7);
    
    elements.toDate.value = formatDate(today);
    elements.fromDate.value = formatDate(lastWeek);
}

// Format date for input
function formatDate(date) {
    return date.toISOString().split('T')[0];
}

// Check authentication via Supabase (shared with main site)
async function checkAuth() {
    // Try Supabase session first
    if (window.SupabaseAuth) {
        try {
            const { data: { session } } = await window.supabaseClient.auth.getSession();
            if (session) {
                state.isAuthenticated = true;
                state.email = session.user.email;
            }
        } catch(e) {
            console.log('Supabase check failed:', e);
        }
    }
    // Always show the app — auth is handled by the main site
    showApp();
}

// Show main application
function showApp() {
    elements.app.style.display = 'block';
    elements.userEmail.textContent = state.email;
    loadHistory();
}

// Setup event listeners
function setupEventListeners() {
    // Logout
    if (elements.logoutBtn) {
        elements.logoutBtn.addEventListener('click', handleLogout);
    }
    
    // Date method toggle
    document.querySelectorAll('input[name="dateMethod"]').forEach(radio => {
        radio.addEventListener('change', handleDateMethodChange);
    });
    
    // Sort by P/L toggle
    elements.sortByPL.addEventListener('change', () => {
        elements.plSortOrder.style.display = elements.sortByPL.checked ? 'block' : 'none';
    });
    
    // Exchange change
    elements.exchangeSelect.addEventListener('change', () => {
        state.currentExchange = elements.exchangeSelect.value;
        elements.historyExchange.textContent = state.currentExchange;
        loadHistory();
    });
    
    // Fetch signals
    elements.fetchBtn.addEventListener('click', fetchSignals);
    
    // Export
    elements.exportBtn.addEventListener('click', exportSignals);
    
    // Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', handleTabClick);
    });
}

// Handle login
async function handleLogin(e) {
    e.preventDefault();
    
    const email = elements.emailInput.value.trim();
    elements.loginError.style.display = 'none';
    
    try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        
        const data = await response.json();
        
        if (data.success) {
            state.isAuthenticated = true;
            state.email = data.email;
            state.token = data.token;
            
            localStorage.setItem('jc_algos_email', data.email);
            localStorage.setItem('jc_algos_token', data.token);
            
            showApp();
        } else {
            showLoginError(data.error || 'Login failed');
        }
    } catch (error) {
        showLoginError('Connection error. Please try again.');
        console.error('Login error:', error);
    }
}

// Show login error
function showLoginError(message) {
    elements.loginError.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    elements.loginError.style.display = 'flex';
}

// Handle logout
async function handleLogout() {
    state.isAuthenticated = false;
    state.email = '';
    state.token = '';
    
    localStorage.removeItem('jc_algos_email');
    localStorage.removeItem('jc_algos_token');
    
    if (window.SupabaseAuth) {
        await window.SupabaseAuth.signOut();
    } else {
        window.location.href = 'index.html';
    }
}

// Handle date method change
function handleDateMethodChange(e) {
    const method = e.target.value;
    elements.daysInput.style.display = method === 'days' ? 'block' : 'none';
    elements.dateRangeInput.style.display = method === 'custom' ? 'block' : 'none';
}

// Handle tab click
function handleTabClick(e) {
    const tab = e.currentTarget.dataset.tab;
    
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    e.currentTarget.classList.add('active');
    document.getElementById(`${tab}Tab`).classList.add('active');
    
    if (tab === 'history') {
        loadHistory();
    }
}

// Fetch signals from API
async function fetchSignals() {
    const exchange = elements.exchangeSelect.value;
    const dateMethod = document.querySelector('input[name="dateMethod"]:checked').value;
    
    let params = { exchange };
    
    if (dateMethod === 'days') {
        params.days_ago = parseInt(elements.daysAgo.value);
    } else {
        params.from_date = elements.fromDate.value;
        params.to_date = elements.toDate.value;
    }
    
    showLoading(true);
    hideResults();
    
    try {
        const response = await fetch(`${API_BASE}/api/signals/fetch`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify(params)
        });
        
        const data = await response.json();
        
        if (data.success) {
            state.signals = data.signals;
            state.statistics = data.statistics;
            
            if (data.signals.length > 0) {
                displayStatistics(data.statistics);
                displaySignals(data.signals);
            } else {
                showEmptyState('No signals found for the specified criteria');
            }
        } else {
            showEmptyState(data.error || 'Failed to fetch signals');
        }
    } catch (error) {
        console.error('Fetch error:', error);
        showEmptyState('Connection error. Please try again.');
    } finally {
        showLoading(false);
    }
}

// Show/hide loading
function showLoading(show) {
    elements.loading.style.display = show ? 'block' : 'none';
}

// Hide results
function hideResults() {
    elements.statsSection.style.display = 'none';
    elements.signalsSection.style.display = 'none';
    elements.emptyState.style.display = 'none';
}

// Show empty state
function showEmptyState(message) {
    elements.emptyState.querySelector('p').textContent = message;
    elements.emptyState.style.display = 'block';
}

// Display statistics
function displayStatistics(stats) {
    document.getElementById('buySignals').textContent = stats.buy_signals;
    document.getElementById('sellSignals').textContent = stats.sell_signals;
    document.getElementById('validBuySignals').textContent = stats.valid_buy_signals;
    document.getElementById('validSellSignals').textContent = stats.valid_sell_signals;
    
    document.getElementById('initialRatio').textContent = 
        `${stats.buy_signals} 好 : ${stats.sell_signals} 淡`;
    document.getElementById('actualRatio').textContent = 
        `${stats.valid_buy_signals} 好 : ${stats.valid_sell_signals} 淡`;
    document.getElementById('bullishStrength').textContent = 
        `${stats.buy_signals} 好 : ${stats.valid_buy_signals} 有效 (${stats.bullish_pct}%)`;
    document.getElementById('bearishStrength').textContent = 
        `${stats.sell_signals} 淡 : ${stats.valid_sell_signals} 有效 (${stats.bearish_pct}%)`;
    
    elements.statsSection.style.display = 'block';
}

// Display signals in table
function displaySignals(signals) {
    let sortedSignals = [...signals];
    
    // Apply sorting
    if (elements.sortBySentiment.checked) {
        sortedSignals.sort((a, b) => {
            if (a.sentiment === '好' && b.sentiment !== '好') return -1;
            if (a.sentiment !== '好' && b.sentiment === '好') return 1;
            return 0;
        });
    }
    
    if (elements.sortByPL.checked) {
        const ascending = elements.plSortSelect.value === 'asc';
        sortedSignals.sort((a, b) => {
            const plA = parseFloat(a.pl_percent) || -Infinity;
            const plB = parseFloat(b.pl_percent) || -Infinity;
            return ascending ? plA - plB : plB - plA;
        });
    }
    
    // Build table rows
    const tbody = elements.signalsTableBody;
    tbody.innerHTML = '';
    
    sortedSignals.forEach(signal => {
        const row = document.createElement('tr');
        
        const sentimentClass = signal.sentiment === '好' ? 'bullish' : 'bearish';
        const validClass = signal.valid_signal === 'Yes' ? 'yes' : 'no';
        const plValue = parseFloat(signal.pl_percent);
        const plClass = plValue > 0 ? 'pl-positive' : plValue < 0 ? 'pl-negative' : '';
        
        row.innerHTML = `
            <td><strong>${signal.ticker_symbol}</strong></td>
            <td><span class="sentiment-badge ${sentimentClass}">${signal.sentiment}</span></td>
            <td>${signal.trigger_price}</td>
            <td>${signal.stop_price}</td>
            <td>${signal.resistance1}</td>
            <td>${signal.resistance2}</td>
            <td>${signal.resistance3}</td>
            <td>${signal.date}</td>
            <td>${signal.strategy}</td>
            <td>${signal.trigger_day_close}</td>
            <td>${signal.present_close}</td>
            <td class="${plClass}">${signal.pl_percent ? signal.pl_percent + '%' : ''}</td>
            <td><span class="valid-badge ${validClass}">${signal.valid_signal}</span></td>
        `;
        
        tbody.appendChild(row);
    });
    
    elements.signalsSection.style.display = 'block';
}

// Load signal history
async function loadHistory() {
    const exchange = elements.exchangeSelect.value;
    elements.historyExchange.textContent = exchange;
    
    try {
        const response = await fetch(`${API_BASE}/api/signals/history/${exchange}`);
        const data = await response.json();
        
        if (data.success && data.history.length > 0) {
            displayHistory(data.history);
            elements.historyEmpty.style.display = 'none';
        } else {
            elements.historyTableBody.innerHTML = '';
            elements.historyEmpty.style.display = 'block';
        }
    } catch (error) {
        console.error('History fetch error:', error);
        elements.historyEmpty.style.display = 'block';
    }
}

// Display history
function displayHistory(history) {
    const tbody = elements.historyTableBody;
    tbody.innerHTML = '';
    
    history.forEach(item => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${item.date}</td>
            <td>${item.buy_signals}</td>
            <td>${item.valid_buy_signals}</td>
            <td>${item.sell_signals}</td>
            <td>${item.valid_sell_signals}</td>
            <td>${item.initial_ratio}</td>
            <td>${item.actual_ratio}</td>
            <td class="pl-positive">${item.bullish_strength}</td>
            <td class="pl-negative">${item.bearish_strength}</td>
        `;
        tbody.appendChild(row);
    });
}

// Export signals to CSV
async function exportSignals() {
    if (state.signals.length === 0) {
        alert('No signals to export');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/signals/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ signals: state.signals })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Create download
            const blob = new Blob([data.csv], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = data.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        }
    } catch (error) {
        console.error('Export error:', error);
        alert('Failed to export signals');
    }
}
