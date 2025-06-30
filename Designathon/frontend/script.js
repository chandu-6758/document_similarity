// API Base URL
const API_BASE_URL = 'http://127.0.0.1:8000';

// Global variables
let currentView = 'arRequestor';
let currentUser = null;

// Check authentication on page load
document.addEventListener('DOMContentLoaded', function() {
    // If not authenticated and not on login page, redirect to login
    if (!isAuthenticated() && !window.location.pathname.includes('login.html')) {
        window.location.href = 'login.html';
        return;
    }
    // If on login page and authenticated, redirect to main
    if (window.location.pathname.includes('login.html') && isAuthenticated()) {
        window.location.href = 'index.html';
        return;
    }
    // If authenticated, update user info and show logout button
    if (isAuthenticated()) {
        updateUserInfo();
        // Show only the correct dashboard based on role
        const role = localStorage.getItem('role');
        if (role === 'recruiter') {
            document.getElementById('recruiterView').style.display = 'block';
            document.getElementById('arRequestorView').style.display = 'none';
            const arJDFormRow = document.getElementById('arRequestorJDFormRow');
            if (arJDFormRow) arJDFormRow.style.display = 'none';
        } else if (role === 'ar_requestor') {
            document.getElementById('arRequestorView').style.display = 'block';
            document.getElementById('recruiterView').style.display = 'none';
            const arJDFormRow = document.getElementById('arRequestorJDFormRow');
            if (arJDFormRow) arJDFormRow.style.display = '';
        }
    } else {
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) logoutBtn.style.display = 'none';
    }
    // If not on login page, check auth for dashboard
    if (!window.location.pathname.includes('login.html')) {
        checkAuth();
    }
});

// Authentication functions
function isAuthenticated() {
    return localStorage.getItem('token') !== null;
}

function getAuthHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
    };
}

async function checkAuth() {
    if (!isAuthenticated()) {
        window.location.href = 'login.html';
        return;
    }

    fetch(`${API_BASE_URL}/me`, {
        headers: getAuthHeaders()
    })
    .then(response => {
        if (!response.ok) {
            localStorage.removeItem('token');
            localStorage.removeItem('username');
            localStorage.removeItem('role');
            window.location.href = 'login.html';
            return;
        }
        return response.json();
    })
    .then(user => {
        currentUser = user;
        updateUserInfo();
        // Show only the correct dashboard
        if (currentUser.role === 'recruiter') {
            document.getElementById('recruiterView').style.display = 'block';
            document.getElementById('arRequestorView').style.display = 'none';
            // Hide AR Requestor JD form if present
            const arJDFormRow = document.getElementById('arRequestorJDFormRow');
            if (arJDFormRow) arJDFormRow.style.display = 'none';
            currentView = 'recruiter';
        } else if (currentUser.role === 'ar_requestor') {
            document.getElementById('arRequestorView').style.display = 'block';
            document.getElementById('recruiterView').style.display = 'none';
            // Show AR Requestor JD form if present
            const arJDFormRow = document.getElementById('arRequestorJDFormRow');
            if (arJDFormRow) arJDFormRow.style.display = '';
            currentView = 'arRequestor';
        }
        loadData();
        setInterval(loadData, 5000);
    })
    .catch(error => {
        console.error('Auth check failed:', error);
        localStorage.removeItem('token');
        localStorage.removeItem('username');
        localStorage.removeItem('role');
        window.location.href = 'login.html';
    });
}

function updateUserInfo() {
    // Remove any existing user info
    const navbar = document.getElementById('mainNavbarNav');
    if (!navbar) return;
    const existingUserInfo = navbar.querySelector('.nav-item.dropdown');
    if (existingUserInfo) navbar.removeChild(existingUserInfo);
    const username = localStorage.getItem('username');
    const logoutBtn = document.getElementById('logoutBtn');
    if (username) {
        const userInfo = document.createElement('li');
        userInfo.className = 'nav-item dropdown';
        userInfo.innerHTML = `
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                <i class="fas fa-user me-2"></i>${username}
            </a>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="#" onclick="logout()">
                    <i class="fas fa-sign-out-alt me-2"></i>Logout
                </a></li>
            </ul>
        `;
        navbar.appendChild(userInfo);
        if (logoutBtn) logoutBtn.style.display = '';
    } else {
        if (logoutBtn) logoutBtn.style.display = 'none';
    }
}

