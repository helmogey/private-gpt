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
    
    const chatCategorySelect = document.getElementById('chat-category-select');
    
    // [NEW] Zabbix DOM Elements
    const zabbixHealthBtn = document.getElementById('zabbix-health-btn');
    const zabbixTimeRange = document.getElementById('zabbix-time-range');
    const zabbixCustomDatesContainer = document.getElementById('zabbix-custom-dates');

    const tagModal = document.getElementById('tag-modal');
    const tagModalCloseBtn = document.getElementById('tag-modal-close-btn');
    
    const availableTeamsList = document.getElementById('available-teams-list');
    const selectedTeamsList = document.getElementById('selected-teams-list');
    const availableTagsList = document.getElementById('available-tags-list');
    const selectedTagsList = document.getElementById('selected-tags-list');
    
    const cancelUploadBtn = document.getElementById('cancel-upload-btn');
    const confirmUploadBtn = document.getElementById('confirm-upload-btn');
    
    const profileBtn = document.getElementById('profile-btn');
    const profileDropdown = document.getElementById('profile-dropdown');
    const profileUsername = document.getElementById('profile-username');
    const profileRole = document.getElementById('profile-role');
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

    // --- Utility Functions ---
    function autoResizeTextarea(textarea) {
        if (!textarea) return;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 128) + 'px';
    }

    function showStatus(message, type = 'info', element = uploadStatus) {
        if (!element) return;
        element.textContent = message;
        element.className = `upload-status ${type}`;
        element.style.display = 'block';
        if (type !== 'loading') {
            setTimeout(() => { element.style.display = 'none'; }, 3000);
        }
    }

    function updateUploadProgress(percent) {
        if (!uploadProgress || !uploadProgressBar) return;
        uploadProgress.classList.toggle('visible', percent > 0 && percent < 100);
        uploadProgressBar.style.width = `${percent}%`;
    }

    function setButtonLoading(button, loading) {
        if (!button) return;
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
        if (!chatList) return;
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
        if (sessionElement && chatTitle) {
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
        if (chatTitle) chatTitle.textContent = "New Chat";
        if (chatInput) chatInput.focus();
    }

    // [MODIFIED] Added zabbix date range parameters
    async function sendMessage(triggerToolFlag = null, hiddenMessageText = null, zabbixTimeFrom = null, zabbixTimeTill = null) {
        const message = hiddenMessageText !== null ? hiddenMessageText : chatInput.value.trim();
        if (!message || isTyping) return;

        const isNewChat = !currentSessionId;
        if (isNewChat) {
            chatHistory = [];
        }

        const selectedCategory = chatCategorySelect ? chatCategorySelect.value : 'Default';

        clearTimeout(inactivityTimerId);
        appendMessage('user', message);
        chatHistory.push({ role: 'user', content: message });
        
        if (!triggerToolFlag) {
            chatInput.value = '';
            autoResizeTextarea(chatInput);
        }

        setButtonLoading(sendBtn, true);
        if (zabbixHealthBtn) setButtonLoading(zabbixHealthBtn, true);
        showTypingIndicator();

        try {
            const payload = {
                messages: chatHistory,
                mode: currentMode,
                context_filter: selectedFile ? { docs_ids: [selectedFile] } : null,
                session_id: currentSessionId,
                category: selectedCategory 
            };

            if (triggerToolFlag) {
                payload.trigger_tool = triggerToolFlag;
            }
            if (zabbixTimeFrom) {
                payload.zabbix_time_from = zabbixTimeFrom;
            }
            if (zabbixTimeTill) {
                payload.zabbix_time_till = zabbixTimeTill;
            }

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
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
                if (newSessionElement && chatTitle) {
                    chatTitle.textContent = newSessionElement.textContent;
                }
            }
        } catch (error) {
            console.error('Chat error:', error);
            showStatus('Failed to send message', 'error');
        } finally {
            hideTypingIndicator();
            setButtonLoading(sendBtn, false);
            if (zabbixHealthBtn) setButtonLoading(zabbixHealthBtn, false);
            resetSessionTimeout();
        }
    }

    // --- File Management Functions ---
    async function refreshFileList() {
        if (!fileList) return;
        try {
            const response = await fetch('/api/files');
            if (!response.ok) throw new Error('Failed to fetch files.');
            const files = await response.json();
            fileList.innerHTML = '';
            
            files.forEach(fileRow => {
                const fileName = fileRow[0];
                const li = document.createElement('li');

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'file-checkbox hidden-by-role';
                checkbox.value = fileName;
                checkbox.addEventListener('click', (e) => e.stopPropagation()); 

                const nameSpan = document.createElement('span');
                nameSpan.className = 'file-item-name';
                nameSpan.textContent = fileName;
                nameSpan.title = fileName; 

                const delBtn = document.createElement('button');
                delBtn.className = 'file-item-delete hidden-by-role';
                delBtn.title = "Delete this file";
                delBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z"/></svg>`;
                delBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteSingleFile(fileName);
                });

                li.appendChild(checkbox);
                li.appendChild(nameSpan);
                li.appendChild(delBtn);

                li.addEventListener('click', () => handleFileSelection(li, fileName));
                fileList.appendChild(li);
            });

            if (selectedFile) {
                const items = Array.from(fileList.children);
                const stillExists = items.find(li => li.querySelector('.file-item-name').textContent === selectedFile);
                if (stillExists) stillExists.classList.add('selected');
                else deselectFile();
            }

            fetchUserInfo(); 
        } catch (error) {
            console.error('Error refreshing file list:', error);
            showStatus('Failed to refresh file list', 'error');
        }
    }

    function handleFileSelection(listItem, overrideFileName) {
        const current = fileList.querySelector('.selected');
        if (current) current.classList.remove('selected');
        listItem.classList.add('selected');
        
        selectedFile = overrideFileName;
        
        if (selectedFileText) {
            selectedFileText.value = selectedFile;
        }
        
        if (deselectBtn) deselectBtn.disabled = false;
    }
    
    function deselectFile() {
        if (!fileList) return;
        const current = fileList.querySelector('.selected');
        if (current) current.classList.remove('selected');
        selectedFile = null;
        if (selectedFileText) {
            selectedFileText.value = "All files";
        }
        if (deselectBtn) deselectBtn.disabled = true;
    }

    async function handleFileUpload(files, teams, tags) {
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
        formData.append('tags', JSON.stringify(tags));
    
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
            if (uploadInput) uploadInput.value = '';
            pendingFilesToUpload = null;
        }
    }

    async function deleteSingleFile(fileName) {
        const result = await Swal.fire({
            title: 'Delete Document?',
            text: `Are you sure you want to delete "${fileName}"?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: 'hsl(0, 72.2%, 50.6%)',
            confirmButtonText: 'Yes, delete it!'
        });

        if (result.isConfirmed) {
            try {
                showStatus('Deleting file...', 'loading');
                const response = await fetch(`/api/files/${encodeURIComponent(fileName)}`, { method: 'DELETE' });
                if (response.ok) {
                    await refreshFileList();
                    if(selectedFile === fileName) deselectFile();
                    Swal.fire('Deleted!', 'Your file has been deleted.', 'success');
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || 'Delete failed');
                }
            } catch (error) {
                Swal.fire('Error', error.message, 'error');
            }
        }
    }

    async function deleteSelected() {
        const checkboxes = document.querySelectorAll('.file-checkbox:checked');
        if (checkboxes.length === 0) {
            Swal.fire('No files selected', 'Please check the boxes next to the files you want to delete.', 'info');
            return;
        }

        const result = await Swal.fire({
            title: 'Delete Selected Files?',
            text: `You are about to delete ${checkboxes.length} file(s). This cannot be undone.`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: 'hsl(0, 72.2%, 50.6%)',
            confirmButtonText: 'Yes, delete them!'
        });

        if (result.isConfirmed) {
            try {
                showStatus('Deleting files...', 'loading');
                for (let box of checkboxes) {
                    await fetch(`/api/files/${encodeURIComponent(box.value)}`, { method: 'DELETE' });
                    if(selectedFile === box.value) deselectFile();
                }
                await refreshFileList();
                Swal.fire('Deleted!', 'Selected files have been deleted.', 'success');
            } catch (error) {
                Swal.fire('Error', 'Some files could not be deleted.', 'error');
            }
        }
    }

    async function deleteAllFiles() {
        const result = await Swal.fire({
            title: 'Delete ALL Files?',
            text: "Are you sure? This will remove all ingested documents!",
            icon: 'error',
            showCancelButton: true,
            confirmButtonColor: 'hsl(0, 72.2%, 50.6%)',
            confirmButtonText: 'Yes, wipe everything!'
        });

        if (result.isConfirmed) {
            try {
                showStatus('Deleting all files...', 'loading');
                const response = await fetch('/api/files', { method: 'DELETE' });
                if (response.ok) {
                    await refreshFileList();
                    deselectFile();
                    Swal.fire('Deleted!', 'All files have been deleted.', 'success');
                } else { throw new Error('Delete failed'); }
            } catch (error) {
                Swal.fire('Error', 'Failed to delete files', 'error');
            }
        }
    }

    // --- UI Enhancement & Role Management ---
    window.toggleAccordion = function(header) {
        if (!header || !header.nextElementSibling) return;
        header.classList.toggle('collapsed');
        header.nextElementSibling.classList.toggle('collapsed');
    };

    async function openUploadModal() {
        const [teams, tags] = await Promise.all([fetchTeams(), fetchTags()]);
        
        setupSelector(availableTeamsList, selectedTeamsList, teams);
        setupSelector(availableTagsList, selectedTagsList, tags);
        
        if (tagModal) tagModal.classList.remove('hidden');
    }

    function setupDragAndDrop() {
        if (!uploadZone) return;
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, e => e.preventDefault());
        });
        uploadZone.addEventListener('dragover', () => uploadZone.classList.add('drag-over'));
        uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
        uploadZone.addEventListener('drop', async e => {
            uploadZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                pendingFilesToUpload = e.dataTransfer.files;
                await openUploadModal();
            }
        });
        uploadZone.addEventListener('click', async () => { 
            if (!isUploading && uploadInput) {
                uploadInput.click();
            }
        });
    }

    function manageTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        if (savedTheme === 'dark') document.body.classList.add('dark');
        if (themeToggleBtn) {
            themeToggleBtn.addEventListener('click', () => {
                document.body.classList.toggle('dark');
                localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
            });
        }
    }

    async function fetchUserInfo() {
        try {
            const response = await fetch('/api/user/info');
            if (!response.ok) throw new Error('Failed to fetch user info.');
            const data = await response.json();
            
            currentUsername = data.username;
            if (profileUsername) profileUsername.textContent = data.display_name || data.username;
            if (profileRole) {
                profileRole.textContent = data.role;
                profileRole.className = `user-role ${data.role}`;
            }

            if (profileNameInput) profileNameInput.value = data.name || '';
            if (profileEmailInput) profileEmailInput.value = data.email || '';

            if (data.role === 'admin') {
                document.querySelectorAll('.hidden-by-role').forEach(el => {
                    el.classList.remove('hidden-by-role');
                });
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
        if (chatList) {
            const firstChat = chatList.querySelector('.chat-session');
            if (firstChat) {
                switchChatSession(firstChat.dataset.sessionId);
            } else {
                startNewChat();
            }
        }
    }
    
    function clearChat(showStatusMsg = true) {
        if (chatbot && welcomeMessage) {
            chatbot.innerHTML = '';
            chatbot.appendChild(welcomeMessage);
            welcomeMessage.style.display = 'flex';
        }
        if (showStatusMsg) { 
            chatHistory = [];
        }
    }

    // --- List Selector Logic (Shared for Teams & Tags) ---
    async function fetchTeams() {
        try {
            const response = await fetch('/api/admin/teams');
            if (!response.ok) throw new Error('Failed to fetch teams');
            return await response.json();
        } catch (error) {
            console.error('Error fetching teams:', error);
            return ['Default'];
        }
    }

    async function fetchTags() {
        try {
            const response = await fetch('/api/tags');
            if (!response.ok) throw new Error('Failed to fetch tags');
            return await response.json();
        } catch (error) {
            console.error('Error fetching tags:', error);
            return ['GENERAL', 'EMPLOYEE', 'SERVER', 'ZABBIX']; // Fallback
        }
    }

    function setupSelector(availableList, selectedList, items) {
        if (!availableList || !selectedList) return;
        availableList.innerHTML = '';
        selectedList.innerHTML = '';
        items.forEach(item => {
            const li = document.createElement('li');
            li.className = 'team-list-item'; 
            li.textContent = item;
            li.dataset.value = item;
            availableList.appendChild(li);
        });
    }

    function moveItem(element, fromList, toList) {
        fromList.removeChild(element);
        toList.appendChild(element);
    }

    async function populateChatCategories() {
        if (!chatCategorySelect) return;
        
        try {
            const tags = await fetchTags();
            chatCategorySelect.innerHTML = '<option value="Default" selected>Default (Auto-Detect)</option>';
            
            tags.forEach(tag => {
                const option = document.createElement('option');
                option.value = tag;
                option.textContent = tag;
                chatCategorySelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error populating chat categories:', error);
        }
    }

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
                profileNewPasswordInput.value = ''; 
                await fetchUserInfo(); 
            } else {
                throw new Error(result.detail || 'Failed to update profile.');
            }
        } catch (error) {
            console.error('Error updating profile:', error);
            showStatus(error.message, 'error', profileSettingsStatus);
        }
    }

	async function fetchAndSetBranding() {
        try {
            const response = await fetch('/api/branding');
            if (!response.ok) throw new Error('Failed to fetch branding info.');
            const data = await response.json();
            const appName = data.appName || 'DocuMind';
            const logoUrl = data.logoUrl || '/assets/NEC-Logo.svg';

            const logoIconContainer = document.getElementById('logo-icon-container');
            const welcomeIconContainer = document.getElementById('welcome-icon-container');
            const favicon = document.getElementById('favicon');
            
            document.title = `${appName} - AI-Powered Document Chat`;
            const appHeaderTitle = document.getElementById('app-header-title');
            if(appHeaderTitle) appHeaderTitle.textContent = appName;
            
            const welcomeHeader = document.getElementById('welcome-header');
            if(welcomeHeader) welcomeHeader.textContent = `Welcome to`;
            
            const welcomeAppName = document.getElementById('welcome-app-name');
            if(welcomeAppName) welcomeAppName.textContent = appName;
            
            if (favicon) {
                favicon.href = logoUrl;
            }

            if (logoIconContainer) {
                const logoImg = document.createElement('img');
                logoImg.src = logoUrl;
                logoImg.alt = `${appName} Logo`;
                logoIconContainer.innerHTML = '';
                logoIconContainer.appendChild(logoImg);
            }

            if (welcomeIconContainer) {
                const welcomeLogoImg = document.createElement('img');
                welcomeLogoImg.src = logoUrl;
                welcomeLogoImg.alt = `${appName} Logo`;
                welcomeIconContainer.innerHTML = '';
                welcomeIconContainer.appendChild(welcomeLogoImg);
            }
            
        } catch (error) {
            console.error('Error setting app branding:', error);
        }
    }
    
    // --- Event Listeners ---
    if (sendBtn) sendBtn.addEventListener('click', () => sendMessage());
    
    if (chatInput) {
        chatInput.addEventListener('input', () => autoResizeTextarea(chatInput));
        chatInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    }
    
    // [NEW] Event Listener for Zabbix Health Intercept Calendar Logic
    if (zabbixTimeRange && zabbixCustomDatesContainer) {
        zabbixTimeRange.addEventListener('change', (e) => {
            if (e.target.value === 'custom') {
                zabbixCustomDatesContainer.style.display = 'flex';
            } else {
                zabbixCustomDatesContainer.style.display = 'none';
            }
        });
    }

    if (zabbixHealthBtn) {
        zabbixHealthBtn.addEventListener('click', () => {
            let timeFrom = null;
            let timeTill = null;
            let rangeText = "the selected date range";

            if (zabbixTimeRange && zabbixTimeRange.value === 'custom') {
                const fromInput = document.getElementById('zabbix-custom-from').value;
                const toInput = document.getElementById('zabbix-custom-to').value;
                
                if (fromInput) {
                    timeFrom = Math.floor(new Date(fromInput).getTime() / 1000);
                    rangeText = `from ${fromInput}`;
                }
                if (toInput) {
                    // Set to end of the selected day
                    const toObj = new Date(toInput);
                    toObj.setHours(23, 59, 59, 999);
                    timeTill = Math.floor(toObj.getTime() / 1000);
                    rangeText += ` to ${toInput}`;
                }
            } else if (zabbixTimeRange) {
                const days = parseInt(zabbixTimeRange.value) || 30;
                timeFrom = Math.floor(Date.now() / 1000) - (days * 86400);
                rangeText = `the last ${days} days`;
            }
            
            sendMessage("zabbix_health_check", `🔍 Run Zabbix Health Check (${rangeText})`, timeFrom, timeTill);
        });
    }

    if (uploadInput) {
        uploadInput.addEventListener('change', async e => { 
            if (e.target.files.length > 0) {
                pendingFilesToUpload = e.target.files;
                await openUploadModal();
            }
        });
    }

    if (deselectBtn) deselectBtn.addEventListener('click', deselectFile);
    if (deleteAllBtn) deleteAllBtn.addEventListener('click', deleteAllFiles);
    if (deleteSelectedBtn) deleteSelectedBtn.addEventListener('click', deleteSelected);
    if (newChatBtn) newChatBtn.addEventListener('click', startNewChat);
    if (clearBtn) clearBtn.addEventListener('click', () => clearChat(true));
    modeRadios.forEach(radio => radio.addEventListener('change', (e) => { currentMode = e.target.value; }));
    
    // Modals and Dropdowns
    if (profileSettingsForm) profileSettingsForm.addEventListener('submit', handleUpdateProfile);
    
    if (profileBtn && profileDropdown) {
        profileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            profileDropdown.classList.toggle('show');
        });
    }

    if(profileSettingsLink && profileModal && profileDropdown) {
        profileSettingsLink.addEventListener('click', (e) => {
            e.preventDefault();
            profileModal.classList.remove('hidden');
            profileDropdown.classList.remove('show');
        });
    }
    
    [profileModalCloseBtn, tagModalCloseBtn, cancelUploadBtn].forEach(btn => {
        if(btn) {
            btn.addEventListener('click', () => {
                if (profileModal) profileModal.classList.add('hidden');
                if (tagModal) tagModal.classList.add('hidden');
                pendingFilesToUpload = null;
                if (uploadInput) uploadInput.value = '';
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
                        if (uploadInput) uploadInput.value = '';
                    }
                }
            });
        }
    });
    
    window.addEventListener('click', (e) => {
        if (profileDropdown && profileBtn && !profileDropdown.contains(e.target) && !profileBtn.contains(e.target)) {
            profileDropdown.classList.remove('show');
        }
    });
    
    if (confirmUploadBtn && selectedTeamsList && selectedTagsList && tagModal) {
        confirmUploadBtn.addEventListener('click', () => {
            const selectedTeamElements = selectedTeamsList.querySelectorAll('li');
            const selectedTeams = Array.from(selectedTeamElements).map(el => el.dataset.value);

            const selectedTagElements = selectedTagsList.querySelectorAll('li');
            const selectedTags = Array.from(selectedTagElements).map(el => el.dataset.value);

            if (selectedTeams.length === 0) {
                showStatus('Please select at least one team.', 'error', document.getElementById('tag-modal').querySelector('.upload-status'));
                return;
            }
            if (pendingFilesToUpload) {
                tagModal.classList.add('hidden');
                handleFileUpload(pendingFilesToUpload, selectedTeams, selectedTags);
            }
        });
    }

    [
        { available: availableTeamsList, selected: selectedTeamsList },
        { available: availableTagsList, selected: selectedTagsList }
    ].forEach(pair => {
        if (pair.available && pair.selected) {
            pair.available.addEventListener('click', e => {
                if (e.target.tagName === 'LI') {
                    moveItem(e.target, pair.available, pair.selected);
                }
            });
            pair.selected.addEventListener('click', e => {
                if (e.target.tagName === 'LI') {
                    moveItem(e.target, pair.selected, pair.available);
                }
            });
        }
    });

    // --- Initialization ---
    manageTheme();
    setupDragAndDrop();
    refreshFileList();
    autoResizeTextarea(chatInput);
    if (chatInput) chatInput.focus();
    fetchUserInfo();
    setupSessionTimeout();
    loadInitialChat();
    fetchAndSetBranding();
    populateChatCategories();
});
