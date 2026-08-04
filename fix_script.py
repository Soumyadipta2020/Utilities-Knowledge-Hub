with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# We will cut off everything from <!-- Dataset Relations Modal --> to the end of the file
# Since we know my regex corrupted the file, we can just find the modal start.
modal_start_idx = content.find('<!-- Dataset Relations Modal -->')

new_modal_and_js_with_script = """<!-- Dataset Relations Modal -->
    <div id="relationModal" class="modal-overlay">
        <div class="relation-modal">
            <div class="relation-header">
                <h3>Manage Dataset Relations</h3>
                <button class="close-modal" onclick="closeRelationModal()">&times;</button>
            </div>
            <div class="relation-body">
                <div class="dataset-selects">
                    <select id="datasetA">
                        <option value="">Loading datasets...</option>
                    </select>
                    <span style="color: #a1a1aa;">↔️</span>
                    <select id="datasetB">
                        <option value="">Loading datasets...</option>
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

<script>
    // Dataset Relations Logic
    function openRelationModal() {
        document.getElementById('relationModal').classList.add('active');
        fetchDatasets();
    }
    
    function closeRelationModal() {
        document.getElementById('relationModal').classList.remove('active');
        document.getElementById('relationEditor').value = '';
    }
    
    function fetchDatasets() {
        fetch('/api/graph/data')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const datasets = data.nodes.filter(n => n.category === 'Dataset').map(n => n.id);
                    // Add fallbacks just in case
                    if(datasets.length === 0) {
                        datasets.push('SharePoint HR Manuals', 'SAP Financial Ledger', 'Snowflake User DB', 'Information_Harnessing_Source.xlsx');
                    }
                    
                    const selectA = document.getElementById('datasetA');
                    const selectB = document.getElementById('datasetB');
                    
                    let optionsHtml = '';
                    datasets.forEach(ds => {
                        optionsHtml += `<option value="${ds}">${ds}</option>`;
                    });
                    
                    selectA.innerHTML = optionsHtml;
                    selectB.innerHTML = optionsHtml;
                }
            })
            .catch(err => console.error("Error fetching datasets", err));
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
        
        // Save to backend graph
        fetch('/api/graph/relation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                source: dsA,
                target: dsB,
                details: editor
            })
        })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
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
            } else {
                alert("Failed to save relation: " + data.error);
            }
        })
        .catch(err => {
            console.error("Error saving relation", err);
            alert("Error saving relation");
        });
    }
</script>
</body>
</html>
"""

if modal_start_idx != -1:
    new_content = content[:modal_start_idx] + new_modal_and_js_with_script
    
    with open('app/templates/index.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully updated index.html")
else:
    print("Could not find <!-- Dataset Relations Modal --> in index.html")
