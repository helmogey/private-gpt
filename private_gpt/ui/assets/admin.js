document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const profileBtn = document.getElementById('profile-btn');
    const profileDropdown = document.getElementById('profile-dropdown');
    const profileUsername = document.getElementById('profile-username');
    const profileRole = document.getElementById('profile-role');

    // Tab elements
    const userManagementTab = document.getElementById('user-management-tab');
    const docManagementTab = document.getElementById('doc-management-tab');
    const userManagementContent = document.getElementById('user-management-content');
    const docManagementContent = document.getElementById('doc-management-content');

    // User Management elements
    const createUserForm = document.getElementById('create-user-form');
    const newUsernameInput = document.getElementById('new-username');
    const newPasswordInput = document.getElementById('new-password');
    const newUserRoleSelect = document.getElementById('new-user-role');
    const newUserTeamSelect = document.getElementById('new-user-team');
    const createUserStatus = document.getElementById('create-user-status');
    const userList = document.getElementById('user-list');

    // Edit User Modal elements
    const editUserModal = document.getElementById('edit-user-modal');
    const editUserModalCloseBtn = document.getElementById('edit-user-modal-close-btn');
    const editUsernameDisplay = document.getElementById('edit-username-display');
    const editUserRoleSelect = document.getElementById('edit-user-role-select');
    const editUserTeamsSelect = document.getElementById('edit-user-teams-select');
    const cancelEditUserBtn = document.getElementById('cancel-edit-user-btn');
    const saveEditUserBtn = document.getElementById('save-edit-user-btn');
    const editUserStatus = document.getElementById('edit-user-status');

    // Reset Password Modal elements
    const resetPasswordModal = document.getElementById('reset-password-modal');
    const resetPasswordModalCloseBtn = document.getElementById('reset-password-modal-close-btn');
    const resetUsernameDisplay = document.getElementById('reset-username-display');
    const newDefaultPasswordInput = document.getElementById('new-default-password');
    const cancelResetPasswordBtn = document.getElementById('cancel-reset-password-btn');
    const saveResetPasswordBtn = document.getElementById('save-reset-password-btn');
    const resetPasswordStatus = document.getElementById('reset-password-status');


    // Document Management elements
    const docList = document.getElementById('doc-list');
    const permissionsModal = document.getElementById('permissions-modal');
    const permissionsModalCloseBtn = document.getElementById('permissions-modal-close-btn');
    const modalDocName = document.getElementById('modal-doc-name');
    const availableTeamsList = document.getElementById('available-teams-list-modal');
    const assignedTeamsList = document.getElementById('assigned-teams-list-modal');
    const cancelPermissionsBtn = document.getElementById('cancel-permissions-btn');
    const savePermissionsBtn = document.getElementById('save-permissions-btn');

    // --- State Variables ---
    let currentUsername = null;
    let allTeams = [];
    let currentEditingDoc = null;
    let currentEditingUser = null; // Track user for editing/password reset


    // --- Utility Functions ---
    function showStatus(message, type = 'info', element = createUserStatus) {
        element.textContent = message;
        element.className = `upload-status ${type}`;
        element.style.display = 'block';
        setTimeout(() => {
            element.style.display = 'none';
        }, 3000);
    }

    // --- Tab Navigation ---
    function setupTabs() {
        userManagementTab.addEventListener('click', () => {
            // Button state
            userManagementTab.classList.add('active');
            docManagementTab.classList.remove('active');
            // Content visibility
            userManagementContent.classList.add('active');
            docManagementContent.classList.remove('active');
        });

        docManagementTab.addEventListener('click', () => {
            // Button state
            docManagementTab.classList.add('active');
            userManagementTab.classList.remove('active');
            // Content visibility
            docManagementContent.classList.add('active');
            userManagementContent.classList.remove('active');
        });
    }

    // --- Document Management ---
    async function fetchDocumentsAndPermissions() {
        try {
            const response = await fetch('/api/admin/documents');
            if (!response.ok) {
                throw new Error('Failed to fetch document permissions');
            }
            const documents = await response.json();
            renderDocumentList(documents);
        } catch (error) {
            console.error('Error fetching documents:', error);
            docList.innerHTML = '<tr><td colspan="3">Could not load documents.</td></tr>';
        }
    }

    function renderDocumentList(documents) {
        docList.innerHTML = '';
        if (documents.length === 0) {
            docList.innerHTML = '<tr><td colspan="3">No documents have been ingested yet.</td></tr>';
            return;
        }
        documents.forEach(doc => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${doc.file_name}</td>
                <td>
                    <div class="team-badges">
                        ${doc.teams.map(team => `<span class="team-badge">${team}</span>`).join('') || '<span>No teams assigned</span>'}
                    </div>
                </td>
                <td>
                    <button class="edit-permissions-btn icon-button" data-doc-name="${doc.file_name}">Edit</button>
                </td>
            `;
            docList.appendChild(tr);
        });
    }
    
    function openPermissionsModal(docName) {
        currentEditingDoc = docName;
        modalDocName.textContent = docName;
    
        const docRow = Array.from(docList.querySelectorAll('tr')).find(row => row.cells[0].textContent === docName);
        const assignedTeamBadges = docRow.querySelectorAll('.team-badge');
        const assignedTeams = Array.from(assignedTeamBadges).map(badge => badge.textContent);
    
        availableTeamsList.innerHTML = '';
        assignedTeamsList.innerHTML = '';
    
        allTeams.forEach(team => {
            const li = document.createElement('li');
            li.className = 'team-list-item';
            li.textContent = team;
            li.dataset.team = team;
            if (assignedTeams.includes(team)) {
                assignedTeamsList.appendChild(li);
            } else {
                availableTeamsList.appendChild(li);
            }
        });
    
        permissionsModal.classList.remove('hidden');
    }

    function moveTeamItem(element, fromList, toList) {
        fromList.removeChild(element);
        toList.appendChild(element);
    }
    
    async function handleSavePermissions() {
        const assignedTeamElements = assignedTeamsList.querySelectorAll('.team-list-item');
        const newTeams = Array.from(assignedTeamElements).map(el => el.dataset.team);

        try {
            const response = await fetch('/api/admin/documents/permissions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_name: currentEditingDoc,
                    teams: newTeams
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to save permissions.');
            }
            
            await fetchDocumentsAndPermissions();
            permissionsModal.classList.add('hidden');

        } catch (error) {
            console.error('Error saving permissions:', error);
            alert(`Error saving permissions: ${error.message}`);
        }
    }


    // --- User Management ---
    async function fetchAndStoreTeams() {
        try {
            const response = await fetch('/api/admin/teams');
            if (!response.ok) throw new Error('Failed to fetch teams');
            allTeams = await response.json();
            populateTeamsDropdown();
        } catch (error) {
            console.error('Error fetching teams list:', error);
            allTeams = ['Default']; // Fallback
            populateTeamsDropdown();
        }
    }

    function populateTeamsDropdown() {
        if (!newUserTeamSelect) return;
        newUserTeamSelect.innerHTML = '';
        // Also populate the edit modal dropdown
        editUserTeamsSelect.innerHTML = '';
        
        allTeams.forEach(team => {
            const option = document.createElement('option');
            option.value = team;
            option.textContent = team;
            
            newUserTeamSelect.appendChild(option);
            // Clone the option for the edit modal
            editUserTeamsSelect.appendChild(option.cloneNode(true));
        });
    }

    async function refreshUserList() {
        try {
            const response = await fetch('/api/admin/users');
            if (!response.ok) {
                throw new Error(`Failed to fetch users: ${response.statusText}`);
            }
            const users = await response.json();
            userList.innerHTML = '';
            users.forEach(user => {
                const li = document.createElement('li');
                const isEditableAndDeletable = user.username !== 'admin' && user.username !== currentUsername;
                
                // Handle single team (string) or multiple teams (array)
                let teamDisplay = 'No Team';
                let teamsData = '';
                if (Array.isArray(user.teams) && user.teams.length > 0) {
                    teamDisplay = user.teams.map(team => `<span class="user-team">${team}</span>`).join('');
                    teamsData = user.teams.join(',');
                } else if (typeof user.team === 'string' && user.team) {
                    // Fallback for older single-team format
                    teamDisplay = `<span class="user-team">${user.team}</span>`;
                    teamsData = user.team;
                }

                li.innerHTML = `
                    <div class="user-info">
                        <span>${user.username}</span>
                        <div class="user-teams-list">${teamDisplay}</div>
                    </div>
                    <div class="user-role-actions">
                        <span class="user-role ${user.role}">${user.role}</span>
                        
                        <!-- Edit User Button -->
                        <button class="edit-user-btn" 
                                data-username="${user.username}" 
                                data-role="${user.role}" 
                                data-teams="${teamsData}" 
                                title="Edit User" 
                                ${!isEditableAndDeletable ? 'disabled' : ''}>
                            <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M20.71 7.04c.39-.39.39-1.04 0-1.41l-2.34-2.34c-.37-.39-1.02-.39-1.41 0l-1.84 1.83l3.75 3.75l1.84-1.83M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25Z"/></svg>
                        </button>
                        
                        <!-- NEW: Reset Password Button -->
                        <button class="reset-password-btn"
                                data-username="${user.username}"
                                title="Reset Password"
                                ${!isEditableAndDeletable ? 'disabled' : ''}>
                            <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M12 17a2 2 0 0 0 2-2a2 2 0 0 0-2-2a2 2 0 0 0-2 2a2 2 0 0 0 2 2m6-9h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2m-6 9a2 2 0 0 1-2-2a2 2 0 0 1 2-2a2 2 0 0 1 2 2a2 2 0 0 1-2 2m3-9H9V6c0-1.66 1.34-3 3-3s3 1.34 3 3v2Z"/></svg>
                        </button>

                        <!-- Delete User Button -->
                        <button class="delete-user-btn" data-username="${user.username}" title="Delete User" ${!isEditableAndDeletable ? 'disabled' : ''}>
                            <svg width="16" height="16" viewBox="0 0 24 24">
    <path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
</svg>
                        </button>
                    </div>
                `;
                userList.appendChild(li);
            });
        } catch (error) {
            console.error('Error refreshing user list:', error);
            showStatus('Could not load user list', 'error', createUserStatus);
        }
    }

    /**
     * --- **FIXED** ---
     * Helper to extract a readable error message from the server response.
     * Handles strings, objects (e.g., detail.msg), and FastAPI validation arrays.
     */
    function getErrorMessage(detail) {
        if (typeof detail === 'string') {
            return detail;
        }
        if (Array.isArray(detail) && detail[0]?.msg) {
            // Handle FastAPI validation errors
            return detail.map(err => `${err.loc.join('.')} - ${err.msg}`).join('; ');
        }
        if (detail?.msg) {
            // Handle other object-based error messages
            return detail.msg;
        }
        // Fallback
        return 'An unknown error occurred.';
    }


    async function handleCreateUser(event) {
        event.preventDefault();
        const username = newUsernameInput.value.trim();
        const password = newPasswordInput.value.trim();
        const role = newUserRoleSelect.value;
        const teams = Array.from(newUserTeamSelect.selectedOptions).map(option => option.value);

        if (!username || !password) {
            showStatus('Username and password are required.', 'error', createUserStatus);
            return;
        }

        try {
            showStatus('Creating user...', 'loading', createUserStatus);
            const response = await fetch('/api/admin/create-user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                // ***FIX 1:*** Changed key from 'teams' to 'team' to match backend error
                body: JSON.stringify({ username, password, role, team: teams }),
            });

            const result = await response.json();

            if (response.ok) {
                showStatus(result.message, 'success', createUserStatus);
                createUserForm.reset();
                await refreshUserList();
            } else {
                // ***MODIFIED HERE***: Use the new error helper
                throw new Error(getErrorMessage(result.detail) || 'Failed to create user.');
            }
        } catch (error) {
            console.error('Error creating user:', error);
            showStatus(error.message, 'error', createUserStatus);
        }
    }

    async function handleDeleteUser(username) {
        if (!confirm(`Are you sure you want to permanently delete the user '${username}'? This action cannot be undone.`)) {
            return;
        }

        try {
            showStatus('Deleting user...', 'loading', createUserStatus);
            const response = await fetch(`/api/admin/users/${username}`, {
                method: 'DELETE',
            });

            const result = await response.json();

            if (response.ok) {
                showStatus(result.message, 'success', createUserStatus);
                await refreshUserList();
            } else {
                // ***MODIFIED HERE***: Use the new error helper
                throw new Error(getErrorMessage(result.detail) || 'Failed to delete user.');
            }
        } catch (error) {
            console.error('Error deleting user:', error);
            showStatus(error.message, 'error', createUserStatus);
        }
    }

    // --- Edit User Modal Functions ---
    function openEditUserModal(username, role, teamsString) {
        currentEditingUser = username;
        editUsernameDisplay.textContent = username;
        editUserRoleSelect.value = role;

        // Deselect all team options first
        Array.from(editUserTeamsSelect.options).forEach(opt => {
            opt.selected = false;
        });

        // Select the user's current teams
        const userTeams = teamsString ? teamsString.split(',') : [];
        userTeams.forEach(teamName => {
            const option = editUserTeamsSelect.querySelector(`option[value="${teamName}"]`);
            if (option) {
                option.selected = true;
            }
        });
        
        editUserModal.classList.remove('hidden');
    }

    async function handleSaveUserEdit() {
        if (!currentEditingUser) return;

        const newRole = editUserRoleSelect.value;
        const newTeams = Array.from(editUserTeamsSelect.selectedOptions).map(option => option.value);

        try {
            showStatus('Saving changes...', 'loading', editUserStatus);
            const response = await fetch('/api/admin/users/edit', {
                // ***FIX 2:*** Changed method from 'POST' to 'PUT'
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: currentEditingUser,
                    new_role: newRole,
                    new_teams: newTeams
                })
            });

            const result = await response.json();

            if (response.ok) {
                showStatus('User updated successfully.', 'success', editUserStatus);
                await refreshUserList();
                setTimeout(() => {
                    editUserModal.classList.add('hidden');
                    currentEditingUser = null;
                }, 1500);
            } else {
                // ***MODIFIED HERE***: Use the new error helper
                throw new Error(getErrorMessage(result.detail) || 'Failed to save changes.');
            }

        } catch (error) {
            console.error('Error saving user edits:', error);
            showStatus(error.message, 'error', editUserStatus);
        }
    }

    // --- NEW: Reset Password Modal Functions ---
    function openResetPasswordModal(username) {
        currentEditingUser = username;
        resetUsernameDisplay.textContent = username;
        newDefaultPasswordInput.value = ''; // Clear old password
        resetPasswordModal.classList.remove('hidden');
    }

    async function handleResetPassword() {
        if (!currentEditingUser) return;

        const newPassword = newDefaultPasswordInput.value;
        if (!newPassword) {
            showStatus('Please enter a new password.', 'error', resetPasswordStatus);
            return;
        }

        try {
            showStatus('Resetting password...', 'loading', resetPasswordStatus);
            const response = await fetch('/api/admin/users/reset-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: currentEditingUser,
                    new_password: newPassword
                })
            });

            const result = await response.json();

            if (response.ok) {
                showStatus('Password reset successfully.', 'success', resetPasswordStatus);
                await refreshUserList();
                setTimeout(() => {
                    resetPasswordModal.classList.add('hidden');
                    currentEditingUser = null;
                }, 1500);
            } else {
                // ***MODIFIED HERE***: Use the new error helper
                throw new Error(getErrorMessage(result.detail) || 'Failed to reset password.');
            }

        } catch (error) {
            console.error('Error resetting password:', error);
            showStatus(error.message, 'error', resetPasswordStatus);
        }
    }


    // --- UI & Theme ---
    function manageTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        if (savedTheme === 'dark') document.body.classList.add('dark');
        themeToggleBtn.addEventListener('click', () => {
            document.body.classList.toggle('dark');
            localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
        });
    }

    async function fetchUserInfo() {
        try {
            const response = await fetch('/api/user/info');
            if (!response.ok) throw new Error('Failed to fetch user info.');
            const data = await response.json();
            
            currentUsername = data.username;
            profileUsername.textContent = data.display_name || data.username;
            profileRole.textContent = data.role;
            profileRole.className = `user-role ${data.role}`;
        } catch (error) {
            console.error('Error fetching user info:', error);
        }
    }

    // --- Event Listeners ---
    if (createUserForm) createUserForm.addEventListener('submit', handleCreateUser);
    
    profileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        profileDropdown.classList.toggle('show');
    });
    
    window.addEventListener('click', (e) => {
        if (!profileDropdown.contains(e.target) && !profileBtn.contains(e.target)) {
            profileDropdown.classList.remove('show');
        }
    });

    userList.addEventListener('click', (event) => {
        const deleteButton = event.target.closest('.delete-user-btn');
        const editButton = event.target.closest('.edit-user-btn');
        const resetButton = event.target.closest('.reset-password-btn'); // NEW

        if (deleteButton && !deleteButton.disabled) {
            handleDeleteUser(deleteButton.dataset.username);
        }
        
        if (editButton && !editButton.disabled) {
            const { username, role, teams } = editButton.dataset;
            openEditUserModal(username, role, teams);
        }

        // NEW
        if (resetButton && !resetButton.disabled) {
            openResetPasswordModal(resetButton.dataset.username);
        }
    });

    docList.addEventListener('click', (event) => {
        const editButton = event.target.closest('.edit-permissions-btn');
        if (editButton) {
            openPermissionsModal(editButton.dataset.docName);
        }
    });

    availableTeamsList.addEventListener('click', e => {
        if (e.target.classList.contains('team-list-item')) {
            moveTeamItem(e.target, availableTeamsList, assignedTeamsList);
        }
    });

    assignedTeamsList.addEventListener('click', e => {
        if (e.target.classList.contains('team-list-item')) {
            moveTeamItem(e.target, assignedTeamsList, availableTeamsList);
        }
    });

    [permissionsModalCloseBtn, cancelPermissionsBtn].forEach(btn => {
        btn.addEventListener('click', () => permissionsModal.classList.add('hidden'));
    });
    
    savePermissionsBtn.addEventListener('click', handleSavePermissions);

    // Edit User Modal Listeners
    [editUserModalCloseBtn, cancelEditUserBtn].forEach(btn => {
        btn.addEventListener('click', () => {
            editUserModal.classList.add('hidden');
            currentEditingUser = null;
            editUserStatus.style.display = 'none';
        });
    });

    saveEditUserBtn.addEventListener('click', handleSaveUserEdit);
    
    // NEW: Reset Password Modal Listeners
    [resetPasswordModalCloseBtn, cancelResetPasswordBtn].forEach(btn => {
        btn.addEventListener('click', () => {
            resetPasswordModal.classList.add('hidden');
            currentEditingUser = null;
            resetPasswordStatus.style.display = 'none';
        });
    });

    saveResetPasswordBtn.addEventListener('click', handleResetPassword);


    // --- Initialization ---
    async function init() {
        if (createUserForm) createUserForm.reset();
        
        setupTabs();
        manageTheme();
        await fetchUserInfo();
        await fetchAndStoreTeams();
        await refreshUserList();
        await fetchDocumentsAndPermissions();
    }

    init();
});

