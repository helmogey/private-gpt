document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatbot = document.getElementById('chatbot');
    const fileList = document.getElementById('file-list');
    const uploadInput = document.getElementById('upload-input');
    const uploadZone = document.getElementById('upload-zone');
    const uploadStatus = document.getElementById('upload-status');
    const uploadProgress = document.getElementById('upload-progress');
    const uploadProgressBar = document.getElementById('upload-progress-bar');
    const selectedFileText = document.getElementById('selected-file-text');
    const deselectBtn = document.getElementById('deselect-btn');
    const deleteSelectedBtn = document.getElementById('delete-selected-btn');
    const deleteAllBtn = document.getElementById('delete-all-btn');
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const welcomeMessage = document.getElementById('welcome-message');
    const clearBtn = document.getElementById('clear-btn');
    const modeRadios = document.querySelectorAll('input[name="mode"]');
    const chatList = document.getElementById('chat-list');
    const newChatBtn = document.getElementById('new-chat-btn');
    const createUserForm = document.getElementById('create-user-form');
    const newUsernameInput = document.getElementById('new-username');
    const newPasswordInput = document.getElementById('new-password');
    const newUserRoleSelect = document.getElementById('new-user-role');
    const createUserStatus = document.getElementById('create-user-status');
    const userList = document.getElementById('user-list');
    
    // Profile & Admin Modal Elements
    const profileBtn = document.getElementById('profile-btn');
    const profileDropdown = document.getElementById('profile-dropdown');
    const profileUsername = document.getElementById('profile-username');
    const profileRole = document.getElementById('profile-role');
    const adminPanelLink = document.getElementById('admin-panel-link');
    const adminModal = document.getElementById('admin-modal');
    const adminModalCloseBtn = document.getElementById('admin-modal-close-btn');


    // --- State Variables ---
    let chatHistory = [];
    let selectedFile = null;
    let currentSessionId = null; 
    let currentMode = 'RAG';
    let isUploading = false;
    let isTyping = false;
    let inactivityTimerId = null; 
    let maxSessionAge = 0; 

    // --- Utility Functions ---
    function autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 128) + 'px';
    }

    function showStatus(message, type = 'info', element = uploadStatus) {
        element.textContent = message;
        element.className = `upload-status ${type}`;
        element.style.display = 'block';
        if (type !== 'loading') {
            setTimeout(() => { element.style.display = 'none'; }, 3000);
        }
    }

    function updateUploadProgress(percent) {
        uploadProgress.classList.toggle('visible', percent > 0 && percent < 100);
        uploadProgressBar.style.width = `${percent}%`;
    }

    function setButtonLoading(button, loading) {
        button.classList.toggle('loading', loading);
        button.disabled = loading;
    }

    // --- Core Chat Functions ---
    function appendMessage(sender, message) {
        if (welcomeMessage) welcomeMessage.style.display = 'none';

        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message-bubble', sender);

        const avatar = document.createElement('div');
        avatar.classList.add('message-avatar', sender);
        avatar.innerHTML = sender === 'user' ? 
            `<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M12 4a4 4 0 0 1 4 4 4 4 0 0 1-4 4 4 4 0 0 1-4-4 4 4 0 0 1 4-4m0 10c4.42 0 8 1.79 8 4v2H4v-2c0-2.21 3.58-4 8-4Z"/></svg>` :
            `<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M17.753 14a2.25 2.25 0 0 1 2.25 2.25v.905a3.75 3.75 0 0 1-1.307 2.846C17.13 21.345 14.89 22 12 22c-2.89 0-5.13-.655-6.696-2A3.75 3.75 0 0 1 4 17.155v-.905A2.25 2.25 0 0 1 6.247 14h11.506ZM12 2.25A3.75 3.75 0 0 1 15.75 6v1.5A3.75 3.75 0 0 1 12 11.25 3.75 3.75 0 0 1 8.25 7.5V6A3.75 3.75 0 0 1 12 2.25Z"/></svg>`;

        const content = document.createElement('div');
        content.classList.add('message-content', sender);
        
        content.innerHTML = message.replace(/\n/g, '<br>');
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);

        chatbot.appendChild(messageDiv);
        chatbot.scrollTop = chatbot.scrollHeight;
        
        return messageDiv;
    }
    
    function showTypingIndicator() {
        if (isTyping) return;
        isTyping = true;
        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        typingDiv.classList.add('typing-indicator');
        typingDiv.innerHTML = `
            <div class="message-avatar bot"><svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M17.753 14a2.25 2.25 0 0 1 2.25 2.25v.905a3.75 3.75 0 0 1-1.307 2.846C17.13 21.345 14.89 22 12 22c-2.89 0-5.13-.655-6.696-2A3.75 3.75 0 0 1 4 17.155v-.905A2.25 2.25 0 0 1 6.247 14h11.506ZM12 2.25A3.75 3.75 0 0 1 15.75 6v1.5A3.75 3.75 0 0 1 12 11.25 3.75 3.75 0 0 1 8.25 7.5V6A3.75 3.75 0 0 1 12 2.25Z"/></svg></div>
            <div class="typing-content"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>`;
        chatbot.appendChild(typingDiv);
        chatbot.scrollTop = chatbot.scrollHeight;
    }

    function hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
        isTyping = false;
    }

    async function refreshChatList() {
        chatList.innerHTML = '';
        try {
            const response = await fetch('/api/chats');
            if (!response.ok) throw new Error('Failed to fetch chats.');
            const sessions = await response.json();
            sessions.forEach(session => {
                const li = document.createElement('li');
                li.className = 'chat-session';
                li.textContent = session.name || 'Untitled Chat';
                li.dataset.sessionId = session.session_id;
                if (session.session_id === currentSessionId) li.classList.add('active');
                li.addEventListener('click', () => switchChatSession(session.session_id));
                chatList.appendChild(li);
            });
        } catch (error) {
            console.error('Error refreshing chat list:', error);
            showStatus('Failed to load chats', 'error');
        }
    }

    async function switchChatSession(sessionId) {
        if (currentSessionId === sessionId) return;

        currentSessionId = sessionId;
        chatHistory = [];
        clearChat(false);

        document.querySelectorAll('#chat-list .chat-session').forEach(li => {
            li.classList.toggle('active', li.dataset.sessionId === sessionId);
        });

        try {
            const response = await fetch(`/api/chat/history/${sessionId}`);
            const data = await response.json();
            if (data.history) {
                chatHistory = data.history;
                data.history.forEach(msg => {
                    const sender = msg.role === 'assistant' ? 'bot' : 'user';
                    appendMessage(sender, msg.content);
                });
            }
        } catch (error) {
            console.error('Error fetching history for session:', sessionId, error);
            showStatus('Could not load chat history.', 'error');
        }
    }
    
    function startNewChat() {
        currentSessionId = null;
        chatHistory = [];
        clearChat(false);
        document.querySelectorAll('#chat-list .chat-session.active').forEach(li => li.classList.remove('active'));
        chatInput.focus();
    }

    async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message || isTyping) return;

        const isNewChat = !currentSessionId;
        if (isNewChat) {
            chatHistory = [];
        }

        // Pause the session inactivity timer while the model is thinking.
        clearTimeout(inactivityTimerId);

        appendMessage('user', message);
        chatHistory.push({ role: 'user', content: message });
        
        chatInput.value = '';
        autoResizeTextarea(chatInput);

        setButtonLoading(sendBtn, true);
        showTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: chatHistory,
                    mode: currentMode,
                    context_filter: selectedFile ? { docs_ids: [selectedFile] } : null,
                    session_id: currentSessionId
                }),
            });
             if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            let botMessageElement = null;
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let botReply = '';
            let sources = [];
            let newSessionIdReceived = null;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                chunk.split('\n\n').forEach(line => {
                    if (line.startsWith('data: ')) {
                        const dataPart = line.substring(6);
                        if (!dataPart) return;
                        try {
                            const parsed = JSON.parse(dataPart);
                            if (parsed.delta) {
                                // FIX: On the first response chunk, remove the typing indicator
                                // and create the message bubble. This prevents duplicate bubbles.
                                if (!botMessageElement) {
                                    hideTypingIndicator();
                                    botMessageElement = appendMessage('bot', '');
                                }
                                botReply += parsed.delta;
                                botMessageElement.querySelector('.message-content').innerHTML = botReply.replace(/\n/g, '<br>');
                            }
                            if (parsed.sources) sources = parsed.sources;
                            if (parsed.session_id && isNewChat) newSessionIdReceived = parsed.session_id;
                        } catch (e) { console.error('Error parsing streaming data:', e); }
                    }
                });
                chatbot.scrollTop = chatbot.scrollHeight;
            }

            if (sources.length > 0) {
                if (!botMessageElement) {
                    hideTypingIndicator();
                    botMessageElement = appendMessage('bot', '');
                }
                let sourcesHtml = `<div class="message-sources"><div class="sources-title">Sources</div>`;
                sources.forEach(s => {
                    sourcesHtml += `<div class="source-item"><div class="source-file">${s.file} (Page ${s.page})</div><div class="source-text">${s.text.substring(0, 100)}...</div></div>`;
                });
                sourcesHtml += '</div>';
                botMessageElement.querySelector('.message-content').innerHTML += sourcesHtml;
            }
            
            chatHistory.push({ role: 'assistant', content: botReply });

            if (newSessionIdReceived) {
                currentSessionId = newSessionIdReceived;
                setTimeout(async () => {
                    await refreshChatList();
                }, 250);
            }
        } catch (error) {
            console.error('Chat error:', error);
            showStatus('Failed to send message', 'error');
        } finally {
            // This block ensures cleanup happens regardless of success or error.
            hideTypingIndicator();
            setButtonLoading(sendBtn, false);
            resetSessionTimeout();
        }
    }

    // --- File Management Functions ---
    async function refreshFileList() {
        try {
            const response = await fetch('/api/files');
            if (!response.ok) throw new Error('Failed to fetch files.');
            const files = await response.json();
            fileList.innerHTML = '';
            files.forEach(fileRow => {
                const li = document.createElement('li');
                li.textContent = fileRow[0];
                li.dataset.filename = fileRow[0];
                li.addEventListener('click', () => handleFileSelection(li));
                fileList.appendChild(li);
            });
        } catch (error) {
            console.error('Error refreshing file list:', error);
            showStatus('Failed to refresh file list', 'error');
        }
    }

    function handleFileSelection(listItem) {
        const current = fileList.querySelector('.selected');
        if (current) current.classList.remove('selected');
        listItem.classList.add('selected');
        selectedFile = listItem.dataset.filename;
        selectedFileText.value = selectedFile;
        deselectBtn.disabled = false;
        deleteSelectedBtn.disabled = false;
    }
    
    function deselectFile() {
        const current = fileList.querySelector('.selected');
        if (current) current.classList.remove('selected');
        selectedFile = null;
        selectedFileText.value = "All files";
        deselectBtn.disabled = true;
        deleteSelectedBtn.disabled = true;
    }

     async function handleFileUpload(files) {
        if (files.length === 0 || isUploading) return;
        isUploading = true;
    
        const fileCount = files.length;
        const statusMessage = `Uploading ${fileCount} file${fileCount > 1 ? 's' : ''}...`;
        showStatus(statusMessage, 'loading');
        
        updateUploadProgress(0);
        const formData = new FormData();
        
        // Loop through all selected files and append them to FormData
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
    
        try {
            let progress = 0;
            const interval = setInterval(() => {
                progress = Math.min(progress + Math.random() * 10, 90);
                updateUploadProgress(progress);
            }, 500);
    
            const response = await fetch('/api/upload', { method: 'POST', body: formData });
            clearInterval(interval);
            updateUploadProgress(100);
    
            if (response.ok) {
                const result = await response.json();
                setTimeout(() => {
                    showStatus(result.message || 'Upload successful!', 'success');
                    updateUploadProgress(0);
                    refreshFileList();
                }, 500);
            } else { 
                // Enhanced error handling for non-JSON responses
                let errorText = 'Upload failed: Unable to get server error details.';
                try {
                    // Try to parse as JSON first, as that's the expected format for FastAPI errors
                    const errorResult = await response.json();
                    errorText = errorResult.detail || JSON.stringify(errorResult);
                } catch (e) {
                    // If JSON parsing fails, the response is likely plain text or HTML (e.g., a server crash page)
                    errorText = await response.text();
                }
                throw new Error(errorText);
            }
        } catch (error) {
            updateUploadProgress(0);
            // Display the more specific error message from the catch block
            showStatus(error.message, 'error');
            console.error('File upload error:', error);
        } finally {
            isUploading = false;
            uploadInput.value = ''; // Clear input to allow re-uploading same files
        }
    }


    async function deleteAllFiles() {
        if (!confirm("Are you sure you want to delete ALL ingested files?")) return;
        try {
            const response = await fetch('/api/files', { method: 'DELETE' });
            if (response.ok) {
                await refreshFileList();
                deselectFile();
                showStatus('All files deleted', 'success');
            } else { throw new Error('Delete failed'); }
        } catch (error) {
            console.error('Error deleting all files:', error);
            showStatus('Failed to delete files', 'error');
        }
    }

    async function deleteSelected() {
        if (!selectedFile || !confirm(`Are you sure you want to delete ${selectedFile}?`)) return;
        try {
            const response = await fetch(`/api/files/${selectedFile}`, { method: 'DELETE' });
            if (response.ok) {
                await refreshFileList();
                deselectFile();
                showStatus('File deleted', 'success');
            } else { throw new Error('Delete failed'); }
        } catch (error) {
            console.error('Error deleting selected file:', error);
            showStatus('Failed to delete file', 'error');
        }
    }

    // --- UI Enhancement & Role Management ---
    window.toggleAccordion = function(header) {
        header.classList.toggle('collapsed');
        header.nextElementSibling.classList.toggle('collapsed');
    };

    function setupDragAndDrop() {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, e => e.preventDefault());
        });
        uploadZone.addEventListener('dragover', () => uploadZone.classList.add('drag-over'));
        uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
        uploadZone.addEventListener('drop', e => {
            uploadZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files);
        });
        uploadZone.addEventListener('click', () => { if (!isUploading) uploadInput.click(); });
    }

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
            
            // Update profile dropdown
            profileUsername.textContent = data.username;
            profileRole.textContent = data.role;
            profileRole.className = `user-role ${data.role}`;

            if (data.role === 'admin') {
                // If user is admin, reveal all admin-only elements
                document.querySelectorAll('.hidden-by-role').forEach(el => {
                    el.classList.remove('hidden-by-role');
                });
                await refreshUserList(); // Fetch users for the admin panel
            } else {
                // For regular users, hide upload, file actions, and settings
                const uploadControls = document.getElementById('upload-controls');
                const fileActionControls = document.getElementById('file-action-controls');
                const chatSettingsSection = document.getElementById('chat-settings-section');

                if (uploadControls) uploadControls.style.display = 'none';
                if (fileActionControls) fileActionControls.style.display = 'none';
                if (chatSettingsSection) chatSettingsSection.style.display = 'none';
            }
        } catch (error) {
            console.error('Error fetching user info:', error);
            // On error, hide sensitive controls as a security precaution
            const uploadControls = document.getElementById('upload-controls');
            const fileActionControls = document.getElementById('file-action-controls');
            const chatSettingsSection = document.getElementById('chat-settings-section');
            if (uploadControls) uploadControls.style.display = 'none';
            if (fileActionControls) fileActionControls.style.display = 'none';
            if (chatSettingsSection) chatSettingsSection.style.display = 'none';
        }
    }

    // --- Session Management & Init ---
    function resetSessionTimeout() {
        clearTimeout(inactivityTimerId);
        if (maxSessionAge > 0) {
            inactivityTimerId = setTimeout(() => {
                showStatus('Session expired due to inactivity, logging out...', 'info');
                setTimeout(() => { window.location.href = '/logout'; }, 1500);
            }, maxSessionAge * 1000);
        }
    }

    async function setupSessionTimeout() {
        try {
            const response = await fetch('/api/session/expiry');
            if (!response.ok) return;
            const data = await response.json();
            maxSessionAge = data.max_age;
            resetSessionTimeout();
            ['mousemove', 'keydown', 'click'].forEach(eventName => {
                document.addEventListener(eventName, resetSessionTimeout);
            });
        } catch (error) {
            console.error('Error setting up session timeout:', error);
        }
    }
    
	async function loadInitialChat() {
        await refreshChatList();
        const firstChat = chatList.querySelector('.chat-session');
        if (firstChat) {
            switchChatSession(firstChat.dataset.sessionId);
        } else {
            startNewChat();
        }
    }
    
    function clearChat(showStatusMsg = true) {
        chatbot.innerHTML = '';
        chatbot.appendChild(welcomeMessage);
        welcomeMessage.style.display = 'flex';
        if (showStatusMsg) { 
            chatHistory = [];
            showStatus('Chat cleared', 'info');
        }
    }

    // --- Admin Panel Functions ---
    async function refreshUserList() {
        try {
            const response = await fetch('/api/admin/users');
            if (!response.ok) {
                throw new Error(`Failed to fetch users: ${response.statusText}`);
            }
            const users = await response.json();
            userList.innerHTML = ''; // Clear existing list
            users.forEach(user => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <span>${user.username}</span>
                    <span class="user-role ${user.role}">${user.role}</span>
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

        if (!username || !password) {
            showStatus('Username and password are required.', 'error', createUserStatus);
            return;
        }

        try {
            showStatus('Creating user...', 'loading', createUserStatus);
            const response = await fetch('/api/admin/create-user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, role }),
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

    // --- Event Listeners ---
    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('input', () => autoResizeTextarea(chatInput));
    chatInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    uploadInput.addEventListener('change', e => { if (e.target.files.length > 0) handleFileUpload(e.target.files); });
    deselectBtn.addEventListener('click', deselectFile);
    deleteAllBtn.addEventListener('click', deleteAllFiles);
    deleteSelectedBtn.addEventListener('click', deleteSelected);
    newChatBtn.addEventListener('click', startNewChat);
    clearBtn.addEventListener('click', () => clearChat(true));
    modeRadios.forEach(radio => radio.addEventListener('change', (e) => { currentMode = e.target.value; }));
    if(createUserForm) {
        createUserForm.addEventListener('submit', handleCreateUser);
    }
    
    profileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        profileDropdown.classList.toggle('show');
    });

    adminPanelLink.addEventListener('click', (e) => {
        e.preventDefault();
        adminModal.classList.remove('hidden');
        profileDropdown.classList.remove('show');
    });

    adminModalCloseBtn.addEventListener('click', () => {
        adminModal.classList.add('hidden');
    });

    adminModal.addEventListener('click', (e) => {
        if (e.target === adminModal) {
            adminModal.classList.add('hidden');
        }
    });
    
    window.addEventListener('click', (e) => {
        if (!profileDropdown.contains(e.target) && !profileBtn.contains(e.target)) {
            profileDropdown.classList.remove('show');
        }
    });

    // --- Initialization ---
    manageTheme();
    setupDragAndDrop();
    refreshFileList();
    autoResizeTextarea(chatInput);
    chatInput.focus();
    fetchUserInfo(); // Changed from fetchUserRole
    setupSessionTimeout();
    loadInitialChat();
});

