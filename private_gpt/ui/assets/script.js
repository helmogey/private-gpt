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

    let chatHistory = [];
    let selectedFile = null;
    let currentMode = 'RAG'; // Default mode
    let isUploading = false;
    let isTyping = false;
    let sessionTimeoutId = null; // To hold the session timer

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
        uploadProgress.classList.toggle('visible', percent > 0);
        uploadProgressBar.style.width = `${percent}%`;
    }

    function setButtonLoading(button, loading) {
        button.classList.toggle('loading', loading);
        button.disabled = loading;
    }

    // --- Core Functions ---

    function appendMessage(sender, message) {
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message-bubble', sender);

        const avatar = document.createElement('div');
        avatar.classList.add('message-avatar', sender);
        avatar.innerHTML = sender === 'user' ? 
            `<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M12 4a4 4 0 0 1 4 4 4 4 0 0 1-4 4 4 4 0 0 1-4-4 4 4 0 0 1 4-4m0 10c4.42 0 8 1.79 8 4v2H4v-2c0-2.21 3.58-4 8-4Z"/></svg>` :
            `<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M17.753 14a2.25 2.25 0 0 1 2.25 2.25v.905a3.75 3.75 0 0 1-1.307 2.846C17.13 21.345 14.89 22 12 22c-2.89 0-5.13-.655-6.696-2A3.75 3.75 0 0 1 4 17.155v-.905A2.25 2.25 0 0 1 6.247 14h11.506ZM12 2.25A3.75 3.75 0 0 1 15.75 6v1.5A3.75 3.75 0 0 1 12 11.25 3.75 3.75 0 0 1 8.25 7.5V6A3.75 3.75 0 0 1 12 2.25Z"/></svg>`;

        const content = document.createElement('div');
        content.classList.add('message-content', sender);
        content.innerHTML = message;
        
        const actions = document.createElement('div');
        actions.classList.add('message-actions');
        actions.innerHTML = `
            <button class="message-action-button" title="Copy" onclick="copyMessage(this)">
                <svg width="14" height="14" viewBox="0 0 24 24"><path fill="currentColor" d="M16,1H4C2.9,1 2,1.9 2,3V17H4V3H16V1M19,5H8C6.9,5 6,5.9 6,7V21C6,22.1 6.9,23 8,23H19C20.1,23 21,22.1 21,21V7C21,5.9 20.1,5 19,5M19,21H8V7H19V21Z"/></svg>
            </button>
        `;
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);
        messageDiv.appendChild(actions);

        chatbot.appendChild(messageDiv);
        chatbot.scrollTop = chatbot.scrollHeight;
        
        return messageDiv;
    }
    
    window.copyMessage = function(button) {
        const content = button.closest('.message-bubble').querySelector('.message-content').innerText;
        navigator.clipboard.writeText(content).then(() => {
            showStatus('Copied to clipboard!', 'success');
        });
    }

    function showTypingIndicator() {
        if (isTyping) return;
        isTyping = true;
        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        typingDiv.classList.add('typing-indicator');
        typingDiv.innerHTML = `
            <div class="message-avatar bot">
                <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M17.753 14a2.25 2.25 0 0 1 2.25 2.25v.905a3.75 3.75 0 0 1-1.307 2.846C17.13 21.345 14.89 22 12 22c-2.89 0-5.13-.655-6.696-2A3.75 3.75 0 0 1 4 17.155v-.905A2.25 2.25 0 0 1 6.247 14h11.506ZM12 2.25A3.75 3.75 0 0 1 15.75 6v1.5A3.75 3.75 0 0 1 12 11.25 3.75 3.75 0 0 1 8.25 7.5V6A3.75 3.75 0 0 1 12 2.25Z"/></svg>
            </div>
            <div class="typing-content">
                <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
            </div>
        `;
        chatbot.appendChild(typingDiv);
        chatbot.scrollTop = chatbot.scrollHeight;
    }

    function hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
        isTyping = false;
    }
    
    
    

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

    async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message || isTyping) return;

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
                    context_filter: selectedFile ? { docs_ids: [selectedFile] } : null
                }),
            });

            hideTypingIndicator();
            	
            
            const botMessageElement = appendMessage('bot', '');
            const botMessageContent = botMessageElement.querySelector('.message-content');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let botReply = '';
            let sources = [];
            
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataPart = line.substring(6);
                        if (!dataPart) continue;
                        
                        try {
                            const parsed = JSON.parse(dataPart);
                            if (parsed.delta) {
                                botReply += parsed.delta;
                                botMessageContent.innerHTML = `<p>${botReply}</p>`;
                            }
                            if (parsed.sources) sources = parsed.sources;
                        } catch (e) { console.error('Error parsing streaming data:', e); }
                    }
                }
                chatbot.scrollTop = chatbot.scrollHeight;
            }

            if (sources.length > 0) {
                let sourcesHtml = `<div class="message-sources"><div class="sources-title">Sources</div>`;
                sources.forEach(s => {
                    sourcesHtml += `<div class="source-item"><div class="source-file">${s.file} (Page ${s.page})</div><div class="source-text">${s.text.substring(0, 100)}...</div></div>`;
                });
                sourcesHtml += '</div>';
                botMessageContent.innerHTML = `<p>${botReply}</p>${sourcesHtml}`;
            }
            
            chatHistory.push({ role: 'assistant', content: botReply });

        } catch (error) {
            hideTypingIndicator();
            appendMessage('bot', 'Error: Could not get a response.');
            console.error('Chat error:', error);
            showStatus('Failed to send message', 'error');
        } finally {
            setButtonLoading(sendBtn, false);
        }
    }
	
	
	async function loadChatHistory() {
        try {
            const response = await fetch('/api/chat/history');
            if (!response.ok) {
                console.log('No previous chat history found for this user.');
                return;
            }
            const data = await response.json();
            
            if (data.history && data.history.length > 0) {
                chatbot.innerHTML = ''; // Clear any welcome messages
                
                data.history.forEach(message => {
                    const sender = message.role === 'assistant' ? 'bot' : 'user';
                    appendMessage(sender, message.content);
                });
                
                chatHistory = data.history;
                chatbot.scrollTop = chatbot.scrollHeight;
            }
            
        } catch (error) {
            console.error('Error loading chat history:', error);
            showStatus('Could not load chat history.', 'error');
        }
    }
	
	
    async function handleFileUpload(files) {
        if (files.length === 0 || isUploading) return;
        isUploading = true;
        const file = files[0];
        showStatus(`Uploading ${file.name}...`, 'loading');
        updateUploadProgress(0);
        const formData = new FormData();
        formData.append('file', file);

        let progress = 0;
        const progressInterval = setInterval(() => {
            progress = Math.min(progress + Math.random() * 15, 90);
            updateUploadProgress(progress);
        }, 200);

        try {
            const response = await fetch('/api/upload', { method: 'POST', body: formData });
            clearInterval(progressInterval);
            updateUploadProgress(100);
            if (response.ok) {
                setTimeout(() => {
                    showStatus('Upload successful!', 'success');
                    updateUploadProgress(0);
                    refreshFileList();
                }, 500);
            } else { throw new Error('Upload failed'); }
        } catch (error) {
            clearInterval(progressInterval);
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

    // --- UI Enhancement Functions ---
    window.toggleAccordion = function(header) {
        header.classList.toggle('collapsed');
        header.nextElementSibling.classList.toggle('collapsed');
    };

    function setupDragAndDrop() {
        ['dragover', 'dragleave', 'drop'].forEach(eventName => {
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
    
    function clearChat() {
        chatbot.innerHTML = '';
        chatbot.appendChild(welcomeMessage);
        welcomeMessage.style.display = 'flex';
        chatHistory = [];
        showStatus('Chat cleared', 'info');
    }

    // --- Role Management ---
    async function fetchUserRole() {
        try {
            const response = await fetch('/api/user/role');
            if (!response.ok) {
                throw new Error('Failed to fetch user role.');
            }
            const data = await response.json();
            
            // Get references to the sections to be hidden
            const uploadControls = document.getElementById('upload-controls');
            const fileActionControls = document.getElementById('file-action-controls');
            const chatSettingsSection = document.getElementById('chat-settings-section');
            const elementsToToggle = [uploadControls, fileActionControls, chatSettingsSection];

            if (data.role === '1') { // Regular User
                elementsToToggle.forEach(el => {
                    if (el) el.classList.add('hidden-by-role');
                });
            } else { // Admin or other roles
                 elementsToToggle.forEach(el => {
                    if (el) el.classList.remove('hidden-by-role');
                });
            }
        } catch (error) {
            console.error('Error fetching user role:', error);
            // Default to hiding elements for security if the role check fails
            const uploadControls = document.getElementById('upload-controls');
            const fileActionControls = document.getElementById('file-action-controls');
            const chatSettingsSection = document.getElementById('chat-settings-section');
            const elementsToToggle = [uploadControls, fileActionControls, chatSettingsSection];
            elementsToToggle.forEach(el => {
                if (el) el.classList.add('hidden-by-role');
            });
        }
    }

    // --- Session Management ---
    function resetSessionTimeout(maxAgeSeconds) {
        // Clear any existing timer
        if (sessionTimeoutId) {
            clearTimeout(sessionTimeoutId);
        }

        // Set a new timer if maxAge is valid
        if (maxAgeSeconds && maxAgeSeconds > 0) {
            sessionTimeoutId = setTimeout(() => {
                try {
                    showStatus('Session expired due to inactivity, logging out...', 'info');
                    setTimeout(() => {
                       window.location.href = '/logout';
                    }, 1500); // Give user a moment to see the message
                } catch (e) {
                    console.error("Error showing session expiry message, forcing logout.", e);
                    window.location.href = '/logout';
                }
            }, maxAgeSeconds * 1000);
        }
    }

    async function setupSessionTimeout() {
        try {
            const response = await fetch('/api/session/expiry');
            if (!response.ok) {
                console.log('Could not fetch session expiry. User might be logged out.');
                return;
            }
            const data = await response.json();
            const maxAgeSeconds = data.max_age;

            // Set the initial timer
            resetSessionTimeout(maxAgeSeconds);

            // Add event listeners to reset the timer on any user activity
            ['mousemove', 'keydown', 'click'].forEach(eventName => {
                document.addEventListener(eventName, () => resetSessionTimeout(maxAgeSeconds));
            });
            
        } catch (error) {
            console.error('Error setting up session timeout:', error);
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
    clearBtn.addEventListener('click', clearChat);
    logoutBtn.addEventListener('click', () => {
        window.location.href = '/logout';
    });
    modeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            currentMode = e.target.value;
        });
    });

    // --- Initialization ---
    manageTheme();
    setupDragAndDrop();
    refreshFileList();
    autoResizeTextarea(chatInput);
    chatInput.focus();
    fetchUserRole();
    setupSessionTimeout();
    loadChatHistory();
});
