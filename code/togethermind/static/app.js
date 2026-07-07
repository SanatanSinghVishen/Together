// Unique Session ID for the chat session
const sessionId = "session_" + Math.random().toString(36).substr(2, 9);

// =====================================================================
// REUSABLE STREAMING HELPER
// =====================================================================
async function handleStreamingRequest(url, payload, onStep, onResult, onError) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || `Server error status ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop(); // keep last incomplete line
            
            for (let line of lines) {
                if (line.startsWith("data: ")) {
                    const dataStr = line.substring(6).trim();
                    if (!dataStr) continue;
                    try {
                        const item = JSON.parse(dataStr);
                        if (item.type === "step") {
                            onStep(item.data);
                        } else if (item.type === "result") {
                            onResult(item.data);
                        } else if (item.type === "error") {
                            onError(new Error(item.message));
                        }
                    } catch (parseErr) {
                        console.error("Failed to parse stream item:", parseErr, dataStr);
                    }
                }
            }
        }
    } catch (err) {
        onError(err);
    }
}

// =====================================================================
// SEMANTIC MARKDOWN PARSER
// =====================================================================
function formatMarkdown(text) {
    if (!text) return "";
    
    const lines = text.split('\n');
    let html = "";
    let inList = false;
    
    for (let line of lines) {
        let trimmed = line.trim();
        if (!trimmed) {
            if (inList) {
                html += "</ul>";
                inList = false;
            }
            continue;
        }
        
        if (trimmed.startsWith("### ")) {
            if (inList) { html += "</ul>"; inList = false; }
            html += `<h4 class="markdown-h3" style="font-family:var(--font-family-display); font-size:16px; font-weight:700; margin:16px 0 8px 0; color:var(--color-signal-orange);">${trimmed.substring(4)}</h4>`;
            continue;
        }
        if (trimmed.startsWith("## ")) {
            if (inList) { html += "</ul>"; inList = false; }
            html += `<h3 class="markdown-h2" style="font-family:var(--font-family-display); font-size:18px; font-weight:700; margin:20px 0 10px 0;">${trimmed.substring(3)}</h3>`;
            continue;
        }
        if (trimmed.startsWith("# ")) {
            if (inList) { html += "</ul>"; inList = false; }
            html += `<h2 class="markdown-h1" style="font-family:var(--font-family-display); font-size:22px; font-weight:700; margin:24px 0 12px 0;">${trimmed.substring(2)}</h2>`;
            continue;
        }
        
        if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
            if (!inList) {
                html += "<ul class='markdown-list' style='list-style:none; padding-left:14px; margin-bottom:16px;'>";
                inList = true;
            }
            let itemContent = trimmed.substring(2);
            itemContent = parseInlineStyles(itemContent);
            html += `<li style='position:relative; margin-bottom:6px; font-size:14.5px;'>${itemContent}</li>`;
            continue;
        }
        
        if (inList) {
            html += "</ul>";
            inList = false;
        }
        let paraContent = parseInlineStyles(trimmed);
        html += `<p class="markdown-para" style="margin-bottom:12px; font-size:15px; line-height:1.55;">${paraContent}</p>`;
    }
    
    if (inList) {
        html += "</ul>";
    }
    
    return html;
}

function parseInlineStyles(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/`([^`]+)`/g, "<code>$1</code>");
}

// =====================================================================
// TOOL 01: OPERATOR MEMORY LOGIC
// =====================================================================
const memoryStatusDot = document.getElementById("memory-status-dot");
const memoryStatusText = document.getElementById("memory-status-text");
const memoryDocCount = document.getElementById("memory-doc-count");
const btnMemoryIngest = document.getElementById("btn-memory-ingest");
const memoryQueryForm = document.getElementById("memory-query-form");
const memoryChatInput = document.getElementById("memory-chat-input");
const btnMemorySubmit = document.getElementById("btn-memory-submit");

const memoryPlaceholder = document.getElementById("memory-placeholder");
const memoryResponseCard = document.getElementById("memory-response-card");
const memoryActiveQuery = document.getElementById("memory-active-query");
const memoryActiveStatus = document.getElementById("memory-active-status");
const memoryBadgeEscalated = document.getElementById("memory-badge-escalated");
const memoryBadgeSynthesized = document.getElementById("memory-badge-synthesized");
const memoryAnswerText = document.getElementById("memory-answer-text");
const memoryCitationsPanel = document.getElementById("memory-citations-panel");
const memoryCitationsGrid = document.getElementById("memory-citations-grid");

const memoryTraceHeader = document.getElementById("memory-trace-header");
const memoryTraceBody = document.getElementById("memory-trace-body");

