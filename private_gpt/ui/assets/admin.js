document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    const docMgmtStatus = document.getElementById('doc-mgmt-status');
    const docTableBody = document.querySelector('#document-management-table tbody');

    // User Management Elements
    const createUserForm = document.getElementById('create-user-form');
    const newUsernameInput = document.getElementById('new-username');
    const newPasswordInput = document.getElementById('new-password');
    const newUserRoleSelect = document.getElementById('new-user-role');
    const newUserTeamSelect = document.getElementById('new-user-team');
    const createUserStatus = document.getElementById('create-user-status');
    const userList = document.getElementById('user-list');

    let allTeams = [];

    // --- Utility Functions ---
    function showStatus(message, type = 'info', element = docMgmtStatus) {
        if (!element) return;
        element.textContent = message;
        element.className = `upload-status ${type}`;
        element.style.display = 'block';
        if (type !== 'loading') {
            setTimeout(() => { element.style.display = 'none'; }, 3000);
        }
    }

    // --- UI & Theme Logic ---
    function manageTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        if (savedTheme === 'dark') document.body.classList.add('dark');
        
        const themeToggleBtn = document.getElementById('theme-toggle-btn');
        if (themeToggleBtn) {
            themeToggleBtn.addEventListener('click', () => {
                document.body.classList.toggle('dark');
                localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
            });
        }
    }

    // --- Profile Dropdown Logic ---
    function setupProfileDropdown() {
        const profileBtn = document.getElementById('profile-btn');
        const profileDropdown = document.getElementById('profile-dropdown');
        const profileUsername = document.getElementById('profile-username');
        const profileRole = document.getElementById('profile-role');

        if (!profileBtn || !profileDropdown) return;

        // Fetch user info to populate dropdown
        fetch('/api/user/info').then(response => {
            if (response.ok) return response.json();
            throw new Error('Failed to fetch user info');
        }).then(data => {
            if (profileUsername) profileUsername.textContent = data.display_name || data.username;
            if (profileRole) {
                profileRole.textContent = data.role;
                profileRole.className = `user-role ${data.role}`;
            }
        }).catch(error => console.error("Error populating profile:", error));
        
        // Toggle dropdown visibility
        profileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            profileDropdown.classList.toggle('show');
        });

        // Close dropdown if clicking outside
        window.addEventListener('click', (e) => {
            if (!profileDropdown.contains(e.target) && !profileBtn.contains(e.target)) {
                profileDropdown.classList.remove('show');
            }
        });
    }

    // --- Tab Switching Logic ---
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            button.classList.add('active');
            const tabId = button.dataset.tab;
            document.getElementById(tabId).classList.add('active');
        });
    });

    // --- Document Management Logic ---
    async function fetchAllTeams() {
        try {
            const response = await fetch('/api/admin/teams');
            if (!response.ok) throw new Error('Failed to fetch teams');
            allTeams = await response.json();
            populateTeamsDropdown(newUserTeamSelect, allTeams);
        } catch (error) {
            console.error('Error fetching teams:', error);
            showStatus('Could not load team data.', 'error');
            allTeams = ['Default']; // Fallback
            populateTeamsDropdown(newUserTeamSelect, allTeams);
        }
    }

    async function fetchDocumentsAndPermissions() {
        try {
            const response = await fetch('/api/admin/documents/permissions');
            if (!response.ok) throw new Error('Failed to fetch document permissions');
            const documents = await response.json();
            renderDocumentTable(documents);
        } catch (error) {
            console.error('Error fetching documents:', error);
            showStatus('Could not load document permissions.', 'error');
        }
    }

    function renderDocumentTable(documents) {
        if (!docTableBody) return;
        docTableBody.innerHTML = '';
        documents.forEach(doc => {
            const row = document.createElement('tr');
            row.dataset.docId = doc.doc_id;

            const selectId = `teams-select-${doc.doc_id}`;
            const teamsSelectHtml = `
                <select id="${selectId}" class="textbox team-select" multiple>
                    ${allTeams.map(team => `
                        <option value="${team}" ${doc.teams.includes(team) ? 'selected' : ''}>
                            ${team}
                        </option>
                    `).join('')}
                </select>`;

            row.innerHTML = `
                <td>${doc.file_name}</td>
                <td>${teamsSelectHtml}</td>
                <td>
                    <button class="save-btn" data-doc-id="${doc.doc_id}">Save</button>
                </td>
            `;
            docTableBody.appendChild(row);
        });
    }

    async function handleSavePermissions(docId) {
        const selectElement = document.getElementById(`teams-select-${docId}`);
        const selectedTeams = Array.from(selectElement.selectedOptions).map(opt => opt.value);

        showStatus('Saving...', 'loading');
        try {
            const response = await fetch('/api/admin/documents/permissions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ doc_id: docId, teams: selectedTeams }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to save permissions');
            }
            showStatus('Permissions updated successfully!', 'success');
        } catch (error) {
            console.error('Error saving permissions:', error);
            showStatus(error.message, 'error');
        }
    }

    // --- User Management Logic ---
    function populateTeamsDropdown(selectElement, teams) {
        if (!selectElement) return;
        selectElement.innerHTML = '';
        teams.forEach(team => {
            const option = document.createElement('option');
            option.value = team;
            option.textContent = team;
            selectElement.appendChild(option);
        });
    }

    async function refreshUserList() {
        if (!userList) return;
        try {
            const response = await fetch('/api/admin/users');
            if (!response.ok) throw new Error(`Failed to fetch users: ${response.statusText}`);
            const users = await response.json();
            userList.innerHTML = '';
            users.forEach(user => {
                const li = document.createElement('li');
                const isDeletable = user.username !== 'admin';

                li.innerHTML = `
                    <div class="user-details-container">
                        <div class="user-info">
                            <span>${user.username}</span>
                            <span class="user-team">${user.team || 'No Team'}</span>
                        </div>
                        <span class="user-role ${user.role}">${user.role}</span>
                    </div>
                    <button class="delete-user-btn" data-username="${user.username}" title="Delete User" ${!isDeletable ? 'disabled' : ''}>
                        <svg width="16" height="16" viewBox="0_0_24_24"><path fill="currentColor" d="M9,3V4H4V6H5V19A2,2_0_0,0_7,21H17A2,2_0_0,0_19,19V6H20V4H15V3H9M7,6H17V19H7V6M9,8V17H11V8H9M13,8V17H15V8H13Z"/></svg>
                    </button>
                `;
                userList.appendChild(li);
            });
        } catch (error) {
            console.error('Error refreshing user list:', error);
            showStatus('Could not load user list', 'error', createUserStatus);
        }
    }

    async function handleCreateUser(event) {
        event.preventDefault();
        const username = newUsernameInput.value.trim();
        const password = newPasswordInput.value.trim();
        const role = newUserRoleSelect.value;
        const team = newUserTeamSelect.value;

        if (!username || !password) {
            showStatus('Username and password are required.', 'error', createUserStatus);
            return;
        }

        try {
            showStatus('Creating user...', 'loading', createUserStatus);
            const response = await fetch('/api/admin/create-user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, role, team }),
            });

            const result = await response.json();
            if (response.ok) {
                showStatus(result.message, 'success', createUserStatus);
                createUserForm.reset();
                await refreshUserList();
            } else {
                throw new Error(result.detail || 'Failed to create user.');
            }
        } catch (error) {
            console.error('Error creating user:', error);
            showStatus(error.message, 'error', createUserStatus);
        }
    }

    async function handleDeleteUser(username) {
        if (!confirm(`Are you sure you want to permanently delete the user '${username}'?`)) return;

        try {
            showStatus('Deleting user...', 'loading', createUserStatus);
            const response = await fetch(`/api/admin/users/${username}`, { method: 'DELETE' });
            const result = await response.json();

            if (response.ok) {
                showStatus(result.message, 'success', createUserStatus);
                await refreshUserList();
            } else {
                throw new Error(result.detail || 'Failed to delete user.');
            }
        } catch (error) {
            console.error('Error deleting user:', error);
            showStatus(error.message, 'error', createUserStatus);
        }
    }

    // --- Event Listeners ---
    if (docTableBody) {
        docTableBody.addEventListener('click', (event) => {
            if (event.target.classList.contains('save-btn')) {
                const docId = event.target.dataset.docId;
                handleSavePermissions(docId);
            }
        });
    }

    if (createUserForm) {
        createUserForm.addEventListener('submit', handleCreateUser);
    }

    if (userList) {
        userList.addEventListener('click', (event) => {
            const deleteButton = event.target.closest('.delete-user-btn');
            if (deleteButton && !deleteButton.disabled) {
                handleDeleteUser(deleteButton.dataset.username);
            }
        });
    }

    // --- Initialization ---
    async function init() {
        manageTheme();
        setupProfileDropdown();
        await fetchAllTeams();
        await fetchDocumentsAndPermissions();
        await refreshUserList();
    }

    init();
});

