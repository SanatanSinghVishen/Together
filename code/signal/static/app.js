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
// TOOL 02: PORTFOLIO PULSE LOGIC
// =====================================================================
const pulseWeekSelector = document.getElementById("pulse-week-selector");
const btnPulseTriage = document.getElementById("btn-pulse-triage");
const pulseCompaniesList = document.getElementById("pulse-companies-list");

const pulsePlaceholder = document.getElementById("pulse-placeholder");
const pulseBriefingWorkspace = document.getElementById("pulse-briefing-workspace");
const pulseReportDate = document.getElementById("pulse-report-date");
const pulseSummaryText = document.getElementById("pulse-summary-text");
const pulseTriageGrid = document.getElementById("pulse-triage-grid");

const pulseTraceHeader = document.getElementById("pulse-trace-header");
const pulseTraceBody = document.getElementById("pulse-trace-body");

async function loadPulseIndex() {
    try {
        const res = await fetch("/api/companies");
        if (!res.ok) throw new Error(`Companies API status ${res.status}`);
        const companies = await res.json();
        
        pulseCompaniesList.innerHTML = "";
        companies.forEach(c => {
            const el = document.createElement("div");
            el.className = "company-index-item";
            el.innerHTML = `
                <span class="company-name-tag">${c.name}</span>
                <span class="company-stage-tag">${c.stage}</span>
            `;
            el.addEventListener("click", () => showCompanyModal(c.id));
            pulseCompaniesList.appendChild(el);
        });
    } catch (err) {
        console.error("Error loading pulse companies sidebar:", err);
    }
}

btnPulseTriage.addEventListener("click", async () => {
    const selectedWeek = parseInt(pulseWeekSelector.value);
    btnPulseTriage.disabled = true;
    btnPulseTriage.innerText = "RUNNING TRIAGE...";
    
    pulsePlaceholder.classList.add("hidden");
    pulseBriefingWorkspace.classList.remove("hidden");
    
    pulseReportDate.innerText = `Weekly Report - Week ${selectedWeek}`;
    pulseSummaryText.innerHTML = `<p class="loading-text">Reviewing updates and checking health metrics history...</p>`;
    pulseTriageGrid.innerHTML = "";
    
    pulseTraceBody.innerHTML = "";
    pulseTraceBody.classList.remove("hidden");
    pulseTraceHeader.classList.add("expanded");

    const onStep = (step) => {
        const stepDiv = document.createElement("div");
        stepDiv.className = "reasoning-step";
        stepDiv.innerHTML = `
            <div class="step-header">[Step ${step.step_num}] ${step.agent_name} -> ${step.action}</div>
            <div class="step-thought">> Thought: ${step.thought}</div>
            ${Object.keys(step.details).length > 0 ? `<div style="color: var(--color-slate-gray); margin-top:2px;">> Details: ${JSON.stringify(step.details)}</div>` : ""}
        `;
        pulseTraceBody.appendChild(stepDiv);
        pulseTraceBody.scrollTop = pulseTraceBody.scrollHeight;
    };

    const onResult = (data) => {
        pulseSummaryText.innerHTML = formatMarkdown(data.summary);
        pulseTriageGrid.innerHTML = "";
        data.ranked_portfolio.forEach(company => {
            const card = document.createElement("div");
            let labelClass = "stable";
            if (company.urgency_label === "CRITICAL") labelClass = "critical";
            if (company.urgency_label === "WARNING") labelClass = "warning";
            
            card.className = `triage-card ${labelClass}`;
            card.innerHTML = `
                <div class="triage-card-header">
                    <div>
                        <h3>${company.company_name}</h3>
                        <span class="status-badge ${labelClass}">${company.urgency_label}</span>
                    </div>
                    <span class="urgency-score-badge">${company.urgency_score.toFixed(1)}/10.0</span>
                </div>
                <p class="triage-reason">${company.reason}</p>
                <div class="signals-preview-box">
                    <div class="signal-row-detail"><span class="sig-lbl">REVENUE TREND:</span><span class="sig-val">${company.signals.revenue_trend.toUpperCase()}</span></div>
                    <div class="signal-row-detail"><span class="sig-lbl">FOUNDER SENTIMENT:</span><span class="sig-val">${company.signals.sentiment.toFixed(2)}</span></div>
                    ${company.signals.blockers.length > 0 ? `<div class="signal-row-detail"><span class="sig-lbl">BLOCKERS:</span><span class="sig-val">${company.signals.blockers.join(', ')}</span></div>` : ""}
                </div>
                ${company.deviations.length > 0 ? `
                    <div class="deviations-badge-list">
                        ${company.deviations.map(d => `<div class="deviation-badge-item"><span class="accent-dot"></span> ${d}</div>`).join('')}
                    </div>
                ` : ""}
                <div class="suggested-action-box">
                    <strong>Suggested Action:</strong><br>${company.suggested_action}
                </div>
                <button class="mc-btn-secondary full-width" onclick="showCompanyModal('${company.company_id}')" style="font-size:12px; padding:8px 14px;">
                    Inspect Company Logs
                </button>
            `;
            pulseTriageGrid.appendChild(card);
        });
        btnPulseTriage.disabled = false;
        btnPulseTriage.innerText = "RUN TRIAGE PIPELINE";
    };

    const onError = (err) => {
        alert("Triage failed: " + err.message);
        console.error(err);
        pulseSummaryText.innerHTML = `<p style="color:var(--color-critical);">Pipeline execution crashed: ${err.message}</p>`;
        btnPulseTriage.disabled = false;
        btnPulseTriage.innerText = "RUN TRIAGE PIPELINE";
    };

    await handleStreamingRequest(
        "/api/briefing/stream",
        { week: selectedWeek },
        onStep,
        onResult,
        onError
    );
});

