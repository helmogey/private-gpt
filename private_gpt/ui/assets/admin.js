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
    const llmConfigTab = document.getElementById('llm-config-tab');
    const mcpConfigTab = document.getElementById('mcp-config-tab'); // Added
    const userManagementContent = document.getElementById('user-management-content');
    const docManagementContent = document.getElementById('doc-management-content');
    const llmConfigContent = document.getElementById('llm-config-content');
    const mcpConfigContent = document.getElementById('mcp-config-content'); // Added

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
    
    // Team Lists
    const availableTeamsList = document.getElementById('available-teams-list-modal');
    const assignedTeamsList = document.getElementById('assigned-teams-list-modal');
    
    // Tag Lists
    const availableTagsList = document.getElementById('available-tags-list-modal');
    const assignedTagsList = document.getElementById('assigned-tags-list-modal');

    const cancelPermissionsBtn = document.getElementById('cancel-permissions-btn');
    const savePermissionsBtn = document.getElementById('save-permissions-btn');

    // --- LLM Config Elements ---
    const llmProviderSelect = document.getElementById('llm-provider');
    const llmUrlGroup = document.getElementById('llm-url-group');
    const llmTokenGroup = document.getElementById('llm-token-group');
    const llmUrlInput = document.getElementById('llm-url');
    const llmTokenInput = document.getElementById('llm-token');
    const fetchModelsBtn = document.getElementById('fetch-models-btn');
    const llmModelSelect = document.getElementById('llm-model-select');
    const saveLlmBtn = document.getElementById('save-llm-btn');
    const fetchModelsStatus = document.getElementById('fetch-models-status');
    const saveLlmStatus = document.getElementById('save-llm-status');

    // --- MCP Config Elements (Added) ---
    const createMcpForm = document.getElementById('create-mcp-form');
    const mcpNameInput = document.getElementById('mcp-name');
    const mcpTransportSelect = document.getElementById('mcp-transport');
    const mcpCommandInput = document.getElementById('mcp-command');
    const mcpCommandHint = document.getElementById('mcp-command-hint');
    const mcpArgsInput = document.getElementById('mcp-args');
    const mcpArgsGroup = document.getElementById('mcp-args-group');
    const mcpEnvVarsContainer = document.getElementById('mcp-env-vars-container');
    const addMcpEnvBtn = document.getElementById('add-mcp-env-btn');
    const createMcpStatus = document.getElementById('create-mcp-status');
    const mcpList = document.getElementById('mcp-list');

    // --- Edit MCP Elements ---
    const editMcpModal = document.getElementById('edit-mcp-modal');
    const editMcpModalCloseBtn = document.getElementById('edit-mcp-modal-close-btn');
    const cancelEditMcpBtn = document.getElementById('cancel-edit-mcp-btn');
    const saveEditMcpBtn = document.getElementById('save-edit-mcp-btn');
    const editMcpId = document.getElementById('edit-mcp-id');
    const editMcpName = document.getElementById('edit-mcp-name');
    const editMcpNameDisplay = document.getElementById('edit-mcp-name-display');
    const editMcpTransport = document.getElementById('edit-mcp-transport');
    const editMcpCommand = document.getElementById('edit-mcp-command');
    const editMcpArgs = document.getElementById('edit-mcp-args');
    const editMcpArgsGroup = document.getElementById('edit-mcp-args-group');
    const editMcpEnvVarsContainer = document.getElementById('edit-mcp-env-vars-container');
    const addEditMcpEnvBtn = document.getElementById('add-edit-mcp-env-btn');
    const editMcpStatus = document.getElementById('edit-mcp-status');

    // --- Test MCP Elements ---
    const testMcpModal = document.getElementById('test-mcp-modal');
    const testMcpModalCloseBtn = document.getElementById('test-mcp-modal-close-btn');
    const testMcpStatus = document.getElementById('test-mcp-status');

    let allMcps = []; // Store to easily fetch for editing

    // --- State Variables ---
    let currentUsername = null;
    let allTeams = [];
    let allTags = []; 
    let currentEditingDoc = null;
    let currentEditingUser = null; 


    // --- Utility Functions ---
    function showStatus(message, type = 'info', element = createUserStatus) {
        element.textContent = message;
        element.className = `upload-status ${type}`;
        element.style.display = 'block';
        setTimeout(() => {
            element.style.display = 'none';
        }, 3000);
    }

    function getErrorMessage(detail) {
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail) && detail[0]?.msg) return detail.map(err => `${err.loc.join('.')} - ${err.msg}`).join('; ');
        if (detail?.msg) return detail.msg;
        return 'An unknown error occurred.';
    }

    // --- Tab Navigation ---
    function setupTabs() {
        const tabs = [userManagementTab, docManagementTab, llmConfigTab, mcpConfigTab];
        const panes = [userManagementContent, docManagementContent, llmConfigContent, mcpConfigContent];

        tabs.forEach((tab, index) => {
            if (!tab) return;
            tab.addEventListener('click', () => {
                tabs.forEach(t => t?.classList.remove('active'));
                panes.forEach(p => p?.classList.remove('active'));
                
                tab.classList.add('active');
                if (panes[index]) {
                    panes[index].classList.add('active');
                    // Special grid handling for panes that need it
                    if (tab.id === 'user-management-tab' || tab.id === 'mcp-config-tab') {
                        panes[index].style.display = 'grid';
                    }
                }

                if (tab.id === 'llm-config-tab') loadCurrentLLMConfig();
                if (tab.id === 'mcp-config-tab') fetchMCPConfigs();
            });
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
            docList.innerHTML = '<tr><td colspan="4">Could not load documents.</td></tr>';
        }
    }

    function renderDocumentList(documents) {
        docList.innerHTML = '';
        if (documents.length === 0) {
            docList.innerHTML = '<tr><td colspan="4">No documents have been ingested yet.</td></tr>';
            return;
        }
        documents.forEach(doc => {
            const tr = document.createElement('tr');
            // Safe fallback if tags is undefined (older version)
            const tags = doc.tags || [];
            
            tr.innerHTML = `
                <td>${doc.file_name}</td>
                <td>
                    <div class="team-badges">
                        ${doc.teams.map(team => `<span class="team-badge">${team}</span>`).join('') || '<span class="empty-badge">No teams</span>'}
                    </div>
                </td>
                <td>
                    <div class="team-badges"> <!-- Reuse badge style for tags -->
                        ${tags.map(tag => `<span class="team-badge tag-badge">${tag}</span>`).join('') || '<span class="empty-badge">No tags</span>'}
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
    
        // Find the document data from the table
        const docRow = Array.from(docList.querySelectorAll('tr')).find(row => row.cells[0].textContent === docName);
        
        // 1. Teams
        const assignedTeamBadges = docRow.cells[1].querySelectorAll('.team-badge');
        const assignedTeams = Array.from(assignedTeamBadges).map(badge => badge.textContent);
        
        // 2. Tags
        const assignedTagBadges = docRow.cells[2].querySelectorAll('.team-badge');
        const assignedTags = Array.from(assignedTagBadges).map(badge => badge.textContent);
    
        // Populate Teams
        availableTeamsList.innerHTML = '';
        assignedTeamsList.innerHTML = '';
        allTeams.forEach(team => {
            const li = document.createElement('li');
            li.className = 'team-list-item';
            li.textContent = team;
            li.dataset.value = team;
            if (assignedTeams.includes(team)) {
                assignedTeamsList.appendChild(li);
            } else {
                availableTeamsList.appendChild(li);
            }
        });

        // Populate Tags
        availableTagsList.innerHTML = '';
        assignedTagsList.innerHTML = '';
        allTags.forEach(tag => {
            const li = document.createElement('li');
            li.className = 'team-list-item';
            li.textContent = tag;
            li.dataset.value = tag;
            if (assignedTags.includes(tag)) {
                assignedTagsList.appendChild(li);
            } else {
                availableTagsList.appendChild(li);
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
        const newTeams = Array.from(assignedTeamElements).map(el => el.dataset.value);

        const assignedTagElements = assignedTagsList.querySelectorAll('.team-list-item');
        const newTags = Array.from(assignedTagElements).map(el => el.dataset.value);

        try {
            const response = await fetch('/api/admin/documents/permissions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_name: currentEditingDoc,
                    teams: newTeams,
                    tags: newTags
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

    // Fetch Tags
    async function fetchAndStoreTags() {
        try {
            const response = await fetch('/api/tags');
            if (!response.ok) throw new Error('Failed to fetch tags');
            allTags = await response.json();
        } catch (error) {
            console.error('Error fetching tags list:', error);
            allTags = ['GENERAL']; // Fallback
        }
    }

    function populateTeamsDropdown() {
        if (!newUserTeamSelect) return;
        newUserTeamSelect.innerHTML = '';
        editUserTeamsSelect.innerHTML = '';
        
        allTeams.forEach(team => {
            const option = document.createElement('option');
            option.value = team;
            option.textContent = team;
            
            newUserTeamSelect.appendChild(option);
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
                
                let teamDisplay = 'No Team';
                let teamsData = '';
                if (Array.isArray(user.teams) && user.teams.length > 0) {
                    teamDisplay = user.teams.map(team => `<span class="user-team">${team}</span>`).join('');
                    teamsData = user.teams.join(',');
                } else if (typeof user.team === 'string' && user.team) {
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
                        <button class="edit-user-btn" data-username="${user.username}" data-role="${user.role}" data-teams="${teamsData}" title="Edit User" ${!isEditableAndDeletable ? 'disabled' : ''}>
                            <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M20.71 7.04c.39-.39.39-1.04 0-1.41l-2.34-2.34c-.37-.39-1.02-.39-1.41 0l-1.84 1.83l3.75 3.75l1.84-1.83M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25Z"/></svg>
                        </button>
                        <button class="reset-password-btn" data-username="${user.username}" title="Reset Password" ${!isEditableAndDeletable ? 'disabled' : ''}>
                            <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M12 17a2 2 0 0 0 2-2a2 2 0 0 0-2-2a2 2 0 0 0-2 2a2 2 0 0 0 2 2m6-9h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2m-6 9a2 2 0 0 1-2-2a2 2 0 0 1 2-2a2 2 0 0 1 2 2a2 2 0 0 1-2 2m3-9H9V6c0-1.66 1.34-3 3-3s3 1.34 3 3v2Z"/></svg>
                        </button>
                        <button class="delete-user-btn" data-username="${user.username}" title="Delete User" ${!isEditableAndDeletable ? 'disabled' : ''}>
                            <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
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
                body: JSON.stringify({ username, password, role, team: teams }),
            });

            const result = await response.json();

            if (response.ok) {
                showStatus(result.message, 'success', createUserStatus);
                createUserForm.reset();
                await refreshUserList();
            } else {
                throw new Error(getErrorMessage(result.detail) || 'Failed to create user.');
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

        Array.from(editUserTeamsSelect.options).forEach(opt => {
            opt.selected = false;
        });

        const userTeams = teamsString ? teamsString.split(',') : [];
        userTeams.forEach(teamName => {
            const option = editUserTeamsSelect.querySelector(`option[value="${teamName}"]`);
            if (option) option.selected = true;
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
                throw new Error(getErrorMessage(result.detail) || 'Failed to save changes.');
            }

        } catch (error) {
            console.error('Error saving user edits:', error);
            showStatus(error.message, 'error', editUserStatus);
        }
    }

    // --- Reset Password Modal Functions ---
    function openResetPasswordModal(username) {
        currentEditingUser = username;
        resetUsernameDisplay.textContent = username;
        newDefaultPasswordInput.value = '';
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
                throw new Error(getErrorMessage(result.detail) || 'Failed to reset password.');
            }

        } catch (error) {
            console.error('Error resetting password:', error);
            showStatus(error.message, 'error', resetPasswordStatus);
        }
    }

    // --- LLM Config Logic ---
    if (llmProviderSelect) {
        llmProviderSelect.addEventListener('change', (e) => {
            if (e.target.value === 'Ollama') {
                llmUrlGroup.style.display = 'flex';
                llmTokenGroup.style.display = 'none';
            } else {
                llmUrlGroup.style.display = 'none';
                llmTokenGroup.style.display = 'flex';
            }
            llmModelSelect.innerHTML = '<option value="">Fetch models first...</option>';
            llmModelSelect.disabled = true;
            saveLlmBtn.disabled = true;
        });

        fetchModelsBtn.addEventListener('click', async () => {
            const provider = llmProviderSelect.value;
            const url = llmUrlInput.value;
            const token = llmTokenInput.value;

            try {
                showStatus('Fetching models...', 'loading', fetchModelsStatus);
                const response = await fetch('/api/admin/llm/models', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ provider, url, token })
                });
                
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || 'Failed to fetch models');

                llmModelSelect.innerHTML = '';
                data.models.forEach(model => {
                    const opt = document.createElement('option');
                    opt.value = model;
                    opt.textContent = model;
                    llmModelSelect.appendChild(opt);
                });
                llmModelSelect.disabled = false;
                saveLlmBtn.disabled = false;
                showStatus('Models loaded successfully', 'success', fetchModelsStatus);
            } catch (error) {
                showStatus(error.message, 'error', fetchModelsStatus);
            }
        });

        saveLlmBtn.addEventListener('click', async () => {
            try {
                showStatus('Saving configuration...', 'loading', saveLlmStatus);
                const response = await fetch('/api/admin/llm/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider: llmProviderSelect.value,
                        url: llmUrlInput.value,
                        token: llmTokenInput.value,
                        model: llmModelSelect.value
                    })
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || 'Failed to save config');
                
                showStatus(data.message, 'success', saveLlmStatus);
            } catch (error) {
                showStatus(error.message, 'error', saveLlmStatus);
            }
        });
    }

    async function loadCurrentLLMConfig() {
        try {
            const response = await fetch('/api/admin/llm/config');
            if (!response.ok) return;
            const data = await response.json();
            
            if (data && data.llm_provider) {
                llmProviderSelect.value = data.llm_provider;
                llmProviderSelect.dispatchEvent(new Event('change'));
                
                if (data.llm_url) llmUrlInput.value = data.llm_url;
                if (data.llm_token) llmTokenInput.value = data.llm_token;
                
                llmModelSelect.innerHTML = `<option value="${data.llm_model}">${data.llm_model}</option>`;
                llmModelSelect.disabled = false;
                saveLlmBtn.disabled = false;
            }
        } catch (error) {
            console.error("Could not load LLM config", error);
        }
    }

    // --- MCP Config Logic ---
    function createEnvVarRow(key = '', value = '', container) {
        if (!container) container = mcpEnvVarsContainer;
        const row = document.createElement('div');
        row.className = 'env-var-row';
        row.style.display = 'flex';
        row.style.gap = '0.5rem';
        row.style.marginBottom = '0.5rem';

        row.innerHTML = `
            <input type="text" class="textbox env-key" placeholder="Key (e.g., ZABBIX_URL)" value="${key}" style="flex: 1;">
            <input type="text" class="textbox env-value" placeholder="Value" value="${value}" style="flex: 2;">
            <button type="button" class="icon-button remove-env-btn" style="background: transparent; color: var(--foreground-muted); border: 1px solid var(--border);">&#10005;</button>
        `;

        row.querySelector('.remove-env-btn').addEventListener('click', () => {
            row.remove();
        });

        container.appendChild(row);
    }

    if (addMcpEnvBtn) {
        addMcpEnvBtn.addEventListener('click', () => createEnvVarRow('', '', mcpEnvVarsContainer));
    }
    if (addEditMcpEnvBtn) {
        addEditMcpEnvBtn.addEventListener('click', () => createEnvVarRow('', '', editMcpEnvVarsContainer));
    }

    function toggleArgsGroup(transportSelect, argsGroup) {
        if (transportSelect.value === 'sse') {
            argsGroup.style.display = 'none';
        } else {
            argsGroup.style.display = 'block';
        }
    }

    if (mcpTransportSelect) {
        mcpTransportSelect.addEventListener('change', (e) => {
            if (e.target.value === 'sse') {
                mcpCommandHint.textContent = 'Enter the SSE URL (e.g., http://localhost:8080/sse).';
                mcpCommandInput.placeholder = 'http://...';
            } else {
                mcpCommandHint.textContent = 'Command to run (e.g., npx).';
                mcpCommandInput.placeholder = 'e.g., npx';
            }
            toggleArgsGroup(mcpTransportSelect, mcpArgsGroup);
        });
    }

    if (editMcpTransport) {
        editMcpTransport.addEventListener('change', () => toggleArgsGroup(editMcpTransport, editMcpArgsGroup));
    }

    async function fetchMCPConfigs() {
        if (!mcpList) return;
        try {
            const response = await fetch('/api/admin/mcp');
            if (!response.ok) throw new Error('Failed to fetch MCP configurations');
            allMcps = await response.json();
            renderMCPList(allMcps);
        } catch (error) {
            console.error('Error fetching MCPs:', error);
            mcpList.innerHTML = '<tr><td colspan="4">Could not load MCP configurations.</td></tr>';
        }
    }

    function renderMCPList(mcps) {
        mcpList.innerHTML = '';
        if (mcps.length === 0) {
            mcpList.innerHTML = '<tr><td colspan="4">No MCP servers configured yet.</td></tr>';
            return;
        }
        mcps.forEach(mcp => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${mcp.name}</strong></td>
                <td><span class="team-badge tag-badge">${mcp.transport_type}</span></td>
                <td>${mcp.command}</td>
                <td>
                    <div style="display: flex; gap: 0.25rem;">
                        <button class="test-mcp-btn icon-button" data-mcp-id="${mcp.id}" title="Test Connection" style="padding: 0.25rem 0.5rem; background: var(--background); color: var(--foreground-muted); border: 1px solid var(--border);">Test</button>
                        <button class="edit-mcp-btn" data-mcp-id="${mcp.id}" title="Edit MCP" style="background: transparent; border: none; cursor: pointer; color: var(--foreground-muted);">
                            <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M20.71 7.04c.39-.39.39-1.04 0-1.41l-2.34-2.34c-.37-.39-1.02-.39-1.41 0l-1.84 1.83l3.75 3.75l1.84-1.83M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25Z"/></svg>
                        </button>
                        <button class="delete-user-btn delete-mcp-btn" data-mcp-id="${mcp.id}" title="Delete MCP">
                            <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
                        </button>
                    </div>
                </td>
            `;
            mcpList.appendChild(tr);
        });
    }

    if (createMcpForm) {
        createMcpForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const payload = {
                name: mcpNameInput.value.trim(),
                transport_type: mcpTransportSelect.value,
                command: mcpCommandInput.value.trim(),
                args: mcpArgsInput.value.trim() ? mcpArgsInput.value.trim().split(',').map(a => a.trim()) : [],
                env_vars: {}
            };

            mcpEnvVarsContainer.querySelectorAll('.env-var-row').forEach(row => {
                const key = row.querySelector('.env-key').value.trim();
                const val = row.querySelector('.env-value').value.trim();
                if (key) payload.env_vars[key] = val;
            });

            if (!payload.name || !payload.command) {
                showStatus('Name and Command/URL are required.', 'error', createMcpStatus);
                return;
            }

            try {
                showStatus('Saving MCP config...', 'loading', createMcpStatus);
                const response = await fetch('/api/admin/mcp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                const result = await response.json();
                if (response.ok) {
                    showStatus('MCP configuration saved successfully.', 'success', createMcpStatus);
                    createMcpForm.reset();
                    mcpEnvVarsContainer.innerHTML = ''; 
                    await fetchMCPConfigs();
                } else {
                    throw new Error(result.detail || 'Failed to save.');
                }
            } catch (error) {
                showStatus(error.message, 'error', createMcpStatus);
            }
        });
    }

    if (mcpList) {
        mcpList.addEventListener('click', async (event) => {
            // DELETE
            const deleteBtn = event.target.closest('.delete-mcp-btn');
            if (deleteBtn) {
                const mcpId = deleteBtn.dataset.mcpId;
                if (!confirm(`Are you sure you want to delete this MCP configuration?`)) return;
                try {
                    const response = await fetch(`/api/admin/mcp/${mcpId}`, { method: 'DELETE' });
                    if (response.ok) await fetchMCPConfigs();
                    else alert('Failed to delete MCP');
                } catch (error) {
                    alert('Error deleting MCP.');
                }
            }

            // EDIT
            const editBtn = event.target.closest('.edit-mcp-btn');
            if (editBtn) {
                const mcpId = parseInt(editBtn.dataset.mcpId);
                const mcp = allMcps.find(m => m.id === mcpId);
                if (mcp) {
                    editMcpId.value = mcp.id;
                    editMcpName.value = mcp.name;
                    editMcpNameDisplay.textContent = mcp.name;
                    editMcpTransport.value = mcp.transport_type;
                    editMcpCommand.value = mcp.command;
                    editMcpArgs.value = mcp.args ? mcp.args.join(', ') : '';
                    
                    editMcpEnvVarsContainer.innerHTML = '';
                    if (mcp.env_vars) {
                        for (const [key, val] of Object.entries(mcp.env_vars)) {
                            createEnvVarRow(key, val, editMcpEnvVarsContainer);
                        }
                    }
                    toggleArgsGroup(editMcpTransport, editMcpArgsGroup);
                    editMcpModal.classList.remove('hidden');
                }
            }

            // TEST
            const testBtn = event.target.closest('.test-mcp-btn');
            if (testBtn) {
                const mcpId = parseInt(testBtn.dataset.mcpId);
                const mcp = allMcps.find(m => m.id === mcpId);
                if (mcp) {
                    runTestConnection(mcp);
                }
            }
        });
    }

    if (saveEditMcpBtn) {
        saveEditMcpBtn.addEventListener('click', async () => {
            const mcpId = editMcpId.value;
            const payload = {
                name: editMcpName.value.trim(),
                transport_type: editMcpTransport.value,
                command: editMcpCommand.value.trim(),
                args: editMcpArgs.value.trim() ? editMcpArgs.value.trim().split(',').map(a => a.trim()) : [],
                env_vars: {}
            };

            editMcpEnvVarsContainer.querySelectorAll('.env-var-row').forEach(row => {
                const key = row.querySelector('.env-key').value.trim();
                const val = row.querySelector('.env-value').value.trim();
                if (key) payload.env_vars[key] = val;
            });

            try {
                showStatus('Updating...', 'loading', editMcpStatus);
                const response = await fetch(`/api/admin/mcp/${mcpId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                if (response.ok) {
                    showStatus('Updated successfully. Restart PrivateGPT to apply to chat!', 'success', editMcpStatus);
                    await fetchMCPConfigs();
                    setTimeout(() => editMcpModal.classList.add('hidden'), 2000);
                } else {
                    const res = await response.json();
                    throw new Error(res.detail || 'Failed to update.');
                }
            } catch (error) {
                showStatus(error.message, 'error', editMcpStatus);
            }
        });
    }

    [editMcpModalCloseBtn, cancelEditMcpBtn].forEach(btn => {
        if(btn) btn.addEventListener('click', () => editMcpModal.classList.add('hidden'));
    });

    // --- Run Test Connection ---
    async function runTestConnection(mcpPayload) {
        testMcpModal.classList.remove('hidden');
        testMcpStatus.textContent = 'Testing connection...\nEstablishing session...';
        testMcpStatus.style.color = 'var(--foreground)';

        try {
            const response = await fetch('/api/admin/mcp/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(mcpPayload),
            });
            const result = await response.json();
            
            if (response.ok) {
                let output = `✅ ${result.message}\n\nDiscovered Tools:\n`;
                result.tools.forEach(t => {
                    output += ` - ${t.name}: ${t.description.substring(0, 70)}...\n`;
                });
                output += '\n\nNote: If tools are discovered, the AI agent has full access to them (Requires Server Restart if recently edited).';
                testMcpStatus.textContent = output;
                testMcpStatus.style.color = 'hsl(145, 55%, 35%)'; // Greenish
            } else {
                testMcpStatus.textContent = `❌ Test Failed\n\nError: ${result.error || result.detail}`;
                testMcpStatus.style.color = 'hsl(0, 72.2%, 50.6%)'; // Redish
            }
        } catch (error) {
            testMcpStatus.textContent = `❌ Test Error\n\nCould not reach backend API: ${error.message}`;
            testMcpStatus.style.color = 'hsl(0, 72.2%, 50.6%)';
        }
    }

    if (testMcpModalCloseBtn) {
        testMcpModalCloseBtn.addEventListener('click', () => testMcpModal.classList.add('hidden'));
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
        const resetButton = event.target.closest('.reset-password-btn');

        if (deleteButton && !deleteButton.disabled) {
            handleDeleteUser(deleteButton.dataset.username);
        }
        
        if (editButton && !editButton.disabled) {
            const { username, role, teams } = editButton.dataset;
            openEditUserModal(username, role, teams);
        }

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

    [availableTeamsList, assignedTeamsList, availableTagsList, assignedTagsList].forEach(list => {
        if (list) {
            list.addEventListener('click', e => {
                if (e.target.classList.contains('team-list-item')) {
                    const targetId = list.id.includes('available') ? list.id.replace('available', 'assigned') : list.id.replace('assigned', 'available');
                    const targetList = document.getElementById(targetId);
                    if (targetList) moveTeamItem(e.target, list, targetList);
                }
            });
        }
    });

    [permissionsModalCloseBtn, cancelPermissionsBtn].forEach(btn => {
        btn.addEventListener('click', () => permissionsModal.classList.add('hidden'));
    });
    
    savePermissionsBtn.addEventListener('click', handleSavePermissions);

    [editUserModalCloseBtn, cancelEditUserBtn].forEach(btn => {
        btn.addEventListener('click', () => {
            editUserModal.classList.add('hidden');
            currentEditingUser = null;
            editUserStatus.style.display = 'none';
        });
    });

    saveEditUserBtn.addEventListener('click', handleSaveUserEdit);
    
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
        await fetchAndStoreTags(); 
        await refreshUserList();
        await fetchDocumentsAndPermissions();
    }

    init();
});
