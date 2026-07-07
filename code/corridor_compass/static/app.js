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
// TOOL 03: CORRIDOR COMPASS GTM AUDITOR LOGIC
// =====================================================================
const compassCompaniesList = document.getElementById("compass-companies-list");
const compassBenchmarksList = document.getElementById("compass-benchmarks-list");
const compassUrlInput = document.getElementById("compass-url-input");
const compassTextInput = document.getElementById("compass-text-input");
const compassCountryInput = document.getElementById("compass-country-input");
const compassAuditForm = document.getElementById("compass-audit-form");
const btnCompassAudit = document.getElementById("btn-compass-audit");

const compassPlaceholder = document.getElementById("compass-placeholder");
const compassLoader = document.getElementById("compass-loader");
const compassLoaderTitle = document.getElementById("compass-loader-title");
const compassLoaderDesc = document.getElementById("compass-loader-desc");

const compassScorecardWorkspace = document.getElementById("compass-scorecard-workspace");
const compassScoreVal = document.getElementById("compass-score-val");
const compassCompanyTitle = document.getElementById("compass-company-title");
const compassReadinessTier = document.getElementById("compass-readiness-tier");
const compassSynthesisText = document.getElementById("compass-synthesis-text");
const compassCriticsGrid = document.getElementById("compass-critics-grid");
const compassDisagreementsCard = document.getElementById("compass-disagreements-card");
const compassDisagreementsList = document.getElementById("compass-disagreements-list");
const compassActionsContainer = document.getElementById("compass-actions-container");

const compassTraceHeader = document.getElementById("compass-trace-header");
const compassTraceBody = document.getElementById("compass-trace-body");

async function loadCompassUrls() {
    try {
        const res = await fetch("/api/urls");
        if (!res.ok) throw new Error(`URLs API status ${res.status}`);
        const data = await res.json();
        
        compassCompaniesList.innerHTML = "";
        data.companies.forEach(url => {
            const el = document.createElement("div");
            el.className = "url-tag-item";
            el.innerText = url.replace("https://www.", "").replace("https://", "");
            el.addEventListener("click", () => {
                compassUrlInput.value = url;
                compassTextInput.value = "";
                compassUrlInput.focus();
            });
            compassCompaniesList.appendChild(el);
        });

        compassBenchmarksList.innerHTML = "";
        data.benchmarks.forEach(url => {
            const el = document.createElement("div");
            el.className = "url-tag-item";
            el.innerText = url.replace("https://www.", "").replace("https://", "");
            compassBenchmarksList.appendChild(el);
        });
    } catch (err) {
        console.error("Error loading sample GTM URLs:", err);
    }
}

compassAuditForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const urlVal = compassUrlInput.value.trim();
    const textVal = compassTextInput.value.trim();
    
    if (!urlVal && !textVal) {
        alert("Please provide either a website URL or paste pitch/landing copy.");
        return;
    }

    btnCompassAudit.disabled = true;
    btnCompassAudit.innerText = "Running Audit...";
    
    compassPlaceholder.classList.add("hidden");
    compassScorecardWorkspace.classList.add("hidden");
    compassLoader.classList.remove("hidden");
    
    compassLoaderTitle.innerText = "Reviewing website layout...";
    compassLoaderDesc.innerText = "Reading value propositions, headlines, and pages.";
    
    compassTraceBody.innerHTML = "";
    compassTraceBody.classList.remove("hidden");
    compassTraceHeader.classList.add("expanded");

    const onStep = (step) => {
        if (step.agent_name === "MessagingCritic") {
            compassLoaderTitle.innerText = "Reviewing Messaging copy...";
            compassLoaderDesc.innerText = "Checking value propositions, tone, and global market clarity.";
        } else if (step.agent_name === "PricingCritic") {
            compassLoaderTitle.innerText = "Analyzing Pricing & Packaging...";
            compassLoaderDesc.innerText = "Checking pricing tables, plans, and country-specific cost lookups.";
        } else if (step.agent_name === "TrustSignalsCritic") {
            compassLoaderTitle.innerText = "Inspecting Security & Trust...";
            compassLoaderDesc.innerText = "Checking compliance benchmarks, customer validation, and trust seals.";
        } else if (step.agent_name === "GTMOrchestrator") {
            if (step.action.includes("Consolidating")) {
                compassLoaderTitle.innerText = "Synthesizing Final Scorecard...";
                compassLoaderDesc.innerText = "Resolving critic feedback and compiling recommendations list.";
            } else {
                compassLoaderTitle.innerText = "Initializing Diligence Auditor...";
                compassLoaderDesc.innerText = "Ingesting website copy and metadata signals.";
            }
        }

        const stepDiv = document.createElement("div");
        stepDiv.className = "reasoning-step";
        stepDiv.innerHTML = `
            <div class="step-header">[Step ${step.step_num}] ${step.agent_name} -> ${step.action}</div>
            <div class="step-thought">> Thought: ${step.thought}</div>
            ${Object.keys(step.details).length > 0 ? `<div style="color: var(--color-slate-gray); margin-top:2px;">> Details: ${JSON.stringify(step.details)}</div>` : ""}
        `;
        compassTraceBody.appendChild(stepDiv);
        compassTraceBody.scrollTop = compassTraceBody.scrollHeight;
    };

    const onResult = (data) => {
        compassLoader.classList.add("hidden");
        compassScorecardWorkspace.classList.remove("hidden");

        compassScoreVal.innerText = Math.round(data.overall_score);
        compassCompanyTitle.innerText = "AUDIT SCORECARD";
        compassReadinessTier.innerText = data.readiness_tier;
        
        let tierClass = "needs-work";
        if (data.readiness_tier === "US-Ready" || data.readiness_tier === "Global-Ready") tierClass = "us-ready";
        if (data.readiness_tier === "Almost There") tierClass = "almost-there";
        compassReadinessTier.className = `readiness-tier-pill ${tierClass}`;

        compassSynthesisText.innerText = data.synthesis;

        compassCriticsGrid.innerHTML = "";
        Object.keys(data.critic_reports).forEach(key => {
            const report = data.critic_reports[key];
            const card = document.createElement("div");
            card.className = "critic-card";
            
            let displayTitle = "MESSAGING";
            if (key === "pricing") displayTitle = "PRICING";
            if (key === "trust_signals") displayTitle = "TRUST SIGNALS";
            
            card.innerHTML = `
                <div class="critic-header">
                    <h4>${displayTitle}</h4>
                    <span class="critic-score">${report.score.toFixed(1)}/10.0</span>
                </div>
                <h5 class="critic-section-title">Findings</h5>
                <ul class="critic-bullet-list">
                    ${report.findings.map(f => `<li>${f}</li>`).join('')}
                </ul>
                <div class="critic-recommendations-box">
                    <h5 class="critic-section-title" style="margin-bottom:4px; color:var(--color-signal-orange);">Fix Ticket</h5>
                    <ul class="critic-bullet-list" style="margin-bottom:0;">
                        ${report.recommendations.map(r => `<li>${r}</li>`).join('')}
                    </ul>
                </div>
            `;
            compassCriticsGrid.appendChild(card);
        });

        if (data.disagreements && data.disagreements.length > 0) {
            compassDisagreementsCard.classList.remove("hidden");
            compassDisagreementsList.innerHTML = "";
            data.disagreements.forEach(d => {
                const li = document.createElement("li");
                li.innerText = d;
                compassDisagreementsList.appendChild(li);
            });
        } else {
            compassDisagreementsCard.classList.add("hidden");
        }

        compassActionsContainer.innerHTML = "";
        data.prioritized_actions.forEach((item, index) => {
            const row = document.createElement("div");
            row.className = "action-checkbox-row";
            row.innerHTML = `
                <div class="action-chk-circle" id="chk-item-${index}"></div>
                <div class="action-text-col">
                    <div class="action-chk-title">${item.action}</div>
                </div>
                <div class="action-meta-col">
                    <span class="action-meta-pill high-impact">Impact: ${item.impact.toUpperCase()}</span>
                    <span class="action-meta-pill">Effort: ${item.effort.toUpperCase()}</span>
                </div>
            `;
            const chkBtn = row.querySelector(".action-chk-circle");
            chkBtn.addEventListener("click", () => {
                chkBtn.classList.toggle("checked");
            });
            compassActionsContainer.appendChild(row);
        });
        btnCompassAudit.disabled = false;
        btnCompassAudit.innerText = "RUN AUDIT PIPELINE";
    };

    const onError = (err) => {
        compassLoader.classList.add("hidden");
        alert("Audit failed: " + err.message);
        console.error(err);
        btnCompassAudit.disabled = false;
        btnCompassAudit.innerText = "RUN AUDIT PIPELINE";
    };

    const countryVal = compassCountryInput.value.trim();
    let payload = { 
        url: urlVal || null, 
        fallback_text: textVal || null 
    };
    if (countryVal) {
        payload.target_country = countryVal;
    }

    await handleStreamingRequest(
        "/api/audit/stream",
        payload,
        onStep,
        onResult,
        onError
    );
});

compassTraceHeader.addEventListener("click", () => {
    compassTraceBody.classList.toggle("hidden");
    compassTraceHeader.classList.toggle("expanded");
});

// Initialization
loadCompassUrls();