function logout() {
    // Remove user info from navbar
    const navbar = document.getElementById('mainNavbarNav');
    if (navbar) {
        const existingUserInfo = navbar.querySelector('.nav-item.dropdown');
        if (existingUserInfo) navbar.removeChild(existingUserInfo);
    }
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.style.display = 'none';
    window.location.href = 'login.html';
}

// View switching functions
function showARRequestorView() {
    if (currentUser && currentUser.role !== 'ar_requestor' && currentUser.role !== 'admin') {
        showAlert('Access denied. AR Requestor role required.', 'danger');
        return;
    }
    
    document.getElementById('arRequestorView').style.display = 'block';
    document.getElementById('recruiterView').style.display = 'none';
    currentView = 'arRequestor';
    loadData();
}

function showRecruiterView() {
    if (currentUser && currentUser.role !== 'recruiter' && currentUser.role !== 'admin') {
        showAlert('Access denied. Recruiter role required.', 'danger');
        return;
    }
    
    document.getElementById('arRequestorView').style.display = 'none';
    document.getElementById('recruiterView').style.display = 'block';
    currentView = 'recruiter';
    loadData();
}

// Load all data
async function loadData() {
    if (!isAuthenticated()) {
        return;
    }
    
    try {
        if (currentView === 'arRequestor') {
            await loadARRequestorData();
        } else {
            await loadRecruiterData();
        }
    } catch (error) {
        console.error('Error loading data:', error);
        if (error.message === 'Unauthorized' || error.status === 401) {
            logout();
        } else {
            showAlert('Error loading data. Please try again.', 'danger');
        }
    }
}

// Load AR Requestor data
async function loadARRequestorData() {
    // Load JDs and their matches
    const jds = await fetchAPI('/jds/');
    if (jds.length > 0) {
        const latestJD = jds[jds.length - 1];
        await loadMatchesForJD(latestJD.id);
        await loadWorkflowStatus(latestJD.id);
    }
}

// Load Recruiter data
async function loadRecruiterData() {
    await loadJDs();
    await loadConsultants();
    await loadMetrics();
}

