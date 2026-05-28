let currentDocId = '';
let currentDocType = '';
let currentDraftText = '';
let lastBaselineDraft = '';
let currentTaskPrompt = '';
let currentChunks = [];

// Render source document chunks in the left panel
function renderSourceChunks() {
    const container = document.getElementById('source-chunks-container');
    const badge = document.getElementById('source-status-badge');

    if (!currentChunks || currentChunks.length === 0) {
        container.innerHTML = `
            <div class="placeholder">Upload a document to view source evidence chunks here.</div>
        `;
        badge.innerText = "No document loaded";
        return;
    }

    badge.innerText = `${currentChunks.length} Chunks Loaded`;

    container.innerHTML = `
        <div class="source-chunks-list">
            ${currentChunks.map((chunk, idx) => `
                <div class="source-chunk-card" id="chunk-${idx}">
                    <div class="source-chunk-card-header">
                        <span>Chunk ${idx + 1}</span>
                    </div>
                    <div class="source-chunk-card-body">
                        ${escapeHtml(chunk)}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// Helper to escape HTML characters in chunks
function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Toggle between View and Edit modes in the Draft panel
function switchDraftMode(mode) {
    const viewContainer = document.getElementById('draft-view-content');
    const operatorEdit = document.getElementById('operator-edit');
    const toggleViewBtn = document.getElementById('toggle-view');
    const toggleEditBtn = document.getElementById('toggle-edit');

    if (mode === 'view') {
        // Sync edits from textarea back to the viewer
        currentDraftText = operatorEdit.value;
        renderDraftWithHover(currentDraftText, 'draft-view-content');

        viewContainer.style.display = 'block';
        operatorEdit.style.display = 'none';

        toggleViewBtn.classList.add('active');
        toggleEditBtn.classList.remove('active');
    } else if (mode === 'edit') {
        // Prepare textarea with current draft text
        operatorEdit.value = currentDraftText;

        viewContainer.style.display = 'none';
        operatorEdit.style.display = 'block';

        toggleViewBtn.classList.remove('active');
        toggleEditBtn.classList.add('active');
    }
}

// Transform raw draft text into HTML with hoverable spans for source tags
function renderDraftWithHover(draftText, targetElementId) {
    const targetElement = document.getElementById(targetElementId);
    if (!draftText) {
        targetElement.innerHTML = `
            <div class="placeholder">Nothing to show here</div>
        `;
        return;
    }

    // Parse markdown to HTML using marked.js
    const parsedHtml = marked.parse(draftText);

    // Match [Source: doc_id_chunk_N], [source: doc_...], or just [doc_id_chunk_N]
    const htmlText = parsedHtml.replace(/\[(?:(?:Source|source):\s*)?(doc_[^\]]+)\]/gi, (match, sourceId) => {
        const cleanId = sourceId.trim();
        return `<span class="source-link" data-source-id="${cleanId}">${match}</span>`;
    });

    targetElement.innerHTML = htmlText;
}

// Handle mouseover hover event: highlight and scroll corresponding source chunk
function handleHoverEvent(event) {
    const target = event.target.closest('.source-link');
    if (target) {
        const sourceId = target.getAttribute('data-source-id');

        // Extract the chunk index from the ID (e.g., doc_pdf_001_chunk_0 -> 0)
        const match = sourceId.match(/_chunk_(\d+)/);

        if (match && currentChunks && currentChunks.length > 0) {
            const index = parseInt(match[1], 10);
            if (index >= 0 && index < currentChunks.length) {
                // Clear any previous highlights
                document.querySelectorAll('.source-chunk-card.highlighted').forEach(el => {
                    el.classList.remove('highlighted');
                });

                // Highlight the target chunk card
                const chunkEl = document.getElementById(`chunk-${index}`);
                if (chunkEl) {
                    chunkEl.classList.add('highlighted');

                    // Smoothly scroll the highlighted chunk card to the center of the scrollable container
                    chunkEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        }
    }
}

// Remove highlights when mouse leaves the source link
function handleMouseOut(event) {
    const target = event.target.closest('.source-link');
    if (target) {
        document.querySelectorAll('.source-chunk-card.highlighted').forEach(el => {
            el.classList.remove('highlighted');
        });
    }
}

// Add event listeners for hover sync
document.addEventListener('mouseover', handleHoverEvent);
document.addEventListener('mouseout', handleMouseOut);

// Upload and process target document
async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files || !fileInput.files.length) {
        alert("Please select a file to upload.");
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    const statusEl = document.getElementById('draft-status');
    statusEl.innerText = "Standby! LLM is Underprocess";

    // Clear previous state
    currentChunks = [];
    renderSourceChunks();
    currentDraftText = '';
    lastBaselineDraft = '';
    renderDraftWithHover('', 'draft-view-content');

    try {
        document.querySelector('.draft-content').classList.add('loading');
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            if (errorData.error) {
                throw new Error(errorData.error);
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        currentDocId = data.document_id;
        currentDocType = data.document_type;
        currentChunks = data.chunks || [];

        // Render chunks in left panel
        renderSourceChunks();

        // Enable query button
        const queryBtn = document.getElementById('query-btn');
        if (queryBtn) {
            queryBtn.removeAttribute('disabled');
        }

        // Run the query with current prompt automatically
        await queryPrompt();
    } catch (error) {
        statusEl.innerText = "Error: " + error.message;
        document.querySelector('.draft-content').classList.remove('loading');
        alert("Upload Failed: " + error.message);
    }
}

// Query the retrieval layer and generate the draft
async function queryPrompt() {
    if (!currentDocId) {
        alert("Please upload and process a document first.");
        return;
    }

    const taskPromptInput = document.getElementById('task-prompt-input');
    const taskPromptValue = taskPromptInput.value.trim();
    if (!taskPromptValue) {
        alert("Please enter a task prompt.");
        return;
    }

    currentTaskPrompt = taskPromptValue;
    const statusEl = document.getElementById('draft-status');
    statusEl.innerText = "Standby! LLM is Underprocess";

    try {
        document.querySelector('.draft-content').classList.add('loading');
        const queryResponse = await fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                document_id: currentDocId,
                document_type: currentDocType,
                task_prompt: currentTaskPrompt
            })
        });

        if (!queryResponse.ok) {
            throw new Error(`HTTP error querying retrieval layer! status: ${queryResponse.status}`);
        }

        const queryData = await queryResponse.json();
        currentDraftText = queryData.draft;
        lastBaselineDraft = queryData.draft;

        // Render current draft in both view and edit container
        renderDraftWithHover(currentDraftText, 'draft-view-content');
        document.getElementById('operator-edit').value = currentDraftText;

        // Enable submit feedback button
        document.getElementById('submit-feedback-btn').removeAttribute('disabled');

        // Switch back to view mode by default
        switchDraftMode('view');

        statusEl.innerText = "";
        document.querySelector('.draft-content').classList.remove('loading');
    } catch (error) {
        statusEl.innerText = "Error: " + error.message;
        document.querySelector('.draft-content').classList.remove('loading');
    }
}