pulseTraceHeader.addEventListener("click", () => {
    pulseTraceBody.classList.toggle("hidden");
    pulseTraceHeader.classList.toggle("expanded");
});

// Onboarding acquired company form
const pulseAddCompanyForm = document.getElementById("pulse-add-company-form");
const pulseAddIdInput = document.getElementById("pulse-add-id-input");
const pulseAddUrlInput = document.getElementById("pulse-add-url-input");
const manualFieldsToggle = document.getElementById("manual-fields-toggle");
const manualCompanyFields = document.getElementById("manual-company-fields");
const pulseAddNameInput = document.getElementById("pulse-add-name-input");
const pulseAddSectorInput = document.getElementById("pulse-add-sector-input");
const pulseAddStageInput = document.getElementById("pulse-add-stage-input");
const pulseAddDescInput = document.getElementById("pulse-add-desc-input");
const btnPulseAddCompany = document.getElementById("btn-pulse-add-company");

manualFieldsToggle.addEventListener("click", () => {
    manualCompanyFields.classList.toggle("hidden");
    if (manualCompanyFields.classList.contains("hidden")) {
        manualFieldsToggle.innerText = "Show manual input fields";
    } else {
        manualFieldsToggle.innerText = "Hide manual input fields";
    }
});

pulseAddCompanyForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const idVal = pulseAddIdInput.value.trim().toLowerCase();
    const urlVal = pulseAddUrlInput.value.trim();
    if (!idVal) return;
    
    btnPulseAddCompany.disabled = true;
    btnPulseAddCompany.innerText = "ONBOARDING STARTUP...";
    
    let payload = { id: idVal };
    if (urlVal) payload.scrape_url = urlVal;
    
    if (!manualCompanyFields.classList.contains("hidden")) {
        const nameVal = pulseAddNameInput.value.trim();
        const sectorVal = pulseAddSectorInput.value.trim();
        const stageVal = pulseAddStageInput.value.trim();
        const descVal = pulseAddDescInput.value.trim();
        if (nameVal) payload.name = nameVal;
        if (sectorVal) payload.sector = sectorVal;
        if (stageVal) payload.stage = stageVal;
        if (descVal) payload.description = descVal;
    }
    
    try {
        const response = await fetch("/api/company/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || `Server returned status ${response.status}`);
        
        alert(`Startup "${data.company.name}" successfully onboarded into portfolio database!`);
        pulseAddIdInput.value = "";
        pulseAddUrlInput.value = "";
        pulseAddNameInput.value = "";
        pulseAddSectorInput.value = "";
        pulseAddStageInput.value = "";
        pulseAddDescInput.value = "";
        manualCompanyFields.classList.add("hidden");
        manualFieldsToggle.innerText = "Show manual input fields";
        loadPulseIndex();
    } catch (err) {
        alert("Onboarding failed: " + err.message);
        console.error(err);
    } finally {
        btnPulseAddCompany.disabled = false;
        btnPulseAddCompany.innerText = "ONBOARD ACQUIRED STARTUP";
    }
});