// Load JDs for recruiter view
async function loadJDs() {
    try {
        const jds = await fetchAPI('/jds/');
        const tbody = document.getElementById('jdTableBody');
        tbody.innerHTML = '';
        
        jds.forEach(jd => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${jd.id}</td>
                <td>${jd.title}</td>
                <td>${jd.required_skills.substring(0, 50)}...</td>
                <td>${jd.experience_level}</td>
                <td><span class="badge bg-${getStatusColor(jd.status)}">${jd.status}</span></td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="viewMatches(${jd.id})">
                        <i class="fas fa-eye"></i> View Matches
                    </button>
                    <button class="btn btn-sm btn-success" onclick="triggerMatching(${jd.id})">
                        <i class="fas fa-play"></i> Match
                    </button>
                    <button class="btn btn-sm btn-warning" onclick="testWorkflow(${jd.id})">
                        <i class="fas fa-cogs"></i> Test Workflow
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteJD(${jd.id})">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading JDs:', error);
    }
}

// Load consultants for recruiter view
async function loadConsultants() {
    try {
        const consultants = await fetchAPI('/consultants/');
        const tbody = document.getElementById('consultantTableBody');
        tbody.innerHTML = '';
        
        consultants.forEach(consultant => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${consultant.id}</td>
                <td>${consultant.name}</td>
                <td>${consultant.email}</td>
                <td>${consultant.skills.substring(0, 50)}...</td>
                <td>${consultant.years_of_experience} years</td>
                <td><span class="badge bg-${consultant.availability ? 'success' : 'danger'}">${consultant.availability ? 'Available' : 'Unavailable'}</span></td>
                <td>
                    <button class="btn btn-sm btn-info" onclick="viewConsultant(${consultant.id})">
                        <i class="fas fa-eye"></i> View
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteConsultant(${consultant.id})">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading consultants:', error);
    }
}

// Load matches for a specific JD
async function loadMatchesForJD(jdId) {
    try {
        const response = await fetchAPI(`/matches/${jdId}`);
        const container = document.getElementById('topMatchesContainer');
        const actionsSection = document.getElementById('matchActionsSection');
        
        if (response.matches && response.matches.length > 0) {
            container.innerHTML = '';
            response.matches.slice(0, 3).forEach(match => {
                const matchCard = document.createElement('div');
                matchCard.className = 'match-card';
                matchCard.innerHTML = `
                    <div class="match-header">
                        <div class="match-rank">${match.rank}</div>
                        <div class="match-score">${(match.similarity_score * 100).toFixed(1)}% Match</div>
                    </div>
                    <div class="match-info">
                        <h6>${match.consultant.name}</h6>
                        <p><strong>Email:</strong> ${match.consultant.email}</p>
                        <p><strong>Skills:</strong> ${match.consultant.skills}</p>
                        <p><strong>Experience:</strong> ${match.consultant.years_of_experience} years</p>
                    </div>
                    <div class="match-actions">
                        <button class="btn btn-sm btn-outline-primary" onclick="selectConsultant(${match.consultant.id})">
                            <i class="fas fa-check"></i> Select
                        </button>
                        <button class="btn btn-sm btn-outline-info" onclick="viewConsultantDetails(${match.consultant.id})">
                            <i class="fas fa-eye"></i> Details
                        </button>
                    </div>
                `;
                container.appendChild(matchCard);
            });
            
            document.getElementById('topMatchesCount').textContent = `${response.matches.length} Found`;
            
            // Show actions section when matches are available
            actionsSection.style.display = 'block';
            
            // Load match history
            await loadMatchHistory();
            
        } else {
            container.innerHTML = `
                <div class="no-matches">
                    <i class="fas fa-search"></i>
                    <p>No matches found for this job description.</p>
                </div>
            `;
            document.getElementById('topMatchesCount').textContent = '0 Found';
            actionsSection.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading matches:', error);
    }
}

// Load workflow status
async function loadWorkflowStatus(jdId) {
    try {
        const status = await fetchAPI(`/workflow/${jdId}`);
        
        // Update status cards
        updateStatusCard('jdComparisonStatus', status.jd_comparison_status);
        updateStatusCard('profileRankingStatus', status.profile_ranking_status);
        updateStatusCard('emailSentStatus', status.email_sent_status);
        
        // Update progress steps
        updateProgressStep('jdComparisonStep', status.jd_comparison_status);
        updateProgressStep('rankingStep', status.profile_ranking_status);
        updateProgressStep('emailStep', status.email_sent_status);
        
    } catch (error) {
        console.error('Error loading workflow status:', error);
    }
}

// Load metrics
async function loadMetrics() {
    try {
        const jds = await fetchAPI('/jds/');
        const consultants = await fetchAPI('/consultants/');
        const emails = await fetchAPI('/emails/');
        
        document.getElementById('totalJDs').textContent = jds.length;
        document.getElementById('totalConsultants').textContent = consultants.length;
        document.getElementById('emailsSent').textContent = emails.filter(e => e.status === 'sent').length;
        
        // Calculate average processing time (mock data for now)
        document.getElementById('avgProcessingTime').textContent = '2.5s';
        
    } catch (error) {
        console.error('Error loading metrics:', error);
    }
}

// Update status card
function updateStatusCard(elementId, status) {
    const element = document.getElementById(elementId);
    const icon = element.parentElement.querySelector('.status-icon');
    
    element.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    
    icon.className = `status-icon ${status}`;
}

// Update progress step
function updateProgressStep(stepId, status) {
    const step = document.getElementById(stepId);
    if (status === 'completed') {
        step.classList.add('completed');
    } else if (status === 'pending') {
        step.classList.remove('completed', 'active');
    } else if (status === 'failed') {
        step.classList.add('failed');
    }
}

// Add JD
async function addJD() {
    const formData = {
        title: document.getElementById('jdTitle').value,
        description: document.getElementById('jdDescription').value,
        required_skills: document.getElementById('jdSkills').value,
        experience_level: document.getElementById('jdExperience').value
    };
    
    try {
        await fetchAPI('/jds/', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(formData)
        });
        
        showAlert('Job Description added successfully!', 'success');
        bootstrap.Modal.getInstance(document.getElementById('addJDModal')).hide();
        document.getElementById('addJDForm').reset();
        loadData();
        
    } catch (error) {
        console.error('Error adding JD:', error);
        showAlert('Error adding Job Description. Please try again.', 'danger');
    }
}

// Add Consultant
async function addConsultant() {
    const formData = {
        name: document.getElementById('consultantName').value,
        email: document.getElementById('consultantEmail').value,
        skills: document.getElementById('consultantSkills').value,
        experience: document.getElementById('consultantExperience').value,
        years_of_experience: parseInt(document.getElementById('consultantYears').value),
        availability: document.getElementById('consultantAvailability').checked
    };
    
    try {
        await fetchAPI('/consultants/', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(formData)
        });
        
        showAlert('Consultant added successfully!', 'success');
        bootstrap.Modal.getInstance(document.getElementById('addConsultantModal')).hide();
        document.getElementById('addConsultantForm').reset();
        loadData();
        
    } catch (error) {
        console.error('Error adding consultant:', error);
        showAlert('Error adding consultant. Please try again.', 'danger');
    }
}

// Trigger matching for a JD
async function triggerMatching(jdId) {
    try {
        const response = await fetchAPI('/match/', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ job_description_id: jdId })
        });
        
        showAlert(`Matching completed! Found ${response.matches.length} matches.`, 'success');
        loadData();
        
    } catch (error) {
        console.error('Error triggering matching:', error);
        showAlert('Error triggering matching. Please try again.', 'danger');
    }
}

