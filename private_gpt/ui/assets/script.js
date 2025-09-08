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
    const chatTitle = document.getElementById('chat-title');
    
    // Tagging Modal Elements
    const tagModal = document.getElementById('tag-modal');
    const tagModalCloseBtn = document.getElementById('tag-modal-close-btn');
    const availableTeamsList = document.getElementById('available-teams-list');
    const selectedTeamsList = document.getElementById('selected-teams-list');
    const cancelUploadBtn = document.getElementById('cancel-upload-btn');
    const confirmUploadBtn = document.getElementById('confirm-upload-btn');
    
    // Profile & Admin Modal Elements
    const profileBtn = document.getElementById('profile-btn');
    const profileDropdown = document.getElementById('profile-dropdown');
    const profileUsername = document.getElementById('profile-username');
    const profileRole = document.getElementById('profile-role');
    const adminPanelLink = document.getElementById('admin-panel-link');
    const profileSettingsLink = document.getElementById('profile-settings-link');
    const profileModal = document.getElementById('profile-modal');
    const profileModalCloseBtn = document.getElementById('profile-modal-close-btn');
    const profileSettingsForm = document.getElementById('profile-settings-form');
    const profileNameInput = document.getElementById('profile-name');
    const profileEmailInput = document.getElementById('profile-email');
    const profileNewPasswordInput = document.getElementById('profile-new-password');
    const profileSettingsStatus = document.getElementById('profile-settings-status');


    // --- State Variables ---
    let chatHistory = [];
    let selectedFile = null;
    let currentSessionId = null; 
    let currentMode = 'RAG';
    let isUploading = false;
    let isTyping = false;
    let inactivityTimerId = null; 
    let maxSessionAge = 0;
    let currentUsername = null;
    let pendingFilesToUpload = null;
    let allTeams = [];

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
        const sessionElement = document.querySelector(`.chat-session[data-session-id="${sessionId}"]`);
        if (sessionElement) {
            chatTitle.textContent = sessionElement.textContent;
        }


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
        chatTitle.textContent = "New Chat";
        chatInput.focus();
    }

    async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message || isTyping) return;

        const isNewChat = !currentSessionId;
        if (isNewChat) {
            chatHistory = [];
        }

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
                await refreshChatList();
                const newSessionElement = document.querySelector(`.chat-session[data-session-id="${currentSessionId}"]`);
                if (newSessionElement) {
                    chatTitle.textContent = newSessionElement.textContent;
                }
            }
        } catch (error) {
            console.error('Chat error:', error);
            showStatus('Failed to send message', 'error');
        } finally {
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
        selectedFile = listItem.textContent;
        selectedFileText.value = listItem.textContent;
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

    async function handleFileUpload(files, teams) {
        if (files.length === 0 || isUploading) return;
        isUploading = true;
    
        const fileCount = files.length;
        const statusMessage = `Uploading ${fileCount} file${fileCount > 1 ? 's' : ''}...`;
        showStatus(statusMessage, 'loading');
        
        updateUploadProgress(0);
        const formData = new FormData();
        
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
        formData.append('teams', JSON.stringify(teams));
    
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
                let errorText = 'Upload failed: Unable to get server error details.';
                try {
                    const errorResult = await response.json();
                    errorText = errorResult.detail || JSON.stringify(errorResult);
                } catch (e) {
                    errorText = await response.text();
                }
                throw new Error(errorText);
            }
        } catch (error) {
            updateUploadProgress(0);
            showStatus(error.message, 'error');
            console.error('File upload error:', error);
        } finally {
            isUploading = false;
            uploadInput.value = '';
            pendingFilesToUpload = null;
        }
    }

    async function deleteAllFiles() {
        if (!confirm("Are you sure you want to delete ALL ingested files?")) return;
        try {
            showStatus('Deleting all files...', 'loading');
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
        if (!selectedFile || !confirm(`Are you sure you want to delete ${selectedFileText.value}?`)) return;
        try {
            showStatus('Deleting file...', 'loading');
            const response = await fetch(`/api/files/${encodeURIComponent(selectedFileText.value)}`, { method: 'DELETE' });
            if (response.ok) {
                await refreshFileList();
                deselectFile();
                showStatus('File deleted', 'success');
            } else { 
                const error = await response.json();
                throw new Error(error.detail || 'Delete failed'); 
            }
        } catch (error) {
            console.error('Error deleting selected file:', error);
            showStatus(error.message, 'error');
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
            if (e.dataTransfer.files.length > 0) {
                pendingFilesToUpload = e.dataTransfer.files;
                openTeamTagModal();
            }
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
            
            currentUsername = data.username;
            profileUsername.textContent = data.display_name || data.username;
            profileRole.textContent = data.role;
            profileRole.className = `user-role ${data.role}`;

            profileNameInput.value = data.name || '';
            profileEmailInput.value = data.email || '';

            if (data.role === 'admin') {
                document.querySelectorAll('.hidden-by-role').forEach(el => {
                    el.classList.remove('hidden-by-role');
                });
                await fetchAndStoreTeams();
            }
        } catch (error) {
            console.error('Error fetching user info:', error);
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
        }
    }

    // --- Dual-List Team Selector Logic ---
    async function fetchAndStoreTeams() {
        try {
            const response = await fetch('/api/admin/teams');
            if (!response.ok) throw new Error('Failed to fetch teams');
            allTeams = await response.json();
        } catch (error) {
            console.error('Error fetching teams list:', error);
            allTeams = ['Default']; // Fallback
        }
    }

    function renderTeamSelector() {
        availableTeamsList.innerHTML = '';
        selectedTeamsList.innerHTML = '';
        allTeams.forEach(team => {
            const li = document.createElement('li');
            li.className = 'team-list-item';
            li.textContent = team;
            li.dataset.team = team;
            availableTeamsList.appendChild(li);
        });
    }
    
    function openTeamTagModal() {
        renderTeamSelector();
        tagModal.classList.remove('hidden');
    }

    function moveTeamItem(element, fromList, toList) {
        fromList.removeChild(element);
        toList.appendChild(element);
    }


    // --- Profile Settings Functions ---
    async function handleUpdateProfile(event) {
        event.preventDefault();
        const name = profileNameInput.value.trim();
        const email = profileEmailInput.value.trim();
        const new_password = profileNewPasswordInput.value;

        const body = { name, email };
        if (new_password) {
            body.new_password = new_password;
        }

        try {
            showStatus('Updating profile...', 'loading', profileSettingsStatus);
            const response = await fetch('/api/user/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            const result = await response.json();

            if (response.ok) {
                showStatus(result.message, 'success', profileSettingsStatus);
                profileNewPasswordInput.value = ''; // Clear password field
                await fetchUserInfo(); // Refresh display name in header
            } else {
                throw new Error(result.detail || 'Failed to update profile.');
            }
        } catch (error) {
            console.error('Error updating profile:', error);
            showStatus(error.message, 'error', profileSettingsStatus);
        }
    }

    // --- New Function to set App Name ---
    async function fetchAndSetAppName() {
        try {
            const response = await fetch('/api/app-name');
            if (!response.ok) throw new Error('Failed to fetch app name.');
            const data = await response.json();
            const appName = data.appName || 'DocuMind';

            // Update Title
            document.title = `${appName} - AI-Powered Document Chat`;
            
            // Update Header in Sidebar
            const headerTitle = document.getElementById('app-header-title');
            if (headerTitle) headerTitle.textContent = appName;

            // Update Welcome Message
            const welcomeHeader = document.getElementById('welcome-header');
            if (welcomeHeader) welcomeHeader.textContent = `Welcome to ${appName}`;
            
            // Update Meta Descriptions
            document.querySelector('meta[name="description"]').setAttribute('content', `Intelligent chatbot for document analysis and conversation. Upload files and get AI-powered insights with ${appName}.`);
            document.querySelector('meta[name="author"]').setAttribute('content', appName);
            document.querySelector('meta[name="keywords"]').setAttribute('content', `AI chatbot, document analysis, file upload, artificial intelligence, ${appName}`);
            document.querySelector('meta[property="og:title"]').setAttribute('content', `${appName} - AI-Powered Document Chat`);
            document.querySelector('meta[name="twitter:title"]').setAttribute('content', `${appName} - AI-Powered Document Chat`);


        } catch (error) {
            console.error('Error setting app name:', error);
        }
    }

    // --- Event Listeners ---
    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('input', () => autoResizeTextarea(chatInput));
    chatInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    
    uploadInput.addEventListener('change', e => { 
        if (e.target.files.length > 0) {
            pendingFilesToUpload = e.target.files;
            openTeamTagModal();
        }
    });

    deselectBtn.addEventListener('click', deselectFile);
    deleteAllBtn.addEventListener('click', deleteAllFiles);
    deleteSelectedBtn.addEventListener('click', deleteSelected);
    newChatBtn.addEventListener('click', startNewChat);
    clearBtn.addEventListener('click', () => clearChat(true));
    modeRadios.forEach(radio => radio.addEventListener('change', (e) => { currentMode = e.target.value; }));
    
    // Modals and Dropdowns
    if (profileSettingsForm) profileSettingsForm.addEventListener('submit', handleUpdateProfile);
    
    profileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        profileDropdown.classList.toggle('show');
    });

    if(profileSettingsLink) {
        profileSettingsLink.addEventListener('click', (e) => {
            e.preventDefault();
            profileModal.classList.remove('hidden');
            profileDropdown.classList.remove('show');
        });
    }
    
    [profileModalCloseBtn, tagModalCloseBtn, cancelUploadBtn].forEach(btn => {
        if(btn) {
            btn.addEventListener('click', () => {
                profileModal.classList.add('hidden');
                tagModal.classList.add('hidden');
                pendingFilesToUpload = null;
                uploadInput.value = ''; // Reset file input
            });
        }
    });

    [profileModal, tagModal].forEach(modal => {
        if(modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.add('hidden');
                    if (modal === tagModal) {
                        pendingFilesToUpload = null;
                        uploadInput.value = ''; // Reset file input
                    }
                }
            });
        }
    });
    
    window.addEventListener('click', (e) => {
        if (!profileDropdown.contains(e.target) && !profileBtn.contains(e.target)) {
            profileDropdown.classList.remove('show');
        }
    });
    
    if (confirmUploadBtn) {
        confirmUploadBtn.addEventListener('click', () => {
            const selectedTeamElements = selectedTeamsList.querySelectorAll('.team-list-item');
            const selectedTeams = Array.from(selectedTeamElements).map(el => el.dataset.team);
            
            if (selectedTeams.length === 0) {
                showStatus('Please select at least one team.', 'error');
                return;
            }
            if (pendingFilesToUpload) {
                tagModal.classList.add('hidden');
                handleFileUpload(pendingFilesToUpload, selectedTeams);
            }
        });
    }

    availableTeamsList.addEventListener('click', e => {
        if (e.target.classList.contains('team-list-item')) {
            moveTeamItem(e.target, availableTeamsList, selectedTeamsList);
        }
    });

    selectedTeamsList.addEventListener('click', e => {
        if (e.target.classList.contains('team-list-item')) {
            moveTeamItem(e.target, selectedTeamsList, availableTeamsList);
        }
    });

    // --- Initialization ---
    manageTheme();
    setupDragAndDrop();
    refreshFileList();
    autoResizeTextarea(chatInput);
    chatInput.focus();
    fetchUserInfo();
    setupSessionTimeout();
    loadInitialChat();
    fetchAndSetAppName();
});