// Submit operator edits as preference feedback to optimize the draft
async function submitFeedback() {
    if (!currentDocId) {
        alert("Please upload and process a document first.");
        return;
    }

    // Capture edits from textarea
    const operatorEdit = document.getElementById('operator-edit').value;

    const taskPromptValue = document.getElementById('task-prompt-input').value.trim();
    currentTaskPrompt = taskPromptValue;

    const statusEl = document.getElementById('draft-status');
    statusEl.innerText = "Standby! LLM is Underprocess";

    try {
        document.querySelector('.draft-content').classList.add('loading');
        const response = await fetch('/improve', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                document_id: currentDocId,
                document_type: currentDocType,
                initial_draft: lastBaselineDraft,
                operator_edit: operatorEdit,
                task_prompt: currentTaskPrompt
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        currentDraftText = data.optimized_draft;
        lastBaselineDraft = data.optimized_draft;

        if (data.learned_rules && data.learned_rules.length > 0) {
            alert("AI Learned the following rules:\n\n" + JSON.stringify(data.learned_rules, null, 2));
        }

        // Update both view and edit containers
        renderDraftWithHover(currentDraftText, 'draft-view-content');
        document.getElementById('operator-edit').value = currentDraftText;

        // Switch back to view mode
        switchDraftMode('view');

        statusEl.innerText = "";
        document.querySelector('.draft-content').classList.remove('loading');
    } catch (error) {
        statusEl.innerText = "Error: " + error.message;
        document.querySelector('.draft-content').classList.remove('loading');
    }
}

// Load default prompt on boot
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('/default-prompt');
        if (response.ok) {
            const data = await response.json();
            document.getElementById('task-prompt-input').value = data.default_prompt;
        }
    } catch (error) {
        console.error("Could not load default prompt:", error);
    }
});

// Prompts Modal Logic
async function showPrompts() {
    const modal = document.getElementById('prompts-modal');
    const container = document.getElementById('prompts-container');
    container.innerHTML = '<p>Loading...</p>';
    modal.style.display = 'block';

    try {
        const response = await fetch('/prompts');
        if (!response.ok) throw new Error("Failed to fetch prompts");
        const data = await response.json();

        container.innerHTML = `
            <div class="prompt-block">
                <h3>Parser Prompt</h3>
                <pre>${escapeHtml(data.parser_prompt)}</pre>
            </div>
            <div class="prompt-block">
                <h3>Generator System Prompt</h3>
                <pre>${escapeHtml(data.generator_system_prompt)}</pre>
            </div>
            <div class="prompt-block">
                <h3>Generator User Prompt</h3>
                <pre>${escapeHtml(data.generator_user_prompt)}</pre>
            </div>
            <div class="prompt-block">
                <h3>Learner Prompt</h3>
                <pre>${escapeHtml(data.learner_prompt)}</pre>
            </div>
        `;
    } catch (error) {
        container.innerHTML = `<p>Error loading prompts: ${error.message}</p>`;
    }
}

function closePrompts() {
    document.getElementById('prompts-modal').style.display = 'none';
}

// Close modal when clicking outside of it
window.onclick = function (event) {
    const modal = document.getElementById('prompts-modal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}
