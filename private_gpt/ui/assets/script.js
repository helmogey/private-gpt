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
    const logoutBtn = document.getElementById('logout-btn');
    const welcomeMessage = document.getElementById('welcome-message');
    const clearBtn = document.getElementById('clear-btn');
    const modeRadios = document.querySelectorAll('input[name="mode"]');
    const chatList = document.getElementById('chat-list');
    const newChatBtn = document.getElementById('new-chat-btn');

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

    function showStatus(message, type = 'info') {
        uploadStatus.textContent = message;
        uploadStatus.className = `upload-status ${type}`;
        uploadStatus.style.display = 'block';
        if (type !== 'loading') {
            setTimeout(() => { uploadStatus.style.display = 'none'; }, 3000);
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
        const file = files[0];
        showStatus(`Uploading ${file.name}...`, 'loading');
        updateUploadProgress(0);
        const formData = new FormData();
        formData.append('file', file);

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
                setTimeout(() => {
                    showStatus('Upload successful!', 'success');
                    updateUploadProgress(0);
                    refreshFileList();
                }, 500);
            } else { throw new Error('Upload failed'); }
        } catch (error) {
            updateUploadProgress(0);
            showStatus('Upload failed', 'error');
            console.error('File upload error:', error);
        } finally {
            isUploading = false;
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

    async function fetchUserRole() {
        try {
            const response = await fetch('/api/user/role');
            if (!response.ok) throw new Error('Failed to fetch user role.');
            const data = await response.json();
            
            const elementsToToggle = document.querySelectorAll('#file-management-section, #chat-settings-section');
            if (data.role === '1') { // Regular User
                elementsToToggle.forEach(el => el.classList.add('hidden-by-role'));
            } else {
                 elementsToToggle.forEach(el => el.classList.remove('hidden-by-role'));
            }
        } catch (error) {
            console.error('Error fetching user role:', error);
            document.querySelectorAll('#file-management-section, #chat-settings-section')
                .forEach(el => el.classList.add('hidden-by-role'));
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
    logoutBtn.addEventListener('click', () => { window.location.href = '/logout'; });
    modeRadios.forEach(radio => radio.addEventListener('change', (e) => { currentMode = e.target.value; }));

    // --- Initialization ---
    manageTheme();
    setupDragAndDrop();
    refreshFileList();
    autoResizeTextarea(chatInput);
    chatInput.focus();
    fetchUserRole();
    setupSessionTimeout();
    loadInitialChat();
});