// View matches for a JD
async function viewMatches(jdId) {
    try {
        const response = await fetchAPI(`/matches/${jdId}`);
        const content = document.getElementById('matchesModalContent');
        
        if (response.matches && response.matches.length > 0) {
            content.innerHTML = `
                <h6>Matches for: ${response.job_description.title}</h6>
                <div class="row">
                    ${response.matches.map(match => `
                        <div class="col-md-6 mb-3">
                            <div class="match-card">
                                <div class="match-header">
                                    <div class="match-rank">${match.rank}</div>
                                    <div class="match-score">${(match.similarity_score * 100).toFixed(1)}% Match</div>
                                </div>
                                <div class="match-info">
                                    <h6>${match.consultant.name}</h6>
                                    <p><strong>Email:</strong> ${match.consultant.email}</p>
                                    <p><strong>Skills:</strong> ${match.consultant.skills}</p>
                                    <p><strong>Experience:</strong> ${match.consultant.years_of_experience} years</p>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            content.innerHTML = `
                <div class="text-center text-muted">
                    <i class="fas fa-search fa-3x mb-3"></i>
                    <p>No matches found for this job description.</p>
                </div>
            `;
        }
        
        new bootstrap.Modal(document.getElementById('viewMatchesModal')).show();
        
    } catch (error) {
        console.error('Error viewing matches:', error);
        showAlert('Error loading matches. Please try again.', 'danger');
    }
}

// Modal functions
function showAddJDModal() {
    if (currentUser && currentUser.role === 'ar_requestor') {
        new bootstrap.Modal(document.getElementById('addJDModal')).show();
    }
}

function showAddConsultantModal() {
    if (currentUser && currentUser.role === 'recruiter') {
        new bootstrap.Modal(document.getElementById('addConsultantModal')).show();
    }
}