async function checkMemoryStatus() {
    try {
        const res = await fetch("/api/status");
        if (!res.ok) throw new Error(`Status API returned status ${res.status}`);
        const data = await res.json();
        
        if (data.status === "active") {
            memoryStatusDot.className = "status-indicator-dot active";
            memoryStatusText.innerText = "Active Library";
            memoryDocCount.innerText = `${data.document_count} chunks`;
        } else {
            memoryStatusDot.className = "status-indicator-dot empty";
            memoryStatusText.innerText = "Empty Lib";
            memoryDocCount.innerText = "0 chunks";
        }
    } catch (err) {
        console.error("Error checking memory status:", err);
        memoryStatusDot.className = "status-indicator-dot empty";
        memoryStatusText.innerText = "Offline";
        memoryDocCount.innerText = "-";
    }
}

btnMemoryIngest.addEventListener("click", async () => {
    btnMemoryIngest.disabled = true;
    btnMemoryIngest.innerText = "INDEXING PLAYBOOKS...";
    memoryStatusText.innerText = "Rebuilding...";
    
    try {
        const res = await fetch("/api/ingest", { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || `Ingest API returned ${res.status}`);
        
        if (data.status === "success") {
            alert("Knowledge base successfully re-indexed into ChromaDB!");
        } else {
            alert("Ingestion error: " + data.message);
        }
    } catch (err) {
        alert("Network error: " + err.message);
    } finally {
        btnMemoryIngest.disabled = false;
        btnMemoryIngest.innerText = "RE-INDEX PLAYBOOKS";
        checkMemoryStatus();
    }
});

memoryQueryForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const queryVal = memoryChatInput.value.trim();
    if (!queryVal) return;

    btnMemorySubmit.disabled = true;
    btnMemorySubmit.innerText = "QUERYING AGENT...";
    
    memoryPlaceholderFounder.classList.add("hidden");
    memoryPlaceholderInvestor.classList.add("hidden");
    memoryResponseCard.classList.remove("hidden");
    memoryActiveQuery.innerText = `"${queryVal}"`;
    memoryActiveStatus.innerText = "Connecting to agent...";
    memoryBadgeEscalated.classList.add("hidden");
    memoryBadgeSynthesized.classList.add("hidden");
    memoryAnswerText.innerHTML = `<p class="loading-text">Searching VC guides and essays...</p>`;
    memoryCitationsPanel.classList.add("hidden");
    
    memoryTraceBody.innerHTML = "";
    memoryTraceBody.classList.remove("hidden");
    memoryTraceHeader.classList.add("expanded");

    const onStep = (step) => {
        memoryActiveStatus.innerText = `Agent Running: ${step.action}`;
        const stepDiv = document.createElement("div");
        stepDiv.className = "reasoning-step";
        stepDiv.innerHTML = `
            <div class="step-header">[Step ${step.step_num}] ${step.agent_name} -> ${step.action}</div>
            <div class="step-thought">> Thought: ${step.thought}</div>
            ${Object.keys(step.details).length > 0 ? `<div style="color: var(--color-slate-gray); margin-top:2px;">> Details: ${JSON.stringify(step.details)}</div>` : ""}
        `;
        memoryTraceBody.appendChild(stepDiv);
        memoryTraceBody.scrollTop = memoryTraceBody.scrollHeight;
    };

    const onResult = (data) => {
        memoryActiveStatus.innerText = data.escalate ? "Escalated to GP" : "Query synthesis complete";
        if (data.escalate) {
            memoryBadgeEscalated.classList.remove("hidden");
        } else {
            memoryBadgeSynthesized.classList.remove("hidden");
        }
        memoryAnswerText.innerHTML = formatMarkdown(data.answer);

        if (data.citations && data.citations.length > 0) {
            memoryCitationsPanel.classList.remove("hidden");
            memoryCitationsGrid.innerHTML = "";
            data.citations.forEach(c => {
                const card = document.createElement("a");
                card.className = "citation-pill";
                card.href = c.url;
                card.target = "_blank";
                card.innerHTML = `
                    <strong>${c.title}</strong>
                    <span class="citation-domain">${c.url.split('/')[2] || 'Local Source'}</span>
                `;
                memoryCitationsGrid.appendChild(card);
            });
        }
        btnMemorySubmit.disabled = false;
        btnMemorySubmit.innerText = "QUERY PLAYBOOKS";
    };

    const onError = (err) => {
        alert("Query failed: " + err.message);
        console.error(err);
        memoryActiveStatus.innerText = "Failed";
        memoryAnswerText.innerHTML = `<p style="color:var(--color-critical);">Error: ${err.message}</p>`;
        btnMemorySubmit.disabled = false;
        btnMemorySubmit.innerText = "QUERY PLAYBOOKS";
    };

    await handleStreamingRequest(
        "/api/query/stream",
        { query: queryVal, session_id: sessionId },
        onStep,
        onResult,
        onError
    );
});

