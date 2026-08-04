import re

with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Inject CSS
css_code = """
/* Dataset Relations Modal */
.modal-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(4px);
    z-index: 1000;
    align-items: center;
    justify-content: center;
}
.modal-overlay.active { display: flex; }
.relation-modal {
    background: #111;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    width: 600px;
    padding: 24px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.5);
    display: flex;
    flex-direction: column;
    gap: 16px;
}
.relation-header {
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    padding-bottom: 12px;
}
.relation-header h3 { margin: 0; font-size: 16px; color: #fff; }
.close-modal { background: none; border: none; color: #a1a1aa; cursor: pointer; font-size: 20px; }
.close-modal:hover { color: #fff; }
.relation-body { display: flex; flex-direction: column; gap: 16px; }
.dataset-selects { display: flex; gap: 12px; align-items: center; }
.dataset-selects select {
    flex: 1;
    background: #1a1a1a;
    border: 1px solid rgba(255,255,255,0.1);
    color: #e4e4e7;
    padding: 8px 12px;
    border-radius: 6px;
    outline: none;
}
.analyze-btn {
    background: var(--accent-orange);
    color: #fff;
    border: none;
    padding: 10px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    display: flex; justify-content: center; align-items: center; gap: 8px;
}
.analyze-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.relation-editor {
    background: #1a1a1a;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    padding: 12px;
    color: #e4e4e7;
    min-height: 80px;
    resize: vertical;
    font-family: inherit;
    font-size: 13px;
    width: 100%;
    box-sizing: border-box;
}
.save-relation-btn {
    background: #22c55e;
    color: #fff;
    border: none;
    padding: 10px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    transition: background 0.3s;
}
.saved-relations-list {
    margin-top: 16px;
    border-top: 1px solid rgba(255,255,255,0.05);
    padding-top: 16px;
}
.relation-item {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.05);
    padding: 10px;
    border-radius: 6px;
    margin-bottom: 8px;
    font-size: 12px;
    color: #a1a1aa;
    line-height: 1.4;
}
.relation-item strong { color: #fff; }
</style>"""
content = content.replace('</style>', css_code)

# 2. Inject Sidebar Button
sidebar_btn = """</button>
        <button class="prompt-btn" style="background: rgba(34, 197, 94, 0.1); border-color: rgba(34, 197, 94, 0.35); color: #4ade80; margin-top: 8px; display: flex; align-items: center; gap: 8px;" onclick="openRelationModal()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5c-1.1 0-2 .9-2 2v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg> Manage Dataset Relations
        </button>"""
content = content.replace('</button>\n    </aside>', sidebar_btn + '\n    </aside>')

# 3. Inject Modal HTML
modal_html = """
    <!-- Dataset Relations Modal -->
    <div id="relationModal" class="modal-overlay">
        <div class="relation-modal">
            <div class="relation-header">
                <h3>Manage Dataset Relations</h3>
                <button class="close-modal" onclick="closeRelationModal()">&times;</button>
            </div>
            <div class="relation-body">
                <div class="dataset-selects">
                    <select id="datasetA">
                        <option value="SharePoint HR Manuals">SharePoint HR Manuals</option>
                        <option value="SAP Financial Ledger">SAP Financial Ledger</option>
                        <option value="Snowflake User DB">Snowflake User DB</option>
                    </select>
                    <span style="color: #a1a1aa;">↔️</span>
                    <select id="datasetB">
                        <option value="Snowflake User DB">Snowflake User DB</option>
                        <option value="SAP Financial Ledger">SAP Financial Ledger</option>
                        <option value="SharePoint HR Manuals">SharePoint HR Manuals</option>
                    </select>
                </div>
                <button class="analyze-btn" id="analyzeBtn" onclick="analyzeRelation()">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg> Analyze Relation (AI)
                </button>
                
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    <label style="font-size: 11px; color: #a1a1aa;">AI Suggested Relationship (Edit to override)</label>
                    <textarea id="relationEditor" class="relation-editor" placeholder="Select datasets and click analyze..."></textarea>
                </div>
                
                <button class="save-relation-btn" onclick="saveRelation()">Save to Knowledge Graph</button>
            </div>
            <div class="saved-relations-list">
                <h4 style="margin: 0 0 8px 0; font-size: 12px; color: #fff;">Saved Relations</h4>
                <div id="relationsList">
                    <div class="relation-item"><strong>SAP Financial Ledger</strong> ↔️ <strong>Snowflake User DB</strong><br/>Joined on UUID. SAP handles transactional history while Snowflake handles user metadata.</div>
                </div>
            </div>
        </div>
    </div>
</body>"""
content = content.replace('</body>', modal_html)

# 4. Inject JS logic
js_code = """
    // Dataset Relations Logic
    function openRelationModal() {
        document.getElementById('relationModal').classList.add('active');
    }
    function closeRelationModal() {
        document.getElementById('relationModal').classList.remove('active');
        document.getElementById('relationEditor').value = '';
    }
    function analyzeRelation() {
        const btn = document.getElementById('analyzeBtn');
        const dsA = document.getElementById('datasetA').value;
        const dsB = document.getElementById('datasetB').value;
        const editor = document.getElementById('relationEditor');
        
        btn.disabled = true;
        btn.innerHTML = 'Analyzing...';
        editor.value = 'AI is analyzing schemas and metadata...';
        
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg> Analyze Relation (AI)';
            
            // Mock AI suggestion
            editor.value = `${dsA} acts as the primary source of truth, linked to ${dsB} via common employee/user ID keys. Unstructured data from ${dsA} is frequently queried alongside structured metrics in ${dsB}.`;
        }, 1200);
    }
    function saveRelation() {
        const dsA = document.getElementById('datasetA').value;
        const dsB = document.getElementById('datasetB').value;
        const editor = document.getElementById('relationEditor').value;
        
        if(!editor || editor.includes('AI is analyzing')) return;
        
        const list = document.getElementById('relationsList');
        const item = document.createElement('div');
        item.className = 'relation-item';
        item.innerHTML = `<strong>${dsA}</strong> ↔️ <strong>${dsB}</strong><br/>${editor}`;
        
        list.prepend(item);
        
        // Show a quick visual success
        const saveBtn = document.querySelector('.save-relation-btn');
        const oldText = saveBtn.innerText;
        saveBtn.innerText = 'Saved Successfully!';
        saveBtn.style.background = '#10b981';
        setTimeout(() => {
            saveBtn.innerText = oldText;
            saveBtn.style.background = '#22c55e';
            closeRelationModal();
        }, 1000);
    }
</script>"""
content = content.replace('</script>', js_code)

with open('app/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Dataset relations feature injected.")