// Utility functions
function getStatusColor(status) {
    switch (status) {
        case 'completed': return 'success';
        case 'pending': return 'warning';
        case 'failed': return 'danger';
        default: return 'secondary';
    }
}

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.querySelector('.container').insertBefore(alertDiv, document.querySelector('.container').firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Generic API fetch function
async function fetchAPI(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const defaultOptions = {
        method: 'GET',
        headers: getAuthHeaders(),
    };
    
    const finalOptions = { ...defaultOptions, ...options };
    
    const response = await fetch(url, finalOptions);
    
    if (!response.ok) {
        if (response.status === 401) {
            throw new Error('Unauthorized');
        }
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
}

// View consultant details
async function viewConsultant(consultantId) {
    try {
        const consultant = await fetchAPI(`/consultants/${consultantId}`);
        const content = document.getElementById('consultantModalContent');
        
        content.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Personal Information</h6>
                    <table class="table table-borderless">
                        <tr>
                            <td><strong>Name:</strong></td>
                            <td>${consultant.name}</td>
                        </tr>
                        <tr>
                            <td><strong>Email:</strong></td>
                            <td>${consultant.email}</td>
                        </tr>
                        <tr>
                            <td><strong>Years of Experience:</strong></td>
                            <td>${consultant.years_of_experience} years</td>
                        </tr>
                        <tr>
                            <td><strong>Availability:</strong></td>
                            <td><span class="badge bg-${consultant.availability ? 'success' : 'danger'}">${consultant.availability ? 'Available' : 'Unavailable'}</span></td>
                        </tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>Skills & Experience</h6>
                    <div class="mb-3">
                        <strong>Skills:</strong>
                        <p class="mt-2">${consultant.skills}</p>
                    </div>
                    <div class="mb-3">
                        <strong>Experience:</strong>
                        <p class="mt-2">${consultant.experience}</p>
                    </div>
                </div>
            </div>
            <div class="row mt-3">
                <div class="col-12">
                    <h6>Match History</h6>
                    <div id="consultantMatchHistory">
                        <p class="text-muted">Loading match history...</p>
                    </div>
                </div>
            </div>
        `;
        
        // Load match history for this consultant
        try {
            const matches = await fetchAPI(`/consultants/${consultantId}/matches`);
            const historyDiv = document.getElementById('consultantMatchHistory');
            
            if (matches && matches.length > 0) {
                historyDiv.innerHTML = `
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>Job Description</th>
                                    <th>Match Score</th>
                                    <th>Rank</th>
                                    <th>Date</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${matches.map(match => `
                                    <tr>
                                        <td>${match.job_description.title}</td>
                                        <td>${(match.similarity_score * 100).toFixed(1)}%</td>
                                        <td>${match.rank}</td>
                                        <td>${new Date(match.created_at).toLocaleDateString()}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            } else {
                historyDiv.innerHTML = '<p class="text-muted">No match history found.</p>';
            }
        } catch (error) {
            document.getElementById('consultantMatchHistory').innerHTML = '<p class="text-muted">Unable to load match history.</p>';
        }
        
        new bootstrap.Modal(document.getElementById('viewConsultantModal')).show();
        
    } catch (error) {
        console.error('Error viewing consultant:', error);
        showAlert('Error loading consultant details. Please try again.', 'danger');
    }
}

// AR Requestor Action Functions
let selectedConsultants = new Set();

function selectConsultant(consultantId) {
    if (selectedConsultants.has(consultantId)) {
        selectedConsultants.delete(consultantId);
    } else {
        selectedConsultants.add(consultantId);
    }
    updateSelectionUI();
}

function updateSelectionUI() {
    // Update UI to show selected consultants
    const buttons = document.querySelectorAll('.match-actions .btn-outline-primary');
    buttons.forEach(button => {
        const consultantId = parseInt(button.getAttribute('onclick').match(/\d+/)[0]);
        if (selectedConsultants.has(consultantId)) {
            button.classList.remove('btn-outline-primary');
            button.classList.add('btn-primary');
            button.innerHTML = '<i class="fas fa-check"></i> Selected';
        } else {
            button.classList.remove('btn-primary');
            button.classList.add('btn-outline-primary');
            button.innerHTML = '<i class="fas fa-check"></i> Select';
        }
    });
}

async function approveMatches() {
    if (selectedConsultants.size === 0) {
        showAlert('Please select at least one consultant to approve.', 'warning');
        return;
    }
    
    try {
        const response = await fetchAPI('/ar-requestor/approve-matches', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                consultant_ids: Array.from(selectedConsultants),
                action: 'approve'
            })
        });
        
        showAlert('Matches approved successfully! Recruiter will be notified.', 'success');
        selectedConsultants.clear();
        updateSelectionUI();
        
    } catch (error) {
        console.error('Error approving matches:', error);
        showAlert('Error approving matches. Please try again.', 'danger');
    }
}

async function requestMoreCandidates() {
    try {
        const response = await fetchAPI('/ar-requestor/request-more-candidates', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                reason: 'Need more candidates',
                additional_requirements: ''
            })
        });
        
        showAlert('Request for more candidates sent to recruiter.', 'success');
        
    } catch (error) {
        console.error('Error requesting more candidates:', error);
        showAlert('Error sending request. Please try again.', 'danger');
    }
}

async function rejectMatches() {
    if (!confirm('Are you sure you want to reject all matches? This will notify the recruiter to find new candidates.')) {
        return;
    }
    
    try {
        const response = await fetchAPI('/ar-requestor/reject-matches', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                reason: 'Matches do not meet requirements'
            })
        });
        
        showAlert('Matches rejected. Recruiter will be notified to find new candidates.', 'success');
        selectedConsultants.clear();
        updateSelectionUI();
        
    } catch (error) {
        console.error('Error rejecting matches:', error);
        showAlert('Error rejecting matches. Please try again.', 'danger');
    }
}

async function contactConsultants() {
    if (selectedConsultants.size === 0) {
        showAlert('Please select consultants to contact.', 'warning');
        return;
    }
    
    // Show contact modal
    const modal = new bootstrap.Modal(document.getElementById('contactConsultantsModal'));
    modal.show();
}

async function scheduleInterviews() {
    if (selectedConsultants.size === 0) {
        showAlert('Please select consultants to schedule interviews.', 'warning');
        return;
    }
    
    // Show interview scheduling modal
    const modal = new bootstrap.Modal(document.getElementById('scheduleInterviewsModal'));
    modal.show();
}

async function exportMatches() {
    try {
        const response = await fetchAPI('/ar-requestor/export-matches', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                format: 'pdf'
            })
        });
        
        // Create download link
        const blob = new Blob([JSON.stringify(response, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'match-report.json';
        a.click();
        window.URL.revokeObjectURL(url);
        
        showAlert('Match report exported successfully!', 'success');
        
    } catch (error) {
        console.error('Error exporting matches:', error);
        showAlert('Error exporting matches. Please try again.', 'danger');
    }
}

async function loadMatchHistory() {
    try {
        const history = await fetchAPI('/ar-requestor/match-history');
        const container = document.getElementById('matchHistoryContainer');
        
        if (history && history.length > 0) {
            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Job Description</th>
                                <th>Matches Found</th>
                                <th>Status</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${history.map(item => `
                                <tr>
                                    <td>${new Date(item.created_at).toLocaleDateString()}</td>
                                    <td>${item.job_description.title}</td>
                                    <td>${item.matches_count}</td>
                                    <td><span class="badge bg-${getStatusColor(item.status)}">${item.status}</span></td>
                                    <td>
                                        <button class="btn btn-sm btn-outline-primary" onclick="viewHistoricalMatches(${item.job_description_id})">
                                            View
                                        </button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        } else {
            container.innerHTML = '<p class="text-muted">No match history found.</p>';
        }
    } catch (error) {
        console.error('Error loading match history:', error);
        document.getElementById('matchHistoryContainer').innerHTML = '<p class="text-muted">Unable to load match history.</p>';
    }
}

function viewConsultantDetails(consultantId) {
    // Reuse the existing viewConsultant function
    viewConsultant(consultantId);
}

function viewHistoricalMatches(jdId) {
    // Load and display historical matches
    loadMatchesForJD(jdId);
}

// Test workflow function
async function testWorkflow(jdId) {
    try {
        showAlert('Starting workflow test...', 'info');
        
        const response = await fetchAPI(`/test/workflow/${jdId}`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        showAlert(`