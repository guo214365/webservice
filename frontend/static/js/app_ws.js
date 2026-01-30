window.__appWsLoaded = true;

class ChatAppWS {
    constructor() {
        this.messages = [];
        this.currentAssistantMessage = null;
        this.ws = null;
        this.reconnectTimeout = null;
        this.isComposing = false;
        this.typewriterQueue = '';
        this.isTyping = false;
        this.displayedText = '';
        
        // 打字机配置
        this.typewriterSpeed = 50;  // 基础速度（毫秒/字符）
        this.typewriterSpeedFast = 10;  // 快速模式
        this.typewriterSpeedSlow = 100;  // 慢速模式
        this.bufferThreshold = 0;  // 缓冲区阈值（开始打字前需要的最小字符数）
        this.isBuffering = false;  // 是否在缓冲中
        
        this.isGenerating = false;
        
        this.messagesContainer = document.getElementById('messages');
        this.userInput = document.getElementById('userInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.jsonData = null;  // 存储上传的JSON数据
        
        // 历史记录管理
        this.chatHistories = [];  // 存储多个对话历史
        this.currentChatId = null;  // 当前选中的对话ID
        this.maxHistories = 15;  // 最多保存15轮对话
        this.storageKey = 'chatHistories';
        
        // Skill 编辑器状态
        this.currentSkillName = null;
        this.originalSkillContent = '';
        this.skillModified = false;
        this.defaultSkillName = 'evaluate-record';
        this.skillsLoaded = false;
        
        this.loadChatHistories();
        this.initEventListeners();
        this.configureMarked();
        this.connectWebSocket();
        
        // 初始化侧边栏标签和技能列表
        this.initSidebarTabs();
        this.initSkillEditor();
        this.loadSkillsList();
    }
    
    configureMarked() {
        if (!window.marked) {
            console.warn('marked 未加载，使用纯文本渲染');
            window.marked = {
                parse: (text) => this.escapeHtml(String(text || '')).replace(/\n/g, '<br>')
            };
            return;
        }
        const hasHighlight = typeof window.hljs !== 'undefined';
        marked.setOptions({
            highlight: function(code, lang) {
                if (!hasHighlight) {
                    return code;
                }
                if (lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {
                        console.error('Highlight error:', e);
                    }
                }
                try {
                    return hljs.highlightAuto(code).value;
                } catch (e) {
                    console.error('Auto highlight error:', e);
                    return code;
                }
            },
            breaks: true,
            gfm: true,
            headerIds: true,
            mangle: false
        });
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        console.log('Connecting to WebSocket:', wsUrl);
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateStatus(true);
            if (this.reconnectTimeout) {
                clearTimeout(this.reconnectTimeout);
                this.reconnectTimeout = null;
            }
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateStatus(false);
            // 5秒后自动重连
            this.reconnectTimeout = setTimeout(() => {
                console.log('Attempting to reconnect...');
                this.connectWebSocket();
            }, 5000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
    }
    updateStatus(connected) {
        if (connected) {
            this.statusIndicator.textContent = '🟢';
            this.statusIndicator.className = 'status-indicator status-connected';
        } else {
            this.statusIndicator.textContent = '🔴';
            this.statusIndicator.className = 'status-indicator status-disconnected';
        }
    }
    
    handleMessage(data) {
        console.log('Received message:', data.type, data.content ? `(${data.content.substring(0, 50)}...)` : '');
        
        // 调试：记录所有接收到的内容
        if (data.type === 'assistant_message' && data.content) {
            console.log('[DEBUG] 接收内容:', data.content);
        }
        
        switch (data.type) {
            case 'user_message':
                // 其他客户端或外部触发的用户消息
                // 跳过，因为本地已经显示了
                break;
                
            case 'assistant_message':
                // AI 回复的内容
                if (!this.currentAssistantMessage) {
                    // 移除加载提示
                    this.removeLoadingIndicator();
                    
                    this.currentAssistantMessage = this.createMessageElement('assistant', '');
                    this.currentAssistantMessage.classList.add('streaming');
                    const contentDiv = this.currentAssistantMessage.querySelector('.message-content');
                    contentDiv.classList.add('typing');
                    this.messagesContainer.appendChild(this.currentAssistantMessage);
                    this.isGenerating = true;
                    this.startTypewriter();
                }
                
                // 添加到打字机队列
                this.typewriterQueue += data.content;
                break;
                
            case 'complete':
                // 回复完成
                this.isGenerating = false;
                
                // 等待打字机完成
                this.finishTypewriter().then(() => {
                    if (this.currentAssistantMessage) {
                        const contentDiv = this.currentAssistantMessage.querySelector('.message-content');
                        contentDiv.classList.remove('typing');
                        this.currentAssistantMessage.classList.remove('streaming');
                        
                        // 完成后进行最终渲染（Markdown 解析）
                        this.updateMessageContent(this.currentAssistantMessage, this.displayedText, contentDiv, true);
                        
                        // 保存到历史
                        this.messages.push({
                            role: 'assistant',
                            content: this.displayedText
                        });
                        
                        this.saveChatHistories();
                        this.currentAssistantMessage = null;
                        this.displayedText = '';
                    }
                });
                break;
                
            case 'error':
                // 错误消息
                this.isGenerating = false;
                
                // 移除加载提示
                this.removeLoadingIndicator();
                
                const errorMsg = this.createMessageElement('assistant', '');
                const errorContentDiv = errorMsg.querySelector('.message-content');
                // 使用最终渲染来正确解析markdown
                this.updateMessageContent(errorMsg, data.content, errorContentDiv, true);
                this.messagesContainer.appendChild(errorMsg);
                this.currentAssistantMessage = null;
                this.scrollToBottom();
                break;
                
            case 'external_trigger':
                // 外部触发的消息，显示特殊标记
                const messageDiv = this.createMessageElement('user', data.message);
                const contentDiv = messageDiv.querySelector('.message-content');
                const badge = document.createElement('span');
                badge.className = 'external-badge';
                badge.textContent = `来自 ${data.source}`;
                contentDiv.appendChild(document.createTextNode(' '));
                contentDiv.appendChild(badge);
                this.messagesContainer.appendChild(messageDiv);
                this.scrollToBottom();
                break;
        }
    }
    
    startTypewriter() {
        if (this.isTyping) return;
        this.isTyping = true;
        this.isBuffering = true;  // 开始时进入缓冲模式
        this.typewriterLoop();
    }
    
    typewriterLoop() {
        // 结束条件：生成完成且队列为空
        if (!this.isGenerating && this.typewriterQueue.length === 0) {
            this.isTyping = false;
            this.isBuffering = false;
            return;
        }
        
        // 如果生成已完成且队列不多，快速显示剩余内容
        if (!this.isGenerating && this.typewriterQueue.length > 0 && this.typewriterQueue.length < 30) {
            // 快速清空剩余队列
            this.displayedText += this.typewriterQueue;
            this.typewriterQueue = '';
            if (this.currentAssistantMessage) {
                this.updateMessageContent(this.currentAssistantMessage, this.displayedText);
                this.scrollToBottom();
            }
            this.isTyping = false;
            this.isBuffering = false;
            return;
        }
        
        // 缓冲逻辑：队列中内容少于阈值时等待
        if (this.isBuffering && this.typewriterQueue.length < this.bufferThreshold && this.isGenerating) {
            // 还在缓冲中，等待更多内容
            setTimeout(() => this.typewriterLoop(), 100);
            return;
        }
        
        // 开始打字后就退出缓冲模式
        if (this.isBuffering) {
            this.isBuffering = false;
        }
        
        // 打字
        if (this.typewriterQueue.length > 0) {
            const char = this.typewriterQueue[0];
            this.typewriterQueue = this.typewriterQueue.slice(1);
            this.displayedText += char;
            
            if (this.currentAssistantMessage) {
                this.updateMessageContent(this.currentAssistantMessage, this.displayedText);
                this.scrollToBottom();
            }
        }
        
        // 动态调整速度
        let speed = this.typewriterSpeed;
        if (this.typewriterQueue.length > 50) {
            // 队列很长，加快速度
            speed = this.typewriterSpeedFast;
        } else if (this.typewriterQueue.length < 10 && this.isGenerating) {
            // 队列很短但还在生成，放慢速度等待
            speed = this.typewriterSpeedSlow;
        } else if (!this.isGenerating && this.typewriterQueue.length > 0) {
            // 生成已完成，快速显示剩余
            speed = this.typewriterSpeedFast;
        }
        
        setTimeout(() => this.typewriterLoop(), speed);
    }
    
    async finishTypewriter() {
        while (this.typewriterQueue.length > 0) {
            await new Promise(resolve => setTimeout(resolve, 50));
        }
    }
    
    initEventListeners() {
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        this.userInput.addEventListener('compositionstart', () => {
            this.isComposing = true;
        });
        
        this.userInput.addEventListener('compositionend', () => {
            this.isComposing = false;
        });
        
        this.userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                if (this.isComposing) {
                    return;
                }
                e.preventDefault();
                this.sendMessage();
            }
        });