// Modal Logic
const globalCompanyModal = document.getElementById("global-company-modal");
const btnCloseModal = document.getElementById("btn-close-modal");
const modalCompanyTitle = document.getElementById("modal-company-title");
const tabBtnProfile = document.getElementById("tab-btn-profile");
const tabBtnHistory = document.getElementById("tab-btn-history");
const tabContentProfile = document.getElementById("tab-content-profile");
const tabContentHistory = document.getElementById("tab-content-history");

const modalValSector = document.getElementById("modal-val-sector");
const modalValStage = document.getElementById("modal-val-stage");
const modalValFounded = document.getElementById("modal-val-founded");
const modalValFounders = document.getElementById("modal-val-founders");
const modalValDesc = document.getElementById("modal-val-desc");
const modalValThesis = document.getElementById("modal-val-thesis");
const modalValTimeline = document.getElementById("modal-val-timeline");

async function showCompanyModal(companyId) {
    try {
        const res = await fetch(`/api/company/${companyId}/history`);
        if (!res.ok) throw new Error(`History API status ${res.status}`);
        const data = await res.json();
        
        modalCompanyTitle.innerText = `Company Profile: ${data.profile.name.toUpperCase()}`;
        modalValSector.innerText = data.profile.sector;
        modalValStage.innerText = data.profile.stage;
        modalValFounded.innerText = data.profile.founded;
        modalValFounders.innerText = data.profile.founders.join(", ");
        modalValDesc.innerText = data.profile.description;
        modalValThesis.innerText = data.profile.investment_thesis;

        modalValTimeline.innerHTML = "";
        if (data.updates.length === 0) {
            modalValTimeline.innerHTML = "<p>No updates logged yet.</p>";
        } else {
            const sorted = data.updates.sort((a,b) => b.week - a.week);
            sorted.forEach(u => {
                const signals = data.signals.find(s => s.week === u.week);
                let priorityClass = "";
                if (signals) {
                    if (signals.red_flags.length > 0) {
                        priorityClass = "critical-item";
                    } else if (signals.revenue_trend === "down") {
                        priorityClass = "warning-item";
                    }
                }
                const item = document.createElement("div");
                item.className = `timeline-item ${priorityClass}`;
                item.innerHTML = `
                    <div class="timeline-date">${u.date} - Week ${u.week}</div>
                    <div class="timeline-title">Update by Author: ${u.author.toUpperCase()}</div>
                    <div class="timeline-text">"${u.update_text}"</div>
                    ${signals ? `
                        <div class="signals-preview-box" style="margin-top:8px; background-color:var(--color-canvas);">
                            <div class="signal-row-detail"><span class="sig-lbl">REVENUE DETAIL:</span><span class="sig-val">${signals.revenue_detail}</span></div>
                            <div class="signal-row-detail"><span class="sig-lbl">HIRING STATUS:</span><span class="sig-val">${signals.hiring_status}</span></div>
                            ${signals.red_flags.length > 0 ? `<div class="signal-row-detail" style="color:var(--color-critical);"><span class="sig-lbl">RED FLAGS:</span><span class="sig-val">${signals.red_flags.join(', ')}</span></div>` : ""}
                        </div>
                    ` : ""}
                `;
                modalValTimeline.appendChild(item);
            });
        }
        switchTab("profile");
        globalCompanyModal.classList.remove("hidden");
    } catch (err) {
        alert("Failed to load company details: " + err.message);
        console.error(err);
    }
}

function switchTab(tabType) {
    if (tabType === "profile") {
        tabBtnProfile.classList.add("active");
        tabBtnHistory.classList.remove("active");
        tabContentProfile.classList.remove("hidden");
        tabContentHistory.classList.add("hidden");
    } else {
        tabBtnProfile.classList.remove("active");
        tabBtnHistory.classList.add("active");
        tabContentProfile.classList.add("hidden");
        tabContentHistory.classList.remove("hidden");
    }
}

tabBtnProfile.addEventListener("click", () => switchTab("profile"));
tabBtnHistory.addEventListener("click", () => switchTab("history"));
btnCloseModal.addEventListener("click", () => { globalCompanyModal.classList.add("hidden"); });
globalCompanyModal.addEventListener("click", (e) => {
    if (e.target === globalCompanyModal) { globalCompanyModal.classList.add("hidden"); }
});

// Initialization
loadPulseIndex();
