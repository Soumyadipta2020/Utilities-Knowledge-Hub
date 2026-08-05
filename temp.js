
        const BOT_ICON_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4"/><circle cx="12" cy="2" r="1"/><rect x="4" y="8" width="16" height="12" rx="3"/><circle cx="9" cy="13" r="1" fill="currentColor"/><circle cx="15" cy="13" r="1" fill="currentColor"/><path d="M10 17h4"/></svg>`;

        const USER_ICON_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;

        function switchMainTab(el, tabId) {
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            
            document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
            if (tabId) {
                const target = document.getElementById(tabId);
                if (target) target.classList.add('active');
            }
        }

        function parseMarkdown(text) {
            if (!text) return '';
            let cleanText = text.trim().replace(/\n{3,}/g, '\n\n');
            try {
                if (typeof marked !== 'undefined' && marked.parse) {
                    return marked.parse(cleanText);
                }
            } catch (e) {
                console.warn("Marked.js parse warning:", e);
            }
            // Fallback lightweight Markdown renderer
            let html = cleanText
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/__(.*?)__/g, '<strong>$1</strong>')
                .replace(/`(.*?)`/g, '<code style="background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px;">$1</code>');

            const lines = html.split('\n');
            let inList = false;
            let formatted = [];

            for (let line of lines) {
                let trimmed = line.trim();
                if (trimmed.startsWith('• ') || trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
                    let content = trimmed.substring(2).trim();
                    if (!inList) {
                        formatted.push('<ul style="margin: 6px 0; padding-left: 20px;">');
                        inList = true;
                    }
                    formatted.push(`<li style="margin-bottom: 2px;">${content}</li>`);
                } else if (trimmed === '') {
                    if (inList) {
                        formatted.push('</ul>');
                        inList = false;
                    }
                } else {
                    if (inList) {
                        formatted.push('</ul>');
                        inList = false;
                    }
                    formatted.push(line);
                }
            }
            if (inList) formatted.push('</ul>');
            return formatted.join('<br>').replace(/(<br>\s*){2,}/g, '<br>');
        }

        function appendMessage(sender, text, showTicketCTA = false, responseGraph = null) {
            const container = document.getElementById('chatMessages');
            const row = document.createElement('div');
            row.className = `message-row ${sender}`;

            const avatar = document.createElement('div');
            avatar.className = `avatar ${sender}`;
            avatar.innerHTML = sender === 'user' ? USER_ICON_SVG : BOT_ICON_SVG;

            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';
            bubble.innerHTML = parseMarkdown(text);

            if (showTicketCTA && sender === 'agent') {
                const ticketBox = document.createElement('div');
                ticketBox.className = 'ticket-cta-box';
                ticketBox.innerHTML = `
                    <span style="font-size: 12px; color: #f8fafc;">Dataset access required for your project. Raise IT request?</span>
                    <button class="ticket-btn" onclick="raiseTicketDirectly()">Submit Access Request</button>
                `;
                bubble.appendChild(ticketBox);
            }

            if (sender === 'agent' && responseGraph && responseGraph.nodes && responseGraph.nodes.length > 0) {
                const graphBox = document.createElement('div');
                graphBox.style.cssText = 'margin-top: 10px; padding: 8px 12px; background: rgba(22, 22, 22, 0.8); border: 1px solid rgba(217, 102, 43, 0.28); border-radius: 8px; display: flex; align-items: center; justify-content: space-between; gap: 12px;';
                
                window.lastResponseGraphs = window.lastResponseGraphs || {};
                const graphId = 'graph_' + Math.random().toString(36).substr(2, 9);
                window.lastResponseGraphs[graphId] = responseGraph;

                graphBox.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 8px; overflow: hidden;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#D9662B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
                        <span style="font-size: 11px; font-weight: 600; color: #D9662B; white-space: nowrap;">Grounding Lineage</span>
                        <span style="font-size: 10px; background: rgba(217, 102, 43, 0.14); color: #e2a37e; padding: 2px 6px; border-radius: 4px; font-weight: 600; white-space: nowrap;">${responseGraph.nodes.length} nodes • ${responseGraph.edges.length} edges</span>
                    </div>
                    <button class="ticket-btn" style="background: rgba(217, 102, 43, 0.18); border: 1px solid rgba(217, 102, 43, 0.35); color: #e2a37e; padding: 4px 10px; font-size: 11px; white-space: nowrap; flex-shrink: 0; display: inline-flex; align-items: center; gap: 4px;" onclick="showReplyGraphModal('${graphId}')">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Inspect Lineage
                    </button>
                `;
                bubble.appendChild(graphBox);
            }

            row.appendChild(avatar);
            row.appendChild(bubble);
            container.appendChild(row);
            container.scrollTop = container.scrollHeight;
        }

        async function handleSend(event) {
            if (event) event.preventDefault();
            const inputEl = document.getElementById('userInput');
            const text = inputEl.value.trim();
            if (!text) return;

            const email = document.getElementById('userEmail').value || 'project.lead@abc.com';

            appendMessage('user', text);
            inputEl.value = '';
            toggleScenarioCards();

            const sendBtn = document.getElementById('sendBtn');
            sendBtn.disabled = true;
            sendBtn.innerText = 'Thinking...';

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: text,
                        user_email: email
                    })
                });

                const data = await response.json();
                const showCTA = data.access_required || (data.response && (data.response.includes('Dataset Access Required') || data.response.includes('Access Denied')));
                appendMessage('agent', data.response, showCTA, data.graph);

            } catch (err) {
                appendMessage('agent', `⚠️ Network Error: Unable to communicate with server backend. (${err.message})`);
            } finally {
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<span>Send Query</span>';
            }
        }

        function raiseTicketDirectly() {
            sendQuickPrompt("Yes please raise an IT access request ticket.");
        }

        function sendQuickPrompt(promptText) {
            document.getElementById('userInput').value = promptText;
            handleSend();
        }

        const PIPELINE_STAGES = [
            { id: 1, name: "File Upload", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>` },
            { id: 2, name: "Ingestion & Extraction", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>` },
            { id: 3, name: "Cleaning & Normalization", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4"/><path d="M12 18v4"/><path d="M4.93 4.93l2.83 2.83"/><path d="M16.24 16.24l2.83 2.83"/><path d="M2 12h4"/><path d="M18 12h4"/></svg>` },
            { id: 4, name: "Chunking & Segmentation", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/></svg>` },
            { id: 5, name: "Metadata Intelligence", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>` },
            { id: 6, name: "Entity & Relationship", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>` },
            { id: 7, name: "Semantic Learning", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 15c6.667-6 13.333 0 20-6"/><path d="M2 9c6.667 6 13.333 0 20 6"/></svg>` },
            { id: 8, name: "EDA Intelligence", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>` },
            { id: 9, name: "ML Validation & Accuracy", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>` },
            { id: 10, name: "Ontology & Governance", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M3 10h18"/><path d="M5 6l7-3 7 3"/><path d="M4 10v11"/><path d="M20 10v11"/><path d="M8 10v11"/><path d="M12 10v11"/><path d="M16 10v11"/></svg>` },
            { id: 11, name: "Canonicalization", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>` },
            { id: 12, name: "Knowledge Graph", icon: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>` }
        ];

        function renderStepper(completedCount = PIPELINE_STAGES.length, stageResults = {}) {
            const container = document.getElementById('stepperContainer');
            if (!container) return;
            let html = '';
            PIPELINE_STAGES.forEach((stage, idx) => {
                const isDone = idx < completedCount;
                const sRes = stageResults[stage.id];
                const durationText = sRes ? `${sRes.duration_ms}ms` : '';
                const statusText = isDone ? `✓ done ${durationText ? '('+durationText+')' : ''}` : 'pending';
                const logText = sRes ? sRes.log : '';

                html += `
                    <div class="sidebar-stage-row ${isDone ? 'active' : ''}" style="flex-direction: column; align-items: stretch; gap: 4px; padding: 6px 8px; margin-bottom: 2px;">
                        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div class="stage-badge ${isDone ? 'done' : ''}" style="display: flex; align-items: center; justify-content: center;">
                                    ${stage.icon}
                                </div>
                                <span class="stage-title" style="font-size: 11px; font-weight: 600;">${stage.name}</span>
                            </div>
                            <span class="stage-status" style="font-size: 9.5px; color: ${isDone ? '#4ade80' : 'var(--text-muted)'};">${statusText}</span>
                        </div>
                        ${isDone && logText ? `<div style="font-size: 9px; color: #94a3b8; line-height: 1.3; padding-left: 20px; font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${logText}">${logText}</div>` : ''}
                    </div>
                `;
            });
            container.innerHTML = html;
        }

        function updateArchitectureVisualizer(stageId) {
            for (let b = 1; b <= 5; b++) {
                const el = document.getElementById(`dhs-node-${b}`);
                if (el) {
                    el.style.transform = el.style.transform.replace(' scale(1.15)', '');
                    el.style.filter = '';
                    el.style.textShadow = '';
                }
            }
            let activeNode = 0;
            if (stageId === 1) activeNode = 1;
            else if (stageId >= 2 && stageId <= 6) activeNode = 2;
            else if (stageId >= 7 && stageId <= 11) activeNode = 3;
            else if (stageId === 12) activeNode = 4;
            else if (stageId === 'done') activeNode = 5;

            for (let b = 1; b <= 5; b++) {
                const node = document.getElementById(`dhs-node-${b}`);
                if (!node) continue;
                if (b < activeNode) {
                    node.style.filter = 'drop-shadow(0 0 4px rgba(74, 222, 128, 0.6))';
                    node.style.textShadow = '0 0 8px rgba(74, 222, 128, 0.8)';
                } else if (b === activeNode) {
                    if (!node.style.transform.includes('scale')) {
                        node.style.transform += ' scale(1.15)';
                    }
                    node.style.filter = 'drop-shadow(0 0 6px rgba(56, 189, 248, 0.8))';
                    node.style.textShadow = '0 0 8px rgba(56, 189, 248, 1)';
                }
            }
        }

        async function triggerPipeline() {
            const fill = document.getElementById('progressFill');
            const percent = document.getElementById('progressPercent');
            const toast = document.getElementById('toastBox');

            const stageResults = {};
            renderStepper(0, stageResults);
            fill.style.width = '0%';
            percent.innerText = '0%';
            
            const sapStatus = document.getElementById('sap-sync-status');
            if(sapStatus) {
                sapStatus.innerText = 'Syncing (0%)';
                sapStatus.style.background = 'rgba(250, 204, 21, 0.15)';
                sapStatus.style.color = '#facc15';
            }

            for (let i = 0; i < PIPELINE_STAGES.length; i++) {
                const stageId = PIPELINE_STAGES[i].id;
                updateArchitectureVisualizer(stageId);
                try {
                    const resp = await fetch(`/api/pipeline/run-stage/${stageId}`, { method: 'POST' });
                    const data = await resp.json();
                    if (data.success && data.stage) {
                        stageResults[stageId] = data.stage;
                        if (data.harnessing_metrics) {
                            window.lastHarnessingMetrics = data.harnessing_metrics;
                        }
                    }
                } catch (e) {
                    console.error(`Pipeline Stage ${stageId} error:`, e);
                }

                const pct = Math.round(((i + 1) / PIPELINE_STAGES.length) * 100);
                fill.style.width = pct + '%';
                percent.innerText = pct + '%';
                renderStepper(i + 1, stageResults);
                
                if (sapStatus) {
                    sapStatus.innerText = `Syncing (${pct}%)`;
                }
            }

            updateArchitectureVisualizer('done');
            await updateDashboardMetrics();

            if (toast) {
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 4000);
            }
        }

        async function updateDashboardMetrics() {
            const sapStatus = document.getElementById('sap-sync-status');
            if (sapStatus) {
                sapStatus.innerText = 'Synced Live';
                sapStatus.style.background = 'rgba(34, 197, 94, 0.15)';
                sapStatus.style.color = '#22c55e';
            }

            try {
                let metrics = window.lastHarnessingMetrics;
                if (!metrics) {
                    const resp = await fetch('/api/harnessing/metrics');
                    const res = await resp.json();
                    if (res.success) metrics = res.metrics;
                }
                if (!metrics) return;

                // Knowledge Harnessing elements
                const graphNodes = document.getElementById('metric-nodes');
                if (graphNodes) graphNodes.innerText = metrics.knowledge_harnessing.entities_count.toLocaleString();
                
                const edges = document.getElementById('metric-edges');
                if (edges) edges.innerText = metrics.knowledge_harnessing.edges_count.toLocaleString();

                const docsIngested = document.getElementById('metric-docs');
                if (docsIngested) docsIngested.innerText = metrics.information_harnessing.total_records.toLocaleString();

                const autoRes = document.getElementById('metric-auto-res');
                if (autoRes) autoRes.innerText = metrics.outcome_harnessing.access_requests_processed.toLocaleString();

                const f1Score = document.getElementById('metric-f1');
                if (f1Score) f1Score.innerText = (metrics.benchmarking.precision_pct / 100).toFixed(2);

            } catch (e) {
                console.error("Error updating harnessing metrics:", e);
            }
        }

        /* Knowledge Graph Visualizer Logic */
        let graphData = { nodes: [], edges: [] };
        let isGraphModalOpen = false;
        let selectedNode = null;

        async function showReplyGraphModal(graphId) {
            const subGraph = window.lastResponseGraphs ? window.lastResponseGraphs[graphId] : null;
            if (!subGraph) return;

            const modal = document.getElementById('graphModal');
            if (!modal) return;

            modal.style.display = 'flex';
            isGraphModalOpen = true;

            graphData = subGraph;
            document.getElementById('graphNodeCount').innerText = `${subGraph.nodes.length} Grounding Nodes`;
            document.getElementById('graphEdgeCount').innerText = `${subGraph.edges.length} Traversed Edges`;

            requestAnimationFrame(() => requestAnimationFrame(() => initCanvasGraph()));

            const nameEl = document.getElementById('inspectorNodeName');
            const descEl = document.getElementById('inspectorNodeDesc');
            const nodeNames = subGraph.nodes.map(n => n.id).join(', ');
            nameEl.innerText = `Reply Generation Lineage (${subGraph.nodes.length} entities traversed)`;
            descEl.innerText = `Query: "${subGraph.query || 'User Query'}"\n\nTraversed Entities: ${nodeNames}\nClick any node to inspect relationship details.`;
        }

        async function toggleGraphModal() {
            const modal = document.getElementById('graphModal');
            if (!modal) return;
            if (modal.style.display === 'none' || !modal.style.display) {
                modal.style.display = 'flex';
                isGraphModalOpen = true;
                await loadGraphData();
                // Defer so the browser lays out the flex container first
                requestAnimationFrame(() => requestAnimationFrame(() => initCanvasGraph()));
            } else {
                modal.style.display = 'none';
                isGraphModalOpen = false;
            }
        }

        async function loadGraphData() {
            try {
                const res = await fetch('/api/graph/data');
                const data = await res.json();
                if (data.success) {
                    graphData = data;
                    document.getElementById('graphNodeCount').innerText = `${data.total_nodes} Nodes`;
                    document.getElementById('graphEdgeCount').innerText = `${data.total_edges} Edges`;
                }
            } catch (e) {
                console.error("Failed to fetch graph data:", e);
            }
        }

        let activeCategoryFilter = 'All';

        function filterGraphCategory(cat) {
            activeCategoryFilter = cat;
            document.querySelectorAll('.filter-pill').forEach(btn => {
                const btnCat = btn.getAttribute('data-cat');
                btn.classList.toggle('active', btnCat === cat);
            });
            initCanvasGraph();
        }

        function getShortLabel(label) {
            if (!label) return '';
            let str = String(label).trim();
            if (str.includes('(')) str = str.split('(')[0].trim();
            if (str.length > 45) return str.substring(0, 43) + '..';
            return str;
        }

        function initCanvasGraph() {
            const canvas = document.getElementById('graphCanvas');
            if (!canvas) return;
            const wrapper = canvas.parentElement;
            const ctx = canvas.getContext('2d');
            
            let nodesToRender = [];
            if (activeCategoryFilter === 'Dataset') {
                nodesToRender = (graphData.nodes || []).filter(n => n.category === 'Dataset');
                nodesToRender.forEach(n => n._isPrimary = true);
            } else if (activeCategoryFilter === 'All') {
                nodesToRender = graphData.nodes || [];
                nodesToRender.forEach(n => n._isPrimary = true);
            } else {
                const primaryNodes = (graphData.nodes || []).filter(n => n.category === activeCategoryFilter);
                const primaryNodeIds = new Set(primaryNodes.map(n => n.id));
                
                const connectedNodeIds = new Set(primaryNodeIds);
                (graphData.edges || []).forEach(e => {
                    const src = typeof e.source === 'object' ? e.source.id : e.source;
                    const tgt = typeof e.target === 'object' ? e.target.id : e.target;
                    if (primaryNodeIds.has(src)) connectedNodeIds.add(tgt);
                    if (primaryNodeIds.has(tgt)) connectedNodeIds.add(src);
                });
                
                nodesToRender = (graphData.nodes || []).filter(n => connectedNodeIds.has(n.id));
                nodesToRender.forEach(n => {
                    n._isPrimary = primaryNodeIds.has(n.id);
                });
            }

            let computedHeight = wrapper.clientHeight || 460;
            const maxNodesInOneTier = Math.max(
                ...[0, 1, 2, 3].map(lvl => nodesToRender.filter(n => {
                    let l = typeof n.tree_level === 'number' ? n.tree_level : 0;
                    if (l > 3) l = 3;
                    return l === lvl;
                }).length)
            );
            // 40px vertical space per node + padding
            computedHeight = Math.max(computedHeight, maxNodesInOneTier * 45 + 100);

            const width = canvas.width = wrapper.clientWidth || 900;
            const height = canvas.height = computedHeight;
            canvas.style.height = computedHeight + 'px';

            const categoryConfig = {
                'Domain Cluster':  { color: '#22c55e', bg: 'rgba(34, 197, 94, 0.08)', icon: '\uf0e8', label: 'Domains' },
                'Dataset':         { color: '#D9662B', bg: 'rgba(217, 102, 43, 0.08)', icon: '\uf1c0', label: 'Datasets' },
                'Key Info Link':   { color: '#f43f5e', bg: 'rgba(244, 63, 94, 0.08)', icon: '\uf0c1', label: 'Shared Entities' },
                'Business Metric': { color: '#c084fc', bg: 'rgba(192, 132, 252, 0.08)', icon: '\uf201', label: 'Metrics' },
                'Entity':          { color: '#facc15', bg: 'rgba(250, 204, 21, 0.08)', icon: '\uf111', label: 'Entity' }
            };

            const nodeMap = {};

            if (activeCategoryFilter === 'Dataset') {
                    // --- Connection-wise Dataset Layout: 2 Columns ---
                    const masterKeywords = ["master", "codes", "rules", "weather", "availab", "epc"];
                    const leftCol = [];
                    const rightCol = [];

                    nodesToRender.forEach(n => {
                        const nid = n.id.toLowerCase();
                        if (masterKeywords.some(k => nid.includes(k))) {
                            leftCol.push(n);
                        } else {
                            rightCol.push(n);
                        }
                    });

                    const topPadding = 55;
                    const bottomPadding = 40;
                    const availH = height - topPadding - bottomPadding;

                    const leftX = width * 0.28;
                    leftCol.forEach((n, idx) => {
                        const y = leftCol.length === 1
                            ? topPadding + availH / 2
                            : topPadding + (idx / Math.max(leftCol.length - 1, 1)) * availH;
                        nodeMap[n.id] = { ...n, x: leftX, y, cfg: categoryConfig['Dataset'] };
                    });

                    const rightX = width * 0.72;
                    rightCol.forEach((n, idx) => {
                        const y = rightCol.length === 1
                            ? topPadding + availH / 2
                            : topPadding + (idx / Math.max(rightCol.length - 1, 1)) * availH;
                        nodeMap[n.id] = { ...n, x: rightX, y, cfg: categoryConfig['Dataset'] };
                    });
                } else {
                    // --- Decision Tree Layout: tier columns ---
                    const tierNodes = { 0: [], 1: [], 2: [], 3: [] };
                    nodesToRender.forEach(n => {
                        let lvl = typeof n.tree_level === 'number' ? n.tree_level : 0;
                        if (lvl > 3) lvl = 3;
                        tierNodes[lvl].push(n);
                    });
                const colWidth = width / 4;
                const topPadding = 55;
                const bottomPadding = 40;
                const availH = height - topPadding - bottomPadding;
                Object.keys(tierNodes).forEach(lvlKey => {
                    const lvl = parseInt(lvlKey);
                    const list = tierNodes[lvl];
                    
                    // Sort the list so that nodes with the same parent (e.g. Domain) are grouped together visually
                    list.sort((a, b) => {
                        const parentA = (a.parents && a.parents.length > 0) ? a.parents[0] : '';
                        const parentB = (b.parents && b.parents.length > 0) ? b.parents[0] : '';
                        if (parentA < parentB) return -1;
                        if (parentA > parentB) return 1;
                        if (a.id < b.id) return -1;
                        if (a.id > b.id) return 1;
                        return 0;
                    });

                    const centerX = colWidth * lvl + colWidth / 2;
                    list.forEach((n, idx) => {
                        const cat = n.category || 'Metric';
                        const y = list.length === 1
                            ? topPadding + availH / 2
                            : topPadding + (idx / Math.max(list.length - 1, 1)) * availH;
                        nodeMap[n.id] = { ...n, x: centerX, y, cfg: categoryConfig[cat] || categoryConfig['Metric'] };
                    });
                    const colNodes = list.map(n => nodeMap[n.id]).filter(Boolean);
                    colNodes.sort((a, b) => a.y - b.y);
                    const minVertDist = 32;
                    for (let pass = 0; pass < 35; pass++) {
                        for (let i = 0; i < colNodes.length - 1; i++) {
                            const a = colNodes[i], b = colNodes[i + 1];
                            if (b.y - a.y < minVertDist) {
                                const push = (minVertDist - (b.y - a.y)) / 2;
                                a.y = Math.max(topPadding, a.y - push);
                                b.y = Math.min(height - bottomPadding, b.y + push);
                            }
                        }
                    }
                });
            }

            let selectedNodePathSet = new Set();
            let selectedEdgePathSet = new Set();

            function updateSelectedNodePath() {
                selectedNodePathSet.clear();
                selectedEdgePathSet.clear();
                if (!selectedNode) return;
                
                selectedNodePathSet.add(selectedNode.id);
                
                const adjOut = {};
                const adjIn = {};
                (graphData.edges || []).forEach(e => {
                    const src = typeof e.source === 'object' ? e.source.id : e.source;
                    const tgt = typeof e.target === 'object' ? e.target.id : e.target;
                    if (!adjOut[src]) adjOut[src] = [];
                    if (!adjIn[tgt]) adjIn[tgt] = [];
                    adjOut[src].push({ neighbor: tgt, edge: e });
                    adjIn[tgt].push({ neighbor: src, edge: e });
                });
                
                // 1. Traverse Ancestors (Upstream)
                let queue = [selectedNode];
                while(queue.length > 0) {
                    const current = queue.shift();
                    const parents = adjIn[current.id] || [];
                    
                    parents.forEach(link => {
                        if (!selectedNodePathSet.has(link.neighbor)) {
                            selectedNodePathSet.add(link.neighbor);
                            selectedEdgePathSet.add(link.edge);
                            
                            const neighborNode = graphData.nodes.find(n => n.id === link.neighbor);
                            if (neighborNode && neighborNode.category !== 'Key Info Link') {
                                queue.push(neighborNode);
                            }
                        } else {
                            selectedEdgePathSet.add(link.edge);
                        }
                    });
                }
                
                // 2. Traverse Descendants (Downstream)
                queue = [selectedNode];
                while(queue.length > 0) {
                    const current = queue.shift();
                    const children = adjOut[current.id] || [];
                    
                    children.forEach(link => {
                        if (!selectedNodePathSet.has(link.neighbor)) {
                            selectedNodePathSet.add(link.neighbor);
                            selectedEdgePathSet.add(link.edge);
                            
                            const neighborNode = graphData.nodes.find(n => n.id === link.neighbor);
                            if (neighborNode && neighborNode.category !== 'Key Info Link') {
                                queue.push(neighborNode);
                            }
                        } else {
                            selectedEdgePathSet.add(link.edge);
                        }
                    });
                }
            }

            function isNodeInSelectedPath(nodeId) {
                if (!selectedNode) return false;
                return selectedNodePathSet.has(nodeId);
            }

            function draw() {
                if (!isGraphModalOpen) return;
                ctx.clearRect(0, 0, width, height);

                if (activeCategoryFilter === 'Dataset') {
                        const colW = width / 2;
                        const datasetHeaders = [
                            { title: 'PRIMARY MASTER DATASETS', icon: '\uf1c0', color: '#D9662B', x: width * 0.28 },
                            { title: 'OPERATIONAL DATASETS & ACTIVITY', icon: '\uf0ae', color: '#f97316', x: width * 0.72 }
                        ];

                        ctx.save();
                        ctx.fillStyle = 'rgba(255,255,255,0.012)';
                        ctx.fillRect(0, 0, colW, height);
                        ctx.fillStyle = 'rgba(0,0,0,0.25)';
                        ctx.fillRect(colW, 0, colW, height);

                        ctx.strokeStyle = 'rgba(255,255,255,0.08)';
                        ctx.setLineDash([4, 4]);
                        ctx.beginPath();
                        ctx.moveTo(colW, 0);
                        ctx.lineTo(colW, height);
                        ctx.stroke();
                        ctx.setLineDash([]);

                        datasetHeaders.forEach(th => {
                            ctx.font = '900 11px "Font Awesome 6 Free", Inter';
                            ctx.fillStyle = th.color;
                            ctx.textAlign = 'center';
                            ctx.fillText(`${th.icon} ${th.title}`, th.x, 22);
                        });
                        ctx.restore();
                    } else {
                        // Tier column backgrounds
                        const tierHeaders = [
                            { title: 'TIER 0: SYSTEM ROOTS',    icon: '\uf0ad', color: '#22c55e' },
                            { title: 'TIER 1: FAULTS & DATA',   icon: '\uf071', color: '#f43f5e' },
                            { title: 'TIER 2: ROOT CAUSES',     icon: '\uf0e7', color: '#D9662B' },
                            { title: 'TIER 3: REMEDIES & SMEs', icon: '\uf00c', color: '#c084fc' }
                        ];
                        const colW = width / 4;
                        for (let lvl = 0; lvl < 4; lvl++) {
                            const laneX = lvl * colW;
                            ctx.save();
                            ctx.fillStyle = lvl % 2 === 0 ? 'rgba(255,255,255,0.012)' : 'rgba(0,0,0,0.25)';
                            ctx.fillRect(laneX, 0, colW, height);
                            if (lvl > 0) {
                                ctx.strokeStyle = 'rgba(255,255,255,0.05)';
                                ctx.setLineDash([4, 4]);
                                ctx.beginPath();
                                ctx.moveTo(laneX, 0);
                                ctx.lineTo(laneX, height);
                                ctx.stroke();
                                ctx.setLineDash([]);
                            }
                            const th = tierHeaders[lvl];
                            ctx.font = '900 11px "Font Awesome 6 Free", Inter';
                            ctx.fillStyle = th.color;
                            ctx.textAlign = 'center';
                            ctx.fillText(`${th.icon} ${th.title}`, laneX + colW / 2, 22);
                            ctx.restore();
                        }
                    }

                // Draw Edges
                (graphData.edges || []).forEach(e => {
                    const src = nodeMap[e.source];
                    const tgt = nodeMap[e.target];
                    if (src && tgt) {
                        // Hide direct dataset-to-dataset edges unless we are explicitly in the Dataset connection view
                        if (src.category === 'Dataset' && tgt.category === 'Dataset' && activeCategoryFilter !== 'Dataset') {
                            return;
                        }

                        const isConnected = selectedNode && selectedEdgePathSet.has(e);
                        const isEndConn = e.relation === 'need_to_end_connection';
                        ctx.save();
                        ctx.beginPath();

                        const dx = Math.abs(tgt.x - src.x) * 0.45;
                        ctx.moveTo(src.x, src.y);
                        ctx.bezierCurveTo(src.x + dx, src.y, tgt.x - dx, tgt.y, tgt.x, tgt.y);

                        if (isEndConn) {
                            const dashOffset = (Date.now() / 55) % 18;
                            ctx.setLineDash([7, 4]);
                            ctx.lineDashOffset = -dashOffset;
                            ctx.strokeStyle = isConnected ? '#ff1a3a' : 'rgba(255, 40, 70, 0.9)';
                            ctx.lineWidth = isConnected ? 3.2 : 2.4;
                            ctx.shadowColor = '#ff2244';
                            ctx.shadowBlur = isConnected ? 20 : 12;
                        } else {
                            ctx.strokeStyle = isConnected ? '#D9662B' : (selectedNode ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.14)');
                            ctx.lineWidth = isConnected ? 2.8 : 1.1;
                        }
                        ctx.stroke();
                        ctx.setLineDash([]);
                        ctx.shadowBlur = 0;

                        const midX = (src.x + tgt.x) / 2;
                        const midY = (src.y + tgt.y) / 2;
                        const isViaEdge = e.relation && e.relation.startsWith('via:');
                        ctx.font = (isEndConn || isViaEdge) ? '700 10px Inter, sans-serif' : '9px Inter, sans-serif';
                        const textW = ctx.measureText(e.relation).width + 10;
                        ctx.fillStyle = isEndConn ? 'rgba(28,4,8,0.97)' : (isViaEdge ? 'rgba(20, 10, 4, 0.95)' : 'rgba(6,6,6,0.94)');
                        ctx.fillRect(midX - textW / 2, midY - 8, textW, 16);
                        if (isEndConn) {
                            ctx.strokeStyle = 'rgba(255,34,68,0.75)';
                            ctx.lineWidth = 1;
                            ctx.strokeRect(midX - textW / 2, midY - 8, textW, 16);
                            ctx.fillStyle = '#ff4466';
                        } else if (isViaEdge) {
                            ctx.strokeStyle = '#D9662B';
                            ctx.lineWidth = 1;
                            ctx.strokeRect(midX - textW / 2, midY - 8, textW, 16);
                            ctx.fillStyle = '#f97316';
                        } else {
                            ctx.fillStyle = isConnected ? '#D9662B' : '#4b5563';
                        }
                        ctx.textAlign = 'center';
                        ctx.fillText(e.relation, midX, midY + 3);
                        ctx.restore();
                    }
                });

                // Draw Nodes
                Object.values(nodeMap).forEach(n => {
                    const isSelected = selectedNode === n;
                    const inPath = isNodeInSelectedPath(n.id);
                    const displayLabel = getShortLabel(n.label);
                    ctx.font = '700 11px "Font Awesome 6 Free", Inter, sans-serif';
                    const iconStr = n.icon || n.cfg.icon;
                    const textW = ctx.measureText(`${iconStr} ${displayLabel}`).width;
                    const pillW = Math.max(textW + 16, 70);
                    const pillH = 23;
                    const rx = n.x - pillW / 2;
                    const ry = n.y - pillH / 2;

                    ctx.save();
                    ctx.beginPath();
                    if (ctx.roundRect) ctx.roundRect(rx, ry, pillW, pillH, 12);
                    else ctx.rect(rx, ry, pillW, pillH);

                    ctx.fillStyle = isSelected ? 'rgba(32,32,32,0.98)' : (inPath ? 'rgba(22,22,22,0.96)' : 'rgba(14,14,14,0.93)');
                    ctx.fill();
                    ctx.strokeStyle = isSelected ? n.cfg.color : (inPath ? n.cfg.color : (selectedNode ? 'rgba(255,255,255,0.12)' : n.cfg.color));
                    ctx.lineWidth = isSelected ? 3 : (inPath ? 2 : 1.4);
                    ctx.stroke();
                    if (isSelected || inPath) {
                        ctx.shadowColor = n.cfg.color;
                        ctx.shadowBlur = isSelected ? 16 : 8;
                        ctx.stroke();
                    }
                    ctx.fillStyle = (isSelected || inPath || !selectedNode) ? '#f8fafc' : '#6b7280';
                    ctx.textAlign = 'center';
                    ctx.fillText(`${iconStr} ${displayLabel}`, n.x, n.y + 4);
                    ctx.restore();
                });

                requestAnimationFrame(draw);
            }

            draw();

            canvas.onclick = (evt) => {
                const rect = canvas.getBoundingClientRect();
                const clickX = evt.clientX - rect.left;
                const clickY = evt.clientY - rect.top;

                let clicked = null;
                Object.values(nodeMap).forEach(n => {
                    if (Math.abs(n.x - clickX) <= 45 && Math.abs(n.y - clickY) <= 14) clicked = n;
                });

                selectedNode = clicked;
                updateSelectedNodePath();
                const nameEl = document.getElementById('inspectorNodeName');
                const descEl = document.getElementById('inspectorNodeDesc');

                if (clicked) {
                    const connectedEdges = (graphData.edges || []).filter(e => e.source === clicked.id || e.target === clicked.id);
                    const relSummary = connectedEdges.map(e => `• ${e.source} --[ ${e.relation} ]--> ${e.target}`).join('\n');
                    const tierName = clicked.tree_level !== undefined ? `Tier ${clicked.tree_level}` : 'Domain Entity';
                    nameEl.innerText = `${clicked.icon || clicked.cfg.icon} [${tierName} • ${clicked.category}] ${clicked.label}`;
                    descEl.innerText = `${clicked.description || 'Enterprise Knowledge Graph Node'}\n\nDecision Path Connections (${connectedEdges.length}):\n${relSummary || 'None'}`;
                } else {
                    nameEl.innerText = 'Click any graph node to inspect decision tree relationships & attributes';
                    descEl.innerText = 'Select a node from the decision tree canvas above to explore lineage, SMEs, and diagnostic paths.';
                }
            };
        }

        // Initialize welcome message & stepper rendering on load
        document.addEventListener('DOMContentLoaded', () => {
            renderStepper(PIPELINE_STAGES.length);

            const welcomeBubble = document.getElementById('welcomeBubble');
            if (welcomeBubble) {
                const initialText = `Welcome to the **Enterprise Agentic Knowledge Hub**! ⚡

Kickstarting a new project? I help teams discover required enterprise datasets, understand data lineage & SME contacts, and raise automated IT access requests.

• **Natural Language Search**: Explore equipment troubleshooting, metric definitions, and knowledge lineage.
• **Project Dataset Access**: Ask for restricted telemetry or business datasets, and I will assist you in raising an IT access request on your behalf.`;
                welcomeBubble.innerHTML = parseMarkdown(initialText);
            }
        });
    
    