        // 图片上传处理
        document.getElementById('imageUploadBtn').addEventListener('click', () => {
            document.getElementById('imageUpload').click();
        });
        
        document.getElementById('imageUpload').addEventListener('change', (e) => {
            const files = e.target.files;
            if (files.length > 0) {
                this.handleImageUpload(files[0]);
            }
            e.target.value = ''; // 重置input
        });
        
        // JSON文件上传处理
        document.getElementById('jsonUploadBtn').addEventListener('click', () => {
            document.getElementById('jsonUpload').click();
        });
        
        document.getElementById('jsonUpload').addEventListener('change', (e) => {
            const files = e.target.files;
            if (files.length > 0) {
                this.handleJsonUpload(files[0]);
            }
            e.target.value = ''; // 重置input
        });
        
        // 导出对话按钮事件 - 切换菜单显示
        document.getElementById('exportBtn').addEventListener('click', () => {
            const menu = document.getElementById('exportMenu');
            menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
        });
        
        // 导出为Markdown
        document.getElementById('exportMarkdown').addEventListener('click', () => {
            this.exportAsMarkdown();
            document.getElementById('exportMenu').style.display = 'none';
        });
        
        // 导出为Word
        document.getElementById('exportWord').addEventListener('click', () => {
            this.exportAsWord();
            document.getElementById('exportMenu').style.display = 'none';
        });
        
        // 点击其他地方关闭菜单
        document.addEventListener('click', (e) => {
            const exportDropdown = document.querySelector('.export-dropdown');
            if (exportDropdown && !exportDropdown.contains(e.target)) {
                document.getElementById('exportMenu').style.display = 'none';
            }
        });
        
        // 新对话按钮事件
        this.initNewChatButton();
        
