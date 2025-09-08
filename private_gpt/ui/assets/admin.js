document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // Document Management Elements
    const docMgmtStatus = document.getElementById('doc-mgmt-status');
    const docTableBody = document.querySelector('#document-management-table tbody');
    const permissionsModal = document.getElementById('permissions-modal');
    const permissionsModalTitle = document.getElementById('permissions-modal-title');
    const permissionsModalCloseBtn = document.getElementById('permissions-modal-close-btn');
    const permissionsModalCancelBtn = document.getElementById('permissions-modal-cancel-btn');
    const permissionsModalSaveBtn = document.getElementById('permissions-modal-save-btn');
    const permissionsTeamList = document.getElementById('permissions-team-list');

    // User Management Elements
    const createUserForm = document.getElementById('create-user-form');
    const newUsernameInput = document.getElementById('new-username');
    const newPasswordInput = document.getElementById('new-password');
    const newUserRoleSelect = document.getElementById('new-user-role');
    const newUserTeamSelect = document.getElementById('new-user-team');
    const createUserStatus = document.getElementById('create-user-status');
    const userList = document.getElementById('user-list');

    // --- State Variables ---
    let allTeams = [];
    let allDocuments = [];
    let currentEditingDocId = null;

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

    function setupProfileDropdown() {
        const profileBtn = document.getElementById('profile-btn');
        const profileDropdown = document.getElementById('profile-dropdown');
        const profileUsername = document.getElementById('profile-username');
        const profileRole = document.getElementById('profile-role');
        if (!profileBtn || !profileDropdown) return;
        fetch('/api/user/info').then(response => response.ok ? response.json() : Promise.reject('Failed to fetch user info'))
        .then(data => {
            if (profileUsername) profileUsername.textContent = data.display_name || data.username;
            if (profileRole) {
                profileRole.textContent = data.role;
                profileRole.className = `user-role ${data.role}`;
            }
        }).catch(error => console.error("Error populating profile:", error));
        profileBtn.addEventListener('click', (e) => { e.stopPropagation(); profileDropdown.classList.toggle('show'); });
        window.addEventListener('click', () => { profileDropdown.classList.remove('show'); });
    }

    // --- Tab Switching Logic ---
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            button.classList.add('active');
            document.getElementById(button.dataset.tab).classList.add('active');
        });
    });

    // --- Document Management & Permissions Modal Logic ---
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
            allDocuments = await response.json();
            renderDocumentTable(allDocuments);
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
            const teamsHtml = doc.teams.length > 0
                ? doc.teams.map(team => `<span class="team-badge">${team}</span>`).join('')
                : '<span>No teams assigned</span>';
            
            row.innerHTML = `
                <td>${doc.file_name}</td>
                <td><div class="team-badge-container">${teamsHtml}</div></td>
                <td>
                    <button class="edit-btn" data-doc-id="${doc.doc_id}" data-doc-name="${doc.file_name}">Edit</button>
                </td>
            `;
            docTableBody.appendChild(row);
        });
    }

    function openPermissionsModal(docId, docName) {
        const doc = allDocuments.find(d => d.doc_id === docId);
        if (!doc) return;

        currentEditingDocId = docId;
        permissionsModalTitle.textContent = `Edit Permissions for: ${docName}`;
        
        permissionsTeamList.innerHTML = allTeams.map(team => `
            <label class="permissions-team-item">
                <input type="checkbox" value="${team}" ${doc.teams.includes(team) ? 'checked' : ''}>
                <span>${team}</span>
            </label>
        `).join('');

        permissionsModal.classList.remove('hidden');
    }

    function closePermissionsModal() {
        permissionsModal.classList.add('hidden');
        currentEditingDocId = null;
    }

    async function handleSavePermissions() {
        if (!currentEditingDocId) return;

        const selectedTeams = Array.from(permissionsTeamList.querySelectorAll('input:checked')).map(input => input.value);
        
        showStatus('Saving...', 'loading');
        try {
            const response = await fetch('/api/admin/documents/permissions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ doc_id: currentEditingDocId, teams: selectedTeams }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to save permissions');
            }
            showStatus('Permissions updated successfully!', 'success');
            closePermissionsModal();
            await fetchDocumentsAndPermissions(); // Refresh table
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
                        <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M9 3v4H4v6h1v9a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-9h1V4h-5V3H9m2 5h2v9h-2V8Z"/></svg>
                    </button>`;
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
            showStatus(error.message, 'error', createUserStatus);
        }
    }

    // --- Event Listeners ---
    if (docTableBody) {
        docTableBody.addEventListener('click', (event) => {
            const editButton = event.target.closest('.edit-btn');
            if (editButton) {
                openPermissionsModal(editButton.dataset.docId, editButton.dataset.docName);
            }
        });
    }

    permissionsModalCloseBtn.addEventListener('click', closePermissionsModal);
    permissionsModalCancelBtn.addEventListener('click', closePermissionsModal);
    permissionsModal.addEventListener('click', (e) => { if (e.target === permissionsModal) closePermissionsModal(); });
    permissionsModalSaveBtn.addEventListener('click', handleSavePermissions);

    if (createUserForm) createUserForm.addEventListener('submit', handleCreateUser);
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
        if (createUserForm) {
            createUserForm.reset(); // Explicitly clear the form on load
        }
        await fetchAllTeams();
        await fetchDocumentsAndPermissions();
        await refreshUserList();
    }

    init();
});