// Custom Document Uploads logic
const memoryAddDocForm = document.getElementById("memory-add-doc-form");
const fileDropZone = document.getElementById("file-drop-zone");
const fileDropText = document.getElementById("file-drop-text");
const memoryFileInput = document.getElementById("memory-file-input");
const btnMemoryAddDoc = document.getElementById("btn-memory-add-doc");

let selectedPlaybookFile = null;

fileDropZone.addEventListener("click", () => {
    memoryFileInput.click();
});

memoryFileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
        handleFileSelection(e.target.files[0]);
    }
});

fileDropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    fileDropZone.style.borderColor = "var(--color-signal-orange)";
});

fileDropZone.addEventListener("dragleave", (e) => {
    e.preventDefault();
    fileDropZone.style.borderColor = "#E4DFD5";
});

fileDropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    fileDropZone.style.borderColor = "#E4DFD5";
    if (e.dataTransfer.files.length > 0) {
        handleFileSelection(e.dataTransfer.files[0]);
    }
});

function handleFileSelection(file) {
    selectedPlaybookFile = file;
    const sizeKB = (file.size / 1024).toFixed(1);
    fileDropText.innerText = `${file.name} (${sizeKB} KB)`;
    btnMemoryAddDoc.disabled = false;
    btnMemoryAddDoc.style.opacity = "1.0";
    btnMemoryAddDoc.style.cursor = "pointer";
}

memoryAddDocForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!selectedPlaybookFile) return;
    
    btnMemoryAddDoc.disabled = true;
    btnMemoryAddDoc.innerText = "READING FILE...";
    
    const reader = new FileReader();
    reader.onload = async (event) => {
        const dataUrlParts = event.target.result.split(',');
        const base64Content = dataUrlParts[1];
        
        let titleVal = selectedPlaybookFile.name.replace(/\.[^/.]+$/, "");
        titleVal = titleVal.replace(/[_\-]/g, " ");
        titleVal = titleVal.split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
        
        const ext = selectedPlaybookFile.name.split('.').pop().toLowerCase();
        let fileType = "txt";
        if (ext === "pdf") fileType = "pdf";
        if (ext === "md") fileType = "md";
        
        btnMemoryAddDoc.innerText = "UPLOADING & EMBEDDING...";
        
        try {
            const response = await fetch("/api/documents/add", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: titleVal,
                    author: "Partner",
                    content: base64Content,
                    is_base64: true,
                    file_type: fileType
                })
            });
            
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || `Server error status ${response.status}`);
            
            alert(`Playbook successfully uploaded! Created ${data.chunk_count} vector embedding chunks for "${titleVal}".`);
            
            selectedPlaybookFile = null;
            fileDropText.innerText = "Drag & drop or click to browse";
            btnMemoryAddDoc.disabled = true;
            btnMemoryAddDoc.style.opacity = "0.6";
            btnMemoryAddDoc.style.cursor = "not-allowed";
            memoryFileInput.value = "";
            checkMemoryStatus();
        } catch (err) {
            alert("Upload failed: " + err.message);
            console.error(err);
        } finally {
            btnMemoryAddDoc.disabled = false;
            btnMemoryAddDoc.innerText = "UPLOAD PLAYBOOK TO LIBRARY";
        }
    };
    reader.readAsDataURL(selectedPlaybookFile);
});

memoryTraceHeader.addEventListener("click", () => {
    memoryTraceBody.classList.toggle("hidden");
    memoryTraceHeader.classList.toggle("expanded");
});

const btnTabFounder = document.getElementById("btn-tab-founder");
const btnTabInvestor = document.getElementById("btn-tab-investor");
const deckPanelFounder = document.getElementById("deck-panel-founder");
const deckPanelInvestor = document.getElementById("deck-panel-investor");

const memoryPlaceholderFounder = document.getElementById("memory-placeholder-founder");
const memoryPlaceholderInvestor = document.getElementById("memory-placeholder-investor");

btnTabFounder.addEventListener("click", () => {
    btnTabFounder.classList.add("active");
    btnTabInvestor.classList.remove("active");
    deckPanelFounder.classList.remove("hidden");
    deckPanelInvestor.classList.add("hidden");
    
    memoryResponseCard.classList.add("hidden");
    memoryPlaceholderFounder.classList.remove("hidden");
    memoryPlaceholderInvestor.classList.add("hidden");
});

btnTabInvestor.addEventListener("click", () => {
    btnTabInvestor.classList.add("active");
    btnTabFounder.classList.remove("active");
    deckPanelInvestor.classList.remove("hidden");
    deckPanelFounder.classList.add("hidden");
    
    memoryResponseCard.classList.add("hidden");
    memoryPlaceholderInvestor.classList.remove("hidden");
    memoryPlaceholderFounder.classList.add("hidden");
});

// Initialization
checkMemoryStatus();