        // 清空历史按钮事件
        const clearHistoryBtn = document.getElementById('clearHistoryBtn');
        if (clearHistoryBtn) {
            clearHistoryBtn.addEventListener('click', () => this.clearAllHistories());
        }
    }

    handleImageUpload(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const imagePreview = document.getElementById('imagePreview');
            const previewDiv = document.createElement('div');
            previewDiv.className = 'preview-item';
            
            const img = document.createElement('img');
            img.src = e.target.result;
            img.className = 'preview-image';
            
            const removeBtn = document.createElement('button');
            removeBtn.className = 'remove-image';
            removeBtn.innerHTML = '×';
            removeBtn.addEventListener('click', () => {
                previewDiv.remove();
            });
            
            previewDiv.appendChild(img);
            previewDiv.appendChild(removeBtn);
            imagePreview.appendChild(previewDiv);
        };
        reader.readAsDataURL(file);
    }
    
    handleJsonUpload(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const jsonData = JSON.parse(e.target.result);
                
                // 验证JSON格式
                if (!Array.isArray(jsonData) && typeof jsonData !== 'object') {
                    alert('JSON格式错误：必须是数组或对象');
                    return;
                }
                
                // 存储JSON数据
                this.jsonData = jsonData;
                
                // 显示JSON预览
                const jsonPreview = document.getElementById('jsonPreview');
                jsonPreview.innerHTML = '';
                
                const previewDiv = document.createElement('div');
                previewDiv.className = 'json-preview-item';
                
                const fileName = document.createElement('div');
                fileName.className = 'json-file-name';
                fileName.textContent = `📄 ${file.name}`;
                
                const caseCount = Array.isArray(jsonData) ? jsonData.length : Object.keys(jsonData).length;
                const infoText = document.createElement('div');
                infoText.className = 'json-file-info';
                infoText.textContent = `包含 ${caseCount} 个case`;
                
                const removeBtn = document.createElement('button');
                removeBtn.className = 'remove-json';
                removeBtn.innerHTML = '×';
                removeBtn.addEventListener('click', () => {
                    previewDiv.remove();
                    this.jsonData = null;
                });
                
                previewDiv.appendChild(fileName);
                previewDiv.appendChild(infoText);
                previewDiv.appendChild(removeBtn);
                jsonPreview.appendChild(previewDiv);
                
                console.log('JSON文件已加载:', jsonData);
                
            } catch (error) {
                alert('JSON解析失败：' + error.message);
                console.error('JSON解析错误:', error);
            }
        };
        reader.readAsText(file);
    }
    
    initNewChatButton() {
        const newChatBtn = document.getElementById('newChatBtn');
        if (newChatBtn) {
            newChatBtn.addEventListener('click', () => this.clearChat());
        }
    }
    
    sendMessage() {
        const message = this.userInput.value.trim();
        const imagePreview = document.getElementById('imagePreview');
        const images = imagePreview.querySelectorAll('.preview-image');
        const jsonPreview = document.getElementById('jsonPreview');
        
        // 检查连接状态
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            alert('未连接到服务器，请等待重连...');
            return;
        }
        
        // 检查是否有内容（文字、图片或JSON）
        if (!message && images.length === 0 && !this.jsonData) {
            alert('请输入文字、上传图片或上传JSON文件');
            return;
        }
        
        // 如果有JSON数据，处理多个case
        if (this.jsonData) {
            this.processJsonCases(message, images);
        } else {
            // 普通消息处理
            this.sendSingleMessage(message, images);
        }
        
        // 清空输入和预览
        this.userInput.value = '';
        imagePreview.innerHTML = '';
        jsonPreview.innerHTML = '';
        this.jsonData = null;
    }
    
    sendSingleMessage(message, images) {
        // 立即显示用户消息
        if (message) {
            this.addMessage('user', message);
        }
        
        // 显示图片
        if (images.length > 0) {
            images.forEach(img => {
                this.addMessage('user', `<img src="${img.src}" class="message-image">`);
            });
        }
        
        // 显示加载提示
        this.showLoadingIndicator();
        
        // 准备发送的数据（始终包含message字段，即使为空）
        const data = {
            message: message || '',  // 确保message字段存在
            history: this.messages
        };
        
        // 如果有图片，添加图片数据
        if (images.length > 0) {
            data.images = Array.from(images).map(img => img.src);
        } else {
            data.images = [];  // 明确表示没有图片
        }
        
        // 通过 WebSocket 发送消息
        this.ws.send(JSON.stringify(data));
        
        // 保存到历史记录（合并文字和图片）
        const userMessage = {
            role: 'user',
            content: message || ''  // 确保content字段存在
        };
        
        if (images.length > 0) {
            // 如果有图片，将图片URL附加到消息内容
            images.forEach(img => {
                userMessage.content += `\n[图片: ${img.src}]`;
            });
        }
        
        this.messages.push(userMessage);
        this.saveChatHistories();
        
        // 添加消息操作按钮
        this.addMessageActions();
    }
    
    async processJsonCases(message, images) {
        // 将JSON数据转换为数组（如果不是数组）
        let cases = [];
        if (Array.isArray(this.jsonData)) {
            cases = this.jsonData;
        } else if (typeof this.jsonData === 'object') {
            // 如果是对象，尝试提取数组字段
            if (this.jsonData.cases && Array.isArray(this.jsonData.cases)) {
                cases = this.jsonData.cases;
            } else if (this.jsonData.data && Array.isArray(this.jsonData.data)) {
                cases = this.jsonData.data;
            } else {
                // 将对象转为数组
                cases = Object.values(this.jsonData);
            }
        }
        
        if (cases.length === 0) {
            alert('JSON文件中没有找到有效的case数据');
            return;
        }
        
        // 显示用户消息（包含JSON文件信息）
        const jsonInfo = `[已上传JSON文件，包含 ${cases.length} 个case]`;
        if (message) {
            this.addMessage('user', `${message}\n${jsonInfo}`);
        } else {
            this.addMessage('user', jsonInfo);
        }
        
        // 显示图片
        if (images.length > 0) {
            images.forEach(img => {
                this.addMessage('user', `<img src="${img.src}" class="message-image">`);
            });
        }
        
        // 逐个处理每个case
        for (let i = 0; i < cases.length; i++) {
            const caseData = cases[i];
            const caseMessage = message || '请分析以下case';
            
            // 显示当前处理的case信息
            this.addMessage('user', `\n--- Case ${i + 1}/${cases.length} ---\n${JSON.stringify(caseData, null, 2)}`);
            
            // 显示加载提示
            this.showLoadingIndicator();
            
            // 准备发送的数据
            const data = {
                message: caseMessage,
                history: this.messages,
                case_data: caseData,  // 添加case数据
                case_index: i,  // 添加case索引
                total_cases: cases.length  // 添加总case数
            };
            
            // 如果有图片，添加图片数据
            if (images.length > 0) {
                data.images = Array.from(images).map(img => img.src);
            } else {
                data.images = [];
            }
            
            // 保存到历史记录
            this.messages.push({
                role: 'user',
                content: `Case ${i + 1}/${cases.length}: ${JSON.stringify(caseData)}`
            });
            
            // 通过 WebSocket 发送消息
            this.ws.send(JSON.stringify(data));
            
            // 等待AI回复完成（通过监听complete事件）
            await this.waitForCompletion();
            
            // 短暂延迟，避免请求过快
            if (i < cases.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }
        
        // 所有case处理完成
        this.addMessage('assistant', `\n✅ 所有 ${cases.length} 个case分析完成！`);
        
        // 添加消息操作按钮
        this.addMessageActions();
    }
    
    waitForCompletion() {
        return new Promise((resolve) => {
            const checkComplete = () => {
                if (!this.isGenerating && this.typewriterQueue.length === 0) {
                    resolve();
                } else {
                    setTimeout(checkComplete, 100);
                }
            };
            checkComplete();
        });
    }
    
    addMessageActions() {
        // 为最新的一条助手消息添加操作按钮
        const messages = document.querySelectorAll('.message.assistant');
        if (messages.length > 0) {
            const lastMessage = messages[messages.length - 1];
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'message-actions';
            
            actionsDiv.innerHTML = `
                <button class="action-btn">复制</button>
                <button class="action-btn">👍</button>
                <button class="action-btn">分享</button>
            `;
            
            // 如果已经有操作按钮，先移除
            const existingActions = lastMessage.querySelector('.message-actions');
            if (existingActions) {
                existingActions.remove();
            }
            
            const contentDiv = lastMessage.querySelector('.message-content');
            if (contentDiv) {
                contentDiv.appendChild(actionsDiv);
            } else {
                console.warn('找不到 .message-content 元素');
            }
            
            // 添加操作按钮事件
            this.attachActionEvents(actionsDiv);
        }
    }
    
    attachActionEvents(actionsDiv) {
        const copyBtn = actionsDiv.querySelector('.action-btn:nth-child(1)');
        const likeBtn = actionsDiv.querySelector('.action-btn:nth-child(2)');
        const shareBtn = actionsDiv.querySelector('.action-btn:nth-child(3)');
        
        copyBtn.addEventListener('click', () => {
            // 获取消息的原始文本内容（不含HTML标签）
            const messageElement = actionsDiv.closest('.message');
            const content = this.extractPlainText(messageElement);
            
            navigator.clipboard.writeText(content).then(() => {
                copyBtn.textContent = '已复制';
                setTimeout(() => {
                    copyBtn.textContent = '复制';
                }, 2000);
            }).catch(err => {
                console.error('复制失败:', err);
            });
        });
        
        likeBtn.addEventListener('click', () => {
            likeBtn.textContent = '已赞';
            likeBtn.disabled = true;
        });
        
        shareBtn.addEventListener('click', () => {
            const messageElement = actionsDiv.closest('.message');
            const content = this.extractPlainText(messageElement);
            
            if (navigator.share) {
                navigator.share({
                    text: content
                });
            } else {
                navigator.clipboard.writeText(content).then(() => {
                    shareBtn.textContent = '已复制';
                    setTimeout(() => {
                        shareBtn.textContent = '分享';
                    }, 2000);
                });
            }
        });
    }
    
    extractPlainText(element) {
        // 获取元素的文本内容，移除"复制", "👍", "分享"这些按钮文本
        let text = element.innerText || element.textContent;
        // 移除操作按钮文本
        text = text.replace(/复制|👍|分享/g, '').trim();
        return text;
    }
    
    addMessage(role, content) {
        const messageDiv = this.createMessageElement(role, content);
        
        // 如果是图片消息，直接显示HTML
        if (content.includes('<img')) {
            const contentDiv = messageDiv.querySelector('.message-content');
            contentDiv.innerHTML = content;
        }
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    createMessageElement(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (content) {
            this.updateMessageContent(messageDiv, content, contentDiv);
        }
        
        messageDiv.appendChild(contentDiv);
        return messageDiv;
    }
    
    updateMessageContent(messageElement, content, contentDiv = null, isFinalRender = false) {
        if (!contentDiv) {
            contentDiv = messageElement.querySelector('.message-content');
        }
        
        if (messageElement.classList.contains('user')) {
            contentDiv.textContent = content;
        } else {
            if (isFinalRender) {
                // 最终渲染：使用完整的 Markdown 解析
                const processed = this.processThinkingAndResponse(content);
                
                // 添加淡入效果，减少视觉跳动
                contentDiv.style.opacity = '0.7';
                contentDiv.innerHTML = processed;
                
                // 美化工具调用提示
                this.styleToolCalls(contentDiv);
                
                contentDiv.querySelectorAll('pre code').forEach((block) => {
                    hljs.highlightElement(block);
                });
                
                // 快速恢复透明度
                setTimeout(() => {
                    contentDiv.style.opacity = '1';
                }, 50);
            } else {
                // 流式输出：使用简化渲染
                this.updateStreamingContent(contentDiv, content);
            }
        }
    }
    
    renderSimpleMarkdown(text) {
        // 简化的Markdown渲染，用于流式显示
        if (!text || !text.trim()) return '';
        
        let html = this.escapeHtml(text.trim());

        // 代码块 ```
        html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<pre><code>${code.trim()}</code></pre>`;
        });

        // 行内代码 `code`
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // 加粗 **text**
        html = html.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>');

        // 斜体 *text*
        html = html.replace(/\*([^\*]+)\*/g, '<em>$1</em>');

        // 分段处理（按双换行分段）
        const paragraphs = html.split(/\n\n+/);
        html = paragraphs.map(para => {
            para = para.trim();
            if (!para) return '';
            
            // 检查是否是列表
            if (/^[\-\*]\s+/.test(para) || /^\d+\.\s+/.test(para)) {
                // 列表项
                const items = para.split('\n').map(line => {
                    line = line.trim();
                    if (/^[\-\*]\s+(.+)$/.test(line)) {
                        return '<li>' + line.replace(/^[\-\*]\s+/, '') + '</li>';
                    } else if (/^\d+\.\s+(.+)$/.test(line)) {
                        return '<li>' + line.replace(/^\d+\.\s+/, '') + '</li>';
                    }
                    return line;
                }).join('');
                return '<ul>' + items + '</ul>';
            } else if (para.startsWith('<pre>')) {
                // 代码块，直接返回
                return para;
            } else {
                // 普通段落，单换行变成<br>
                para = para.replace(/\n/g, '<br>');
                return '<p>' + para + '</p>';
            }
        }).filter(p => p).join('');

        return html;
    }

    updateStreamingContent(contentDiv, content) {
        // 流式显示：保持原有顺序，逐行处理
        
        // 预处理：修复没有换行的情况
        content = content.replace(/---+(##?\s*思考过程[：:：])/g, '---\n$1');
        content = content.replace(/---+(##?\s*思考过程[（(]续[）)]?[：:：])/g, '---\n$1');
        content = content.replace(/---+(##\s*回[复复][：:])/g, '---\n$1');
        // 修复文本后直接跟标题的情况
        content = content.replace(/([^#\n])(##?\s*思考过程[：:：])/g, '$1\n$2');
        content = content.replace(/([^#\n])(##?\s*思考过程[（(]续[）)]?[：:：])/g, '$1\n$2');
        content = content.replace(/([^#\n])(##\s*回[复复][：:])/g, '$1\n$2');
        
        const toolEmojis = ['📖', '✅', '✏️', '🔧', '🔍', '📁', '📝', '⚠️'];
        const lines = content.split('\n');
        
        let html = '';
        let inThinking = false;
        let thinkingContent = [];
        let afterDivider = false;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const trimmed = line.trim();
            
            // 检测工具调用
            if (toolEmojis.some(emoji => trimmed.startsWith(emoji))) {
                // 先结束当前的思考块
                if (inThinking && thinkingContent.length > 0) {
                    html += `
                        <div class="thinking-process">
                            <div class="thinking-process-header">
                                <span class="thinking-process-icon">🤔</span>
                                <span>思考过程</span>
                            </div>
                            <div class="thinking-process-content">
                                ${this.renderSimpleMarkdown(thinkingContent.join('\n'))}
                            </div>
                        </div>
                    `;
                    thinkingContent = [];
                    inThinking = false;
                }
                
                // 渲染工具调用
                let processedCall = this.escapeHtml(trimmed);
                processedCall = processedCall.replace(/`([^`]+)`/g, '<code>$1</code>');
                html += `<div class="tool-call-hint">${processedCall}</div>`;
                continue;
            }
            
            // 检测思考过程标记（支持多种格式）
            if (/^##?\s*思考过程[：:：]/.test(trimmed) || /^##?\s*思考过程[（(]续[）)]?[：:：]/.test(trimmed) || /^##?\s*Thinking Process[：:：]/.test(trimmed)) {
                // 开始新的思考块
                if (inThinking && thinkingContent.length > 0) {
                    // 结束上一个思考块
                    html += `
                        <div class="thinking-process">
                            <div class="thinking-process-header">
                                <span class="thinking-process-icon">🤔</span>
                                <span>思考过程</span>
                            </div>
                            <div class="thinking-process-content">
                                ${this.renderSimpleMarkdown(thinkingContent.join('\n'))}
                            </div>
                        </div>
                    `;
                    thinkingContent = [];
                }
                inThinking = true;
                continue;
            }
            
            // 检测分隔符
            if (/^---+$/.test(trimmed)) {
                // 结束思考，开始回复
                if (inThinking && thinkingContent.length > 0) {
                    html += `
                        <div class="thinking-process">
                            <div class="thinking-process-header">
                                <span class="thinking-process-icon">🤔</span>
                                <span>思考过程</span>
                            </div>
                            <div class="thinking-process-content">
                                ${this.renderSimpleMarkdown(thinkingContent.join('\n'))}
                            </div>
                        </div>
                    `;
                }
                // 清空暂存内容（无论是否在思考中）
                thinkingContent = [];
                inThinking = false;

                // 检查后面是否还有内容（如果有，加分隔线）
                const hasContentAfter = i < lines.length - 1 && lines.slice(i + 1).some(l => l.trim().length > 0);
                if (hasContentAfter) {
                    html += '<hr class="response-divider">';
                    afterDivider = true;
                }
                continue;
            }

            // 检测回复标记
            if (/^##\s*回[复复][：:]/.test(trimmed)) {
                // 结束思考，开始回复
                if (inThinking && thinkingContent.length > 0) {
                    html += `
                        <div class="thinking-process">
                            <div class="thinking-process-header">
                                <span class="thinking-process-icon">🤔</span>
                                <span>思考过程</span>
                            </div>
                            <div class="thinking-process-content">
                                ${this.renderSimpleMarkdown(thinkingContent.join('\n'))}
                            </div>
                        </div>
                    `;
                }
                // 清空暂存内容（无论是否在思考中）
                thinkingContent = [];
                inThinking = false;
                if (!afterDivider) {
                    html += '<hr class="response-divider">';
                }
                afterDivider = true;
                continue;
            }

            // 累积内容
            if (inThinking) {
                thinkingContent.push(line);
            } else if (afterDivider) {
                // 回复内容，直接渲染
                if (trimmed.length > 0) {
                    html += this.renderSimpleMarkdown(line) + '\n';
                }
            } else {
                // 还没开始思考过程，也不在回复中，暂时累积到思考内容
                // 这些文本会在下一个思考标记出现时合并进思考块
                if (trimmed.length > 0) {
                    thinkingContent.push(line);
                }
            }
        }

        // 处理未结束的思考块
        if (inThinking && thinkingContent.length > 0) {
            html += `
                <div class="thinking-process">
                    <div class="thinking-process-header">
                        <span class="thinking-process-icon">🤔</span>
                        <span>思考过程</span>
                    </div>
                    <div class="thinking-process-content">
                        ${this.renderSimpleMarkdown(thinkingContent.join('\n'))}
                    </div>
                </div>
            `;
        }

        contentDiv.innerHTML = html;

        // 添加光标到最后一个文本节点
        this.addCursorToEnd(contentDiv);
    }

    addCursorToEnd(container) {
        // 移除旧光标
        const oldCursors = container.querySelectorAll('.typing-cursor');
        oldCursors.forEach(c => c.remove());

        // 查找最后一个包含文本的元素
        const lastElement = this.findLastTextNode(container);
        if (lastElement) {
            const cursor = document.createElement('span');
            cursor.className = 'typing-cursor';
            cursor.textContent = '▎'; // 使用更粗的竖线字符

            // 检查最后一个文本节点的内容
            const lastTextNode = this.getLastTextNode(lastElement);
            if (lastTextNode && lastTextNode.textContent.endsWith('\n')) {
                // 如果以换行符结尾，创建新行并添加光标
                const newLine = document.createElement('span');
                newLine.style.display = 'block';
                newLine.appendChild(cursor);
                lastElement.appendChild(newLine);
            } else {
                // 直接添加到最后一个元素的末尾
                lastElement.appendChild(cursor);
            }
        }
    }

    getLastTextNode(element) {
        // 获取元素中最后一个文本节点
        let lastTextNode = null;
        const walk = (node) => {
            if (node.nodeType === Node.TEXT_NODE) {
                lastTextNode = node;
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                for (let child of node.childNodes) {
                    walk(child);
                }
            }
        };
        walk(element);
        return lastTextNode;
    }

    findLastTextNode(element) {
        // 递归查找最后一个包含文本内容的节点
        let lastNode = null;
        let lastElement = null;

        const walk = (node) => {
            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                lastNode = node;
                lastElement = node.parentElement;
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                // 遍历所有子节点，不跳过任何内容
                for (let child of node.childNodes) {
                    walk(child);
                }
            }
        };

        walk(element);
        // 返回最后一个文本节点的父元素，这样光标会显示在行内而不是下一行
        return lastElement || element;
    }

    styleToolCalls(contentDiv) {
        // 查找工具调用提示（包含特定emoji的段落）
        const toolEmojis = ['📖', '✅', '✏️', '🔧', '🔍', '📁'];
        contentDiv.querySelectorAll('p').forEach((p) => {
            const text = p.textContent;
            if (toolEmojis.some(emoji => text.startsWith('\n' + emoji) || text.startsWith(emoji))) {
                p.classList.add('tool-call-hint');
            }
        });
    }

    processThinkingAndResponse(content) {
        // 最终渲染：逐行处理，保持原有结构
        // 使用和 updateStreamingContent 相同的逻辑，但用 marked.parse 做完整的 Markdown 解析

        // 预处理：修复没有换行的情况
        content = content.replace(/---+(##?\s*思考过程[：:：])/g, '---\n$1');
        content = content.replace(/---+(##?\s*思考过程[（(]续[）)]?[：:：])/g, '---\n$1');
        content = content.replace(/---+(##\s*回[复复][：:])/g, '---\n$1');
        // 修复文本后直接跟标题的情况
        content = content.replace(/([^#\n])(##?\s*思考过程[：:：])/g, '$1\n$2');
        content = content.replace(/([^#\n])(##?\s*思考过程[（(]续[）)]?[：:：])/g, '$1\n$2');
        content = content.replace(/([^#\n])(##\s*回[复复][：:])/g, '$1\n$2');

        const toolEmojis = ['📖', '✅', '✏️', '🔧', '🔍', '📁', '📝', '⚠️'];
        const lines = content.split('\n');

        let html = '';
        let inThinking = false;
        let thinkingContent = [];
        let afterDivider = false;
        let responseContent = [];

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const trimmed = line.trim();

            // 检测工具调用
            if (toolEmojis.some(emoji => trimmed.startsWith(emoji))) {
                // 先结束当前的思考块
                if (inThinking && thinkingContent.length > 0) {
                    try {
                        const thinkingHtml = marked.parse(thinkingContent.join('\n'));
                        html += `
                            <div class="thinking-process">
                                <div class="thinking-process-header">
                                    <span class="thinking-process-icon">🤔</span>
                                    <span>思考过程</span>
                                </div>
                                <div class="thinking-process-content">
                                    ${thinkingHtml}
                                </div>
                            </div>
                        `;
                    } catch (e) {
                        console.error('Markdown parse error:', e);
                    }
                    thinkingContent = [];
                    inThinking = false;
                }

                // 渲染工具调用
                let processedCall = this.escapeHtml(trimmed);
                processedCall = processedCall.replace(/`([^`]+)`/g, '<code>$1</code>');
                html += `<div class="tool-call-hint">${processedCall}</div>`;
                continue;
            }

            // 检测思考过程标记（支持多种格式）
            if (/^##?\s*思考过程[：:：]/.test(trimmed) || /^##?\s*思考过程[（(]续[）)]?[：:：]/.test(trimmed) || /^##?\s*Thinking Process[：:：]/.test(trimmed)) {
                // 开始新的思考块
                if (inThinking && thinkingContent.length > 0) {
                    // 结束上一个思考块
                    try {
                        const thinkingHtml = marked.parse(thinkingContent.join('\n'));
                        html += `
                            <div class="thinking-process">
                                <div class="thinking-process-header">
                                    <span class="thinking-process-icon">🤔</span>
                                    <span>思考过程</span>
                                </div>
                                <div class="thinking-process-content">
                                    ${thinkingHtml}
                                </div>
                            </div>
                        `;
                    } catch (e) {
                        console.error('Markdown parse error:', e);
                    }
                    thinkingContent = [];
                }
                inThinking = true;
                continue;
            }

            // 检测分隔符
            if (/^---+$/.test(trimmed)) {
                // 结束思考，开始回复
                if (inThinking && thinkingContent.length > 0) {
                    try {
                        const thinkingHtml = marked.parse(thinkingContent.join('\n'));
                        html += `
                            <div class="thinking-process">
                                <div class="thinking-process-header">
                                    <span class="thinking-process-icon">🤔</span>
                                    <span>思考过程</span>
                                </div>
                                <div class="thinking-process-content">
                                    ${thinkingHtml}
                                </div>
                            </div>
                        `;
                    } catch (e) {
                        console.error('Markdown parse error:', e);
                    }
                }
                // 清空暂存内容（无论是否在思考中）
                thinkingContent = [];
                inThinking = false;

                // 检查后面是否还有内容
                const hasContentAfter = i < lines.length - 1 && lines.slice(i + 1).some(l => l.trim().length > 0);
                if (hasContentAfter && !afterDivider) {
                    html += '<hr class="response-divider">';
                    afterDivider = true;
                }
                continue;
            }

            // 检测回复标记
            if (/^##\s*回[复复][：:]/.test(trimmed)) {
                // 结束思考，开始回复
                if (inThinking && thinkingContent.length > 0) {
                    try {
                        const thinkingHtml = marked.parse(thinkingContent.join('\n'));
                        html += `
                            <div class="thinking-process">
                                <div class="thinking-process-header">
                                    <span class="thinking-process-icon">🤔</span>
                                    <span>思考过程</span>
                                </div>
                                <div class="thinking-process-content">
                                    ${thinkingHtml}
                                </div>
                            </div>
                        `;
                    } catch (e) {
                        console.error('Markdown parse error:', e);
                    }
                }
                // 清空暂存内容（无论是否在思考中）
                thinkingContent = [];
                inThinking = false;
                if (!afterDivider) {
                    html += '<hr class="response-divider">';
                }
                afterDivider = true;
                continue;
            }
            
            // 累积内容
            if (inThinking) {
                thinkingContent.push(line);
            } else if (afterDivider) {
                responseContent.push(line);
            } else {
                // 还没开始思考过程，也不在回复中，暂时累积
                // 这些内容可能是思考过程的一部分，会在下一个思考标记出现时合并
                if (trimmed.length > 0) {
                    thinkingContent.push(line);
                }
            }
        }
        
        // 处理未结束的思考块
        if (inThinking && thinkingContent.length > 0) {
            try {
                const thinkingHtml = marked.parse(thinkingContent.join('\n'));
                html += `
                    <div class="thinking-process">
                        <div class="thinking-process-header">
                            <span class="thinking-process-icon">🤔</span>
                            <span>思考过程</span>
                        </div>
                        <div class="thinking-process-content">
                            ${thinkingHtml}
                        </div>
                    </div>
                `;
            } catch (e) {
                console.error('Markdown parse error:', e);
            }
        }
        
        // 处理回复内容
        if (responseContent.length > 0) {
            try {
                const responseHtml = marked.parse(responseContent.join('\n'));
                html += responseHtml;
            } catch (e) {
                console.error('Markdown parse error:', e);
                html += `<pre>${this.escapeHtml(responseContent.join('\n'))}</pre>`;
            }
        }
        
        return html;
    }
    
    // 下面是旧的复杂逻辑，已经不需要了，但先保留以防万一
    processThinkingAndResponse_OLD(content) {
        const toolEmojis = ['📖', '✅', '✏️', '🔧', '🔍', '📁', '📝', '⚠️'];
        const thinkingHeaders = content.match(/##\s*思考过程[：:]/g);
        const hasMultipleThinking = thinkingHeaders && thinkingHeaders.length > 1;
        
        if (hasMultipleThinking) {
            // 有多个思考过程，需要特殊处理
            // 策略：找到真正的"思考-回复"分隔符（不是思考内部的分隔符）
            
            // 查找所有分隔符
            const dividerPattern = /\n---+\s*\n/g;
            const dividers = [];
            let match;
            while ((match = dividerPattern.exec(content)) !== null) {
                dividers.push({
                    index: match.index,
                    length: match[0].length
                });
            }
            
            // 从后往前检查每个分隔符，找到第一个"后面不是思考过程"的分隔符
            let realDividerIndex = -1;
            for (let i = dividers.length - 1; i >= 0; i--) {
                const divider = dividers[i];
                const afterDivider = content.substring(divider.index + divider.length).trim();
                
                // 检查分隔符后面是否是思考过程
                // 如果以 "## 思考过程" 或包含大量分析词汇，说明还是思考
                const startsWithThinking = /^##\s*思考过程[：:]/.test(afterDivider);
                const hasAnalysisKeywords = /^.{0,200}(根据|需要|技能|步骤|策略|检查|判断|分析|首先|然后|因此|所以)/.test(afterDivider);
                
                if (!startsWithThinking && !hasAnalysisKeywords) {
                    // 这是真正的分隔符
                    realDividerIndex = divider.index;
                    break;
                }
            }
            
            if (realDividerIndex > 0) {
                // 找到了真正的分隔符
                const beforeDivider = content.substring(0, realDividerIndex);
                const afterDivider = content.substring(realDividerIndex).replace(/^\n---+\s*\n/, '').trim();
                
                // 提取工具调用
                let allToolCalls = [];
                let thinkingContent = '';
                
                const lines = beforeDivider.split('\n');
                let contentLines = [];
                
                for (const line of lines) {
                    const trimmed = line.trim();
                    if (toolEmojis.some(emoji => trimmed.startsWith(emoji))) {
                        allToolCalls.push(trimmed);
                    } else {
                        contentLines.push(line);
                    }
                }
                
                // 合并思考内容，去掉标题
                thinkingContent = contentLines.join('\n')
                    .replace(/##\s*思考过程[：:]\s*\n?/g, '')
                    .trim();
                
                // 去掉回复部分的标题
                const finalResponse = afterDivider.replace(/^##\s*回[复复][：:]\s*\n?/, '').trim();
                
                // 生成HTML
                let toolCallsHtml = '';
                if (allToolCalls.length > 0) {
                    toolCallsHtml = allToolCalls.map(call => {
                        let processedCall = this.escapeHtml(call);
                        processedCall = processedCall.replace(/`([^`]+)`/g, '<code>$1</code>');
                        return `<div class="tool-call-hint">${processedCall}</div>`;
                    }).join('');
                }
                
                try {
                    const thinkingHtml = marked.parse(thinkingContent);
                    const responseHtml = marked.parse(finalResponse);
                    
                    return `
                        ${toolCallsHtml}
                        <div class="thinking-process">
                            <div class="thinking-process-header">
                                <span class="thinking-process-icon">🤔</span>
                                <span>思考过程</span>
                            </div>
                            <div class="thinking-process-content">
                                ${thinkingHtml}
                            </div>
                        </div>
                        <hr class="response-divider">
                        ${responseHtml}
                    `;
                } catch (e) {
                    console.error('Markdown parse error:', e);
                    return `<pre>${this.escapeHtml(content)}</pre>`;
                }
            }
            
            // 没有分隔符，还在生成中，暂时不做特殊处理
            // 继续使用下面的单思考过程逻辑
        }
        
        // 单个思考过程的情况，使用原有逻辑
        const lines = content.split('\n');
        let toolCalls = [];
        let contentStart = 0;
        
        // 从开头提取工具调用提示
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (toolEmojis.some(emoji => line.startsWith(emoji))) {
                toolCalls.push(line);
                contentStart = i + 1;
            } else if (line.length > 0) {
                break;
            }
        }
        
        const remainingContent = lines.slice(contentStart).join('\n').trim();
        
        let toolCallsHtml = '';
        if (toolCalls.length > 0) {
            toolCallsHtml = toolCalls.map(call => {
                let processedCall = this.escapeHtml(call);
                processedCall = processedCall.replace(/`([^`]+)`/g, '<code>$1</code>');
                return `<div class="tool-call-hint">${processedCall}</div>`;
            }).join('');
        }
        
        // 检查是否有分隔符（--- 标记思考结束，回复开始）
        const hasDivider = /\n---+\s*\n/m.test(remainingContent);
        
        // 如果没有分隔符，说明还在思考过程中，或者只是纯内容
        if (!hasDivider) {
            // 检查是否包含思考过程标记
            const hasThinkingHeader = /^##\s*思考过程[：:]/m.test(remainingContent) || 
                                      /^思考过程[：:]/m.test(remainingContent) ||
                                      /^##\s*Thinking Process[：:]/m.test(remainingContent);
            
            if (hasThinkingHeader) {
                // 提取思考过程内容（去掉标题）
                let thinking = remainingContent.replace(/^##\s*思考过程[：:]\s*\n?/, '')
                                              .replace(/^思考过程[：:]\s*\n?/, '')
                                              .replace(/^##\s*Thinking Process[：:]\s*\n?/, '');
                
                try {
                    const thinkingHtml = marked.parse(thinking);
                    return `
                        ${toolCallsHtml}
                        <div class="thinking-process">
                            <div class="thinking-process-header">
                                <span class="thinking-process-icon">🤔</span>
                                <span>思考过程</span>
                            </div>
                            <div class="thinking-process-content">
                                ${thinkingHtml}
                            </div>
                        </div>
                    `;
                } catch (e) {
                    console.error('Markdown parse error:', e);
                    return `${toolCallsHtml}<pre>${this.escapeHtml(content)}</pre>`;
                }
            } else {
                // 没有思考标记，直接渲染
                try {
                    return toolCallsHtml + marked.parse(remainingContent);
                } catch (e) {
                    console.error('Markdown parse error:', e);
                    return `${toolCallsHtml}<pre>${this.escapeHtml(remainingContent)}</pre>`;
                }
            }
        }
        
        // 有分隔符时，提取所有思考过程和最终回复
        // 先找到最后一个 --- 分隔符的位置
        const lastDividerMatch = remainingContent.match(/\n(---+)\s*\n(?![\s\S]*\n---+\s*\n)/);
        
        if (lastDividerMatch) {
            const lastDividerPos = lastDividerMatch.index + lastDividerMatch[0].length;
            let thinkingPart = remainingContent.substring(0, lastDividerMatch.index).trim();
            let responsePart = remainingContent.substring(lastDividerPos).trim();
            
            // 去掉回复部分开头的 "## 回复：" 标记
            responsePart = responsePart.replace(/^##\s*回[复复][：:]\s*\n?/, '');
            
            // 提取所有的思考过程（可能有多个）
            const thinkingHeaders = [
                /^##\s*思考过程[：:]\s*\n?/gm,
                /^思考过程[：:]\s*\n?/gm,
                /^##\s*Thinking Process[：:]\s*\n?/gm
            ];
            
            // 清理所有思考过程标题
            for (const headerPattern of thinkingHeaders) {
                thinkingPart = thinkingPart.replace(headerPattern, '');
            }
            
            // 如果思考部分包含多个工具调用输出标记，说明有多轮思考
            // 我们提取最后一个完整的思考过程（通常是最终的综合思考）
            const toolCallPattern = /⏺[^\n]*\n\s*⎿[^\n]*/g;
            const toolCallMatches = [...thinkingPart.matchAll(toolCallPattern)];
            
            if (toolCallMatches.length > 0) {
                // 找到最后一个工具调用输出的位置
                const lastToolCall = toolCallMatches[toolCallMatches.length - 1];
                const lastToolCallEnd = lastToolCall.index + lastToolCall[0].length;
                
                // 提取最后一个思考过程（工具调用之后的内容）
                // 但如果这之后还有"思考过程"标记，从那里开始提取
                const afterLastToolCall = thinkingPart.substring(lastToolCallEnd);
                const finalThinkingMatch = afterLastToolCall.match(/(?:##\s*)?(?:思考过程|Thinking Process)[：:]\s*\n([\s\S]*)/);
                
                if (finalThinkingMatch) {
                    // 找到了明确的最后一个思考过程标记
                    thinkingPart = finalThinkingMatch[1].trim();
                } else {
                    // 没有找到标记，使用工具调用之后的所有内容
                    thinkingPart = afterLastToolCall.trim();
                }
            }
            
            try {
                const thinkingHtml = marked.parse(thinkingPart);
                const responseHtml = marked.parse(responsePart);
                
                return `
                    ${toolCallsHtml}
                    <div class="thinking-process">
                        <div class="thinking-process-header">
                            <span class="thinking-process-icon">🤔</span>
                            <span>思考过程</span>
                        </div>
                        <div class="thinking-process-content">
                            ${thinkingHtml}
                        </div>
                    </div>
                    <hr class="response-divider">
                    ${responseHtml}
                `;
            } catch (e) {
                console.error('Markdown parse error:', e);
                return `${toolCallsHtml}<pre>${this.escapeHtml(content)}</pre>`;
            }
        }
        
        // 没有分隔符，直接渲染
        try {
            return toolCallsHtml + marked.parse(remainingContent);
        } catch (e) {
            console.error('Markdown parse error:', e);
            return `${toolCallsHtml}<pre>${this.escapeHtml(remainingContent)}</pre>`;
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    clearChat() {
        if (confirm('确定要清空对话吗？')) {
            this.messagesContainer.innerHTML = '';
            this.messages = [];
            this.currentAssistantMessage = null;
            this.createNewChat();
        }
    }
    
    // ========== 历史记录管理方法 ==========
    
    loadChatHistories() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            if (stored) {
                this.chatHistories = JSON.parse(stored);
            }
        } catch (e) {
            console.error('加载历史记录失败:', e);
            this.chatHistories = [];
        }
        
        this.createNewChat();
        this.renderHistoryList();
    }
    
    createNewChat() {
        const chatId = Date.now().toString();
        this.currentChatId = chatId;
        this.messages = [];
        this.messagesContainer.innerHTML = '';
        
        const newChat = {
            id: chatId,
            title: '新对话',
            messages: [],
            timestamp: new Date().toLocaleString()
        };
        
        this.chatHistories.unshift(newChat);
        
        // 只保留最多maxHistories个对话
        if (this.chatHistories.length > this.maxHistories) {
            this.chatHistories = this.chatHistories.slice(0, this.maxHistories);
        }
        
        this.saveChatHistories();
        this.renderHistoryList();
    }
    
    saveChatHistories() {
        try {
            // 更新当前对话的消息
            const currentChat = this.chatHistories.find(c => c.id === this.currentChatId);
            if (currentChat) {
                currentChat.messages = this.messages;
                // 更新标题（取第一条用户消息的前30个字符）
                const firstUserMsg = this.messages.find(m => m.role === 'user');
                if (firstUserMsg) {
                    currentChat.title = firstUserMsg.content.substring(0, 30) + (firstUserMsg.content.length > 30 ? '...' : '');
                }
            }
            
            localStorage.setItem(this.storageKey, JSON.stringify(this.chatHistories));
            // 刷新左侧历史列表，保持 UI 与存储同步
            try { this.renderHistoryList(); } catch (e) {}
        } catch (e) {
            console.error('保存历史记录失败:', e);
        }
    }
    
    renderHistoryList() {
        const historyList = document.getElementById('historyList');
        historyList.innerHTML = '';
        
        this.chatHistories.forEach((chat, index) => {
            const item = document.createElement('div');
            item.className = 'history-item';
            if (chat.id === this.currentChatId) {
                item.classList.add('active');
            }
            
            const text = document.createElement('span');
            text.textContent = chat.title || '新对话';
            text.style.flex = '1';
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'history-item-delete';
            deleteBtn.innerHTML = '×';
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteChat(chat.id);
            });
            
            item.appendChild(text);
            item.appendChild(deleteBtn);
            
            item.addEventListener('click', () => this.loadChat(chat.id));
            
            historyList.appendChild(item);
        });
    }
    
    loadChat(chatId) {
        const chat = this.chatHistories.find(c => c.id === chatId);
        if (chat) {
            this.currentChatId = chatId;
            this.messages = JSON.parse(JSON.stringify(chat.messages || []));
            this.messagesContainer.innerHTML = '';
            
            // 重新渲染所有消息
            this.messages.forEach(msg => {
                if (msg.role === 'user') {
                    this.addMessage('user', msg.content);
                } else {
                    // 为了保证历史加载时助手消息为最终的 Markdown 渲染，直接创建元素并做最终渲染
                    const messageDiv = this.createMessageElement('assistant', '');
                    const contentDiv = messageDiv.querySelector('.message-content');
                    this.updateMessageContent(messageDiv, msg.content, contentDiv, true);
                    this.messagesContainer.appendChild(messageDiv);
                }
            });
            
            this.renderHistoryList();
            this.scrollToBottom();
        }
    }
    
    deleteChat(chatId) {
        if (confirm('确定要删除这个对话吗？')) {
            this.chatHistories = this.chatHistories.filter(c => c.id !== chatId);
            this.saveChatHistories();
            
            if (this.currentChatId === chatId) {
                this.createNewChat();
            } else {
                this.renderHistoryList();
            }
        }
    }
    
    clearAllHistories() {
        if (confirm('确定要清空所有历史记录吗？这个操作无法撤销。')) {
            this.chatHistories = [];
            this.saveChatHistories();
            this.createNewChat();
        }
    }
    
    exportChat() {
        if (this.messages.length === 0) {
            alert('当前对话为空，无法导出');
            return;
        }
        // 直接导出为 Markdown（用户要求只导出 Markdown）
        this.exportAsMarkdown();
    }
    
    exportAsJSON() {
        const data = {
            title: this.chatHistories.find(c => c.id === this.currentChatId)?.title || '对话记录',
            timestamp: new Date().toISOString(),
            messages: this.messages
        };
        
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
        this.downloadFile(blob, `chat_${Date.now()}.json`);
    }
    
    exportAsMarkdown() {
        if (this.messages.length === 0) {
            alert('当前对话为空，无法导出');
            return;
        }
        
        const currentChat = this.chatHistories.find(c => c.id === this.currentChatId);
        const title = currentChat?.title || '对话记录';
        const timestamp = new Date().toLocaleString('zh-CN');
        
        let markdown = `# ${title}\n\n`;
        markdown += `**导出时间:** ${timestamp}\n`;
        markdown += `**消息数:** ${this.messages.length}\n\n`;
        markdown += `---\n\n`;
        
        this.messages.forEach((msg, index) => {
            if (msg.role === 'user') {
                markdown += `### 👤 用户提问 (${index + 1})\n\n`;
                markdown += `${this.sanitizeMarkdown(msg.content)}\n\n`;
            } else {
                markdown += `### 🤖 AI回复 (${index + 1})\n\n`;
                markdown += `${this.sanitizeMarkdown(msg.content)}\n\n`;
            }
            markdown += `---\n\n`;
        });
        
        const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
        this.downloadFile(blob, `chat_${timestamp.replace(/[\/\s:]/g, '_')}.md`);
    }
    
    /**
     * 导出为 Word 文档
     */
    exportAsWord() {
        if (this.messages.length === 0) {
            alert('当前对话为空，无法导出');
            return;
        }
        
        try {
            const currentChat = this.chatHistories.find(c => c.id === this.currentChatId);
            const title = currentChat?.title || '对话记录';
            const timestamp = new Date().toLocaleString('zh-CN');
            
            // 构建 Word 文档内容
            const sections = [];
            
            // 标题和头部信息
            sections.push(
                new docx.Paragraph({
                    text: title,
                    heading: docx.HeadingLevel.HEADING_1,
                    bold: true,
                    size: 32
                }),
                new docx.Paragraph(''),
                new docx.Paragraph(`导出时间: ${timestamp}`),
                new docx.Paragraph(`消息数: ${this.messages.length}`),
                new docx.Paragraph('')
            );
            
            // 添加分隔线
            sections.push(
                new docx.Paragraph({
                    border: {
                        bottom: {
                            color: '000000',
                            space: 1,
                            style: docx.BorderStyle.SINGLE,
                            size: 6
                        }
                    }
                })
            );
            
            sections.push(new docx.Paragraph(''));
            
            // 添加每条消息
            this.messages.forEach((msg, index) => {
                const isUser = msg.role === 'user';
                const roleLabel = isUser ? '👤 用户提问' : '🤖 AI回复';
                
                // 消息标题
                sections.push(
                    new docx.Paragraph({
                        text: `${roleLabel} (${index + 1})`,
                        heading: isUser ? docx.HeadingLevel.HEADING_2 : docx.HeadingLevel.HEADING_3,
                        bold: true,
                        shading: {
                            fill: isUser ? 'E8F4F8' : 'F0F8E8'
                        }
                    })
                );
                
                sections.push(new docx.Paragraph(''));
                
                // 消息内容 - 处理 Markdown 格式
                const contentParagraphs = this.parseMarkdownToDocx(msg.content);
                sections.push(...contentParagraphs);
                
                sections.push(new docx.Paragraph(''));
                
                // 分隔线
                sections.push(
                    new docx.Paragraph({
                        border: {
                            bottom: {
                                color: 'CCCCCC',
                                space: 1,
                                style: docx.BorderStyle.SINGLE,
                                size: 3
                            }
                        }
                    })
                );
                
                sections.push(new docx.Paragraph(''));
            });
            
            // 创建文档
            const doc = new docx.Document({
                sections: [
                    {
                        properties: {},
                        children: sections
                    }
                ]
            });
            
            // 生成并下载
            const filename = `chat_${timestamp.replace(/[\/\s:]/g, '_')}.docx`;
            docx.Packer.toBlob(doc).then(blob => {
                this.downloadFile(blob, filename);
            });
            
        } catch (error) {
            console.error('导出Word失败:', error);
            alert('导出Word文档失败，请稍后重试');
        }
    }
    
    /**
     * 将 Markdown 文本转换为 Word 文档格式
     */
    parseMarkdownToDocx(content) {
        const paragraphs = [];
        const lines = content.split('\n');
        
        let currentText = '';
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            
            // 空行处理
            if (line.trim() === '') {
                if (currentText.trim()) {
                    paragraphs.push(new docx.Paragraph(currentText.trim()));
                    currentText = '';
                }
                continue;
            }
            
            // 标题处理
            if (line.startsWith('###')) {
                if (currentText.trim()) {
                    paragraphs.push(new docx.Paragraph(currentText.trim()));
                    currentText = '';
                }
                const titleText = line.replace(/^#+\s*/, '');
                paragraphs.push(new docx.Paragraph({
                    text: titleText,
                    heading: docx.HeadingLevel.HEADING_3,
                    bold: true
                }));
            } else if (line.startsWith('##')) {
                if (currentText.trim()) {
                    paragraphs.push(new docx.Paragraph(currentText.trim()));
                    currentText = '';
                }
                const titleText = line.replace(/^#+\s*/, '');
                paragraphs.push(new docx.Paragraph({
                    text: titleText,
                    heading: docx.HeadingLevel.HEADING_2,
                    bold: true
                }));
            } else if (line.startsWith('#')) {
                if (currentText.trim()) {
                    paragraphs.push(new docx.Paragraph(currentText.trim()));
                    currentText = '';
                }
                const titleText = line.replace(/^#+\s*/, '');
                paragraphs.push(new docx.Paragraph({
                    text: titleText,
                    heading: docx.HeadingLevel.HEADING_1,
                    bold: true
                }));
            } else if (line.startsWith('- ') || line.startsWith('* ')) {
                // 列表项
                if (currentText.trim()) {
                    paragraphs.push(new docx.Paragraph(currentText.trim()));
                    currentText = '';
                }
                const itemText = line.replace(/^[-*]\s*/, '');
                paragraphs.push(new docx.Paragraph({
                    text: itemText,
                    bullet: {
                        level: 0
                    }
                }));
            } else if (line.startsWith('> ')) {
                // 引用
                if (currentText.trim()) {
                    paragraphs.push(new docx.Paragraph(currentText.trim()));
                    currentText = '';
                }
                const quoteText = line.replace(/^>\s*/, '');
                paragraphs.push(new docx.Paragraph({
                    text: quoteText,
                    border: {
                        left: {
                            color: '4472C4',
                            space: 1,
                            style: docx.BorderStyle.SINGLE,
                            size: 12
                        }
                    },
                    indent: {
                        left: 720
                    }
                }));
            } else {
                // 普通文本
                currentText += (currentText ? ' ' : '') + line;
            }
        }
        
        // 最后一段
        if (currentText.trim()) {
            paragraphs.push(new docx.Paragraph(currentText.trim()));
        }
        
        return paragraphs.length > 0 ? paragraphs : [new docx.Paragraph('')];
    }
    
    /**
     * Markdown 内容清理 - 移除过度格式化
     */
    sanitizeMarkdown(content) {
        // 保留基本的 markdown 格式
        return content
            .replace(/\*\*\*/g, '') // 移除多余的星号
            .trim();
    }
    
    downloadFile(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
    
    scrollToBottom() {
        // 滚动到底部 - 需要滚动父容器 (.chat-container)
        if (this.messagesContainer.parentElement) {
            this.messagesContainer.parentElement.scrollTop = 
                this.messagesContainer.parentElement.scrollHeight;
        }
    }
    
    showLoadingIndicator() {
        // 如果已经有加载提示，先移除
        this.removeLoadingIndicator();
        
        // 创建加载消息
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message assistant';
        loadingDiv.id = 'loading-indicator';
        
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'typing-indicator';
        typingIndicator.innerHTML = '<span></span><span></span><span></span>';
        
        loadingDiv.appendChild(typingIndicator);
        this.messagesContainer.appendChild(loadingDiv);
        this.scrollToBottom();
    }
    
    removeLoadingIndicator() {
        const loadingIndicator = document.getElementById('loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
    }
    
    // =========================
    // 侧边栏标签切换
    // =========================
    
    initSidebarTabs() {
        const tabs = document.querySelectorAll('.sidebar-tab');
        if (!tabs || tabs.length === 0) {
            console.warn('未找到侧边栏标签');
            return;
        }
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                this.activateSidebarPanel(tab.dataset.panel);
            });
        });

        // 提供全局兜底（防止点击绑定失效）
        window.__openSkillsTab = () => this.activateSidebarPanel('skills');
        window.__openHistoryTab = () => this.activateSidebarPanel('history');
    }

    activateSidebarPanel(panelName) {
        const tabs = document.querySelectorAll('.sidebar-tab');
        tabs.forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.sidebar-panel').forEach(p => p.classList.remove('active'));

        const tab = document.querySelector(`.sidebar-tab[data-panel="${panelName}"]`);
        if (tab) {
            tab.classList.add('active');
        }
        const panelId = panelName + 'Panel';
        const panel = document.getElementById(panelId);
        if (panel) {
            panel.classList.add('active');
        }

        if (panelName === 'skills') {
            this.loadSkillsList();
            this.openDefaultSkillEditor();
        }
    }
    
    // =========================
    // Skills 管理
    // =========================
    
    async loadSkillsList() {
        try {
            const container = document.getElementById('skillsList');
            if (container) {
                container.innerHTML = '<div class="skills-empty">加载中...</div>';
            }
            const response = await fetch('/api/skills');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            this.skillsLoaded = true;
            this.renderSkillsList(data.skills || []);
        } catch (e) {
            console.error('加载 Skills 列表失败:', e);
            this.renderSkillsError('加载技能列表失败，请稍后重试');
        }
    }
    
    renderSkillsList(skills) {
        const container = document.getElementById('skillsList');
        if (!container) return;
        if (!skills.length) {
            container.innerHTML = '<div class="skills-empty">暂无可编辑的技能</div>';
            return;
        }
        
        container.innerHTML = skills.map(skill => `
            <div class="skill-item" data-skill-name="${skill.name}">
                <div class="skill-name">📋 ${skill.name}</div>
                <div class="skill-desc">${skill.description || '暂无描述'}</div>
            </div>
        `).join('');
        
        // 绑定点击事件
        container.querySelectorAll('.skill-item').forEach(item => {
            item.addEventListener('click', () => {
                this.openSkillEditor(item.dataset.skillName);
            });
        });
    }

    renderSkillsError(message) {
        const container = document.getElementById('skillsList');
        if (!container) return;
        container.innerHTML = `<div class="skills-empty">${message}</div>`;
    }
    
    // =========================
    // Skill 编辑器
    // =========================
    
    initSkillEditor() {
        const overlay = document.getElementById('skillEditorOverlay');
        const saveBtn = document.getElementById('skillSaveBtn');
        const closeBtn = document.getElementById('skillCloseBtn');
        const textarea = document.getElementById('skillEditorContent');
        
        if (!overlay || !saveBtn || !closeBtn || !textarea) return;
        
        // 保存按钮
        saveBtn.addEventListener('click', () => this.saveSkill());
        
        // 关闭按钮
        closeBtn.addEventListener('click', () => this.closeSkillEditor());
        
        // 点击遮罩关闭
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.closeSkillEditor();
            }
        });
        
        // 监听内容变化
        textarea.addEventListener('input', () => {
            this.skillModified = textarea.value !== this.originalSkillContent;
            this.updateSkillEditorStatus();
        });
        
        // ESC 关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && overlay.classList.contains('active')) {
                this.closeSkillEditor();
            }
            // Ctrl+S / Cmd+S 保存
            if ((e.ctrlKey || e.metaKey) && e.key === 's' && overlay.classList.contains('active')) {
                e.preventDefault();
                this.saveSkill();
            }
        });
    }
    
    async openSkillEditor(skillName) {
        const overlay = document.getElementById('skillEditorOverlay');
        const title = document.getElementById('skillEditorTitle');
        const textarea = document.getElementById('skillEditorContent');
        const status = document.getElementById('skillEditorStatus');
        
        this.currentSkillName = skillName;
        title.textContent = skillName;
        textarea.value = '加载中...';
        textarea.disabled = true;
        status.textContent = '加载中...';
        status.className = 'skill-editor-status';
        
        overlay.classList.add('active');
        
        try {
            const response = await fetch(`/api/skills/${skillName}`);
            const data = await response.json();
            
            this.originalSkillContent = data.content;
            textarea.value = data.content;
            textarea.disabled = false;
            this.skillModified = false;
            this.updateSkillEditorStatus();
            
            // 聚焦到编辑器
            textarea.focus();
        } catch (e) {
            console.error('加载 Skill 内容失败:', e);
            status.textContent = '加载失败: ' + e.message;
            status.className = 'skill-editor-status';
        }
    }

    openDefaultSkillEditor() {
        if (!this.defaultSkillName) return;
        const overlay = document.getElementById('skillEditorOverlay');
        if (overlay && overlay.classList.contains('active') && this.currentSkillName === this.defaultSkillName) {
            return;
        }
        this.openSkillEditor(this.defaultSkillName);
    }
    
    async saveSkill() {
        if (!this.currentSkillName || !this.skillModified) return;
        
        const textarea = document.getElementById('skillEditorContent');
        const status = document.getElementById('skillEditorStatus');
        const saveBtn = document.getElementById('skillSaveBtn');
        
        saveBtn.disabled = true;
        status.textContent = '保存中...';
        
        try {
            const response = await fetch(`/api/skills/${this.currentSkillName}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: textarea.value
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.originalSkillContent = textarea.value;
                this.skillModified = false;
                status.textContent = '✓ 保存成功，已生效！';
                status.className = 'skill-editor-status saved';
                
                // 重新加载 Skills 列表（更新描述等）
                this.loadSkillsList();
            } else {
                status.textContent = '保存失败: ' + (data.error || '未知错误');
                status.className = 'skill-editor-status';
            }
        } catch (e) {
            console.error('保存 Skill 失败:', e);
            status.textContent = '保存失败: ' + e.message;
            status.className = 'skill-editor-status';
        } finally {
            saveBtn.disabled = false;
        }
    }
    
    closeSkillEditor() {
        if (this.skillModified) {
            if (!confirm('有未保存的更改，确定要关闭吗？')) {
                return;
            }
        }
        
        const overlay = document.getElementById('skillEditorOverlay');
        overlay.classList.remove('active');
        this.currentSkillName = null;
        this.originalSkillContent = '';
        this.skillModified = false;
    }
    
    updateSkillEditorStatus() {
        const status = document.getElementById('skillEditorStatus');
        const saveBtn = document.getElementById('skillSaveBtn');
        
        if (this.skillModified) {
            status.textContent = '● 已修改（未保存）';
            status.className = 'skill-editor-status modified';
            saveBtn.disabled = false;
        } else {
            status.textContent = '就绪';
            status.className = 'skill-editor-status';
            saveBtn.disabled = true;
        }
    }
}

// 初始化应用
const app = new ChatAppWS();
