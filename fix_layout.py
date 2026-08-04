import re

with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

def restructure_tab(tab_id, process_title, process_html, explanation, dashboard_title, dashboard_html, feature_title, feature_html, chart_title, chart_id):
    feature_section = ""
    if feature_title:
        feature_section = f"""<h4 class="tab-section-title" style="margin-top: 16px; margin-bottom: 8px; flex-shrink: 0;">{feature_title}</h4>
                    <div>
                        {feature_html}
                    </div>"""

    return f"""<div id="{tab_id}" class="tab-content" style="padding: 16px 24px; overflow: hidden; flex-direction: column; height: 100%; box-sizing: border-box;">
            <!-- Top Half: Two Columns -->
            <div style="display: flex; gap: 32px; flex-shrink: 0; margin-bottom: 16px;">
                <!-- Left Column -->
                <div style="flex: 1.2; display: flex; flex-direction: column;">
                    <h4 class="tab-section-title" style="margin-top: 0; flex-shrink: 0;">{process_title}</h4>
                    {process_html}
                    
                    <div class="explanation-text" style="margin-top: 4px; font-size: 11.5px; line-height: 1.5;">
                        {explanation}
                    </div>
                </div>
                
                <!-- Right Column -->
                <div style="flex: 1; display: flex; flex-direction: column;">
                    <h4 class="tab-section-title" style="margin-top: 0; flex-shrink: 0;">{dashboard_title}</h4>
                    <div>
                        {dashboard_html}
                    </div>
                    {feature_section}
                </div>
            </div>
            
            <!-- Bottom Half: Full Width Chart -->
            <div style="flex: 1; display: flex; flex-direction: column; background: rgba(20, 20, 20, 0.8); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 12px; min-height: 0;">
                <h4 style="font-size: 11px; color: #fff; text-transform: uppercase; margin-bottom: 8px; margin-top: 0; flex-shrink: 0;">{chart_title}</h4>
                <div style="position: relative; flex: 1; width: 100%; min-height: 0;">
                    <canvas id="{chart_id}"></canvas>
                </div>
            </div>
        </div>"""

tab_info = restructure_tab(
    "tab-info",
    "Architecture Pipeline",
    """<div class="process-flow" style="flex-shrink: 0;">
                <div class="process-step">
                    <h4>1. Connectors</h4>
                    <p>APIs pull from SAP, Snowflake & SharePoint</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. Parser</h4>
                    <p>Extracts text, tables, and images from docs</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. Cleaning</h4>
                    <p>Deduplication and canonicalization</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. Staging</h4>
                    <p>Clean data lands in AWS S3</p>
                </div>
            </div>""",
    "<strong>How it works:</strong> The Information Harnessing layer is the foundation of the intelligence hub. We use highly concurrent webhooks and API connectors to synchronize data from our enterprise systems in real-time. Unstructured documents like PDFs and manuals are passed through a vision-language model to accurately parse tables and diagrams before text is extracted.",
    "Live Telemetry",
    """<div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">Total Documents</div>
                    <div class="metric-value" id="metric-docs">1.4M</div>
                    <div class="metric-change">↑ 12% this week</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Daily Volume</div>
                    <div class="metric-value">4.2 TB</div>
                    <div class="metric-change" style="color: var(--text-muted);">Stable</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Data Connectors</div>
                    <div class="metric-value">24</div>
                    <div class="metric-change">↑ 2 new added</div>
                </div>
            </div>""",
    "Source Lineage Status",
    """<div class="feature-list">
                <div class="feature-item">
                    <span>🗄️ SharePoint Manuals</span>
                    <span class="status-badge">Synced Live</span>
                </div>
                <div class="feature-item">
                    <span>❄️ Snowflake Data</span>
                    <span class="status-badge">Synced Live</span>
                </div>
                <div class="feature-item">
                    <span>🔧 SAP Registry</span>
                    <span id="sap-sync-status" class="status-badge" style="background: rgba(250, 204, 21, 0.15); color: #facc15;">Syncing (92%)</span>
                </div>
            </div>""",
    "Ingestion Volume (Last 7 Days)", "chart-info"
)

tab_knowledge = restructure_tab(
    "tab-knowledge",
    "Semantic Workflow",
    """<div class="process-flow" style="flex-shrink: 0;">
                <div class="process-step">
                    <h4>1. Chunking</h4>
                    <p>Split into semantic context windows</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. Extraction</h4>
                    <p>Identify assets, people, and metrics</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. Mapping</h4>
                    <p>Linking entities contextually</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. Knowledge Graph</h4>
                    <p>Nodes injected into Neo4j</p>
                </div>
            </div>""",
    "<strong>How it works:</strong> Once data is ingested, it must be structured so the AI can \"understand\" business context. We use specialized NLP pipelines to perform Named Entity Recognition (NER) to pull out critical business terms. These terms are mapped against our custom enterprise ontology, creating a massive, interconnected Knowledge Graph that links unstructured text directly to structured SQL tables and SME ownership.",
    "Graph Metrics",
    """<div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">Graph Nodes</div>
                    <div class="metric-value" id="metric-nodes">845,210</div>
                    <div class="metric-change" style="color: var(--text-muted);">Entities Identified</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Relationship Edges</div>
                    <div class="metric-value" id="metric-edges">3.2M</div>
                    <div class="metric-change" style="color: var(--text-muted);">Semantic Links</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Ontology Confidence</div>
                    <div class="metric-value">98.4%</div>
                    <div class="metric-change">↑ 0.2% improvement</div>
                </div>
            </div>""",
    "", "", "Graph Entities Growth", "chart-knowledge"
)

tab_inference = restructure_tab(
    "tab-inference",
    "Query Execution Engine",
    """<div class="process-flow" style="flex-shrink: 0;">
                <div class="process-step">
                    <h4>1. Intent Router</h4>
                    <p>Classifies query as Search/Task</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. GraphRAG</h4>
                    <p>Hybrid search across Vector/Graph</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. Assembly</h4>
                    <p>Inject context into prompt</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. LLM Gen</h4>
                    <p>Streams grounded response</p>
                </div>
            </div>""",
    "<strong>How it works:</strong> The Inference layer powers the chatbot. When a user asks a question, an intent router determines what tools the AI agent needs. We utilize Graph-based Retrieval-Augmented Generation (GraphRAG) to pull highly relevant contextual snippets. This ensures the Large Language Model generates answers that are strictly grounded in our enterprise data, minimizing hallucination and ensuring compliance.",
    "Model Performance",
    """<div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">Query Latency</div>
                    <div class="metric-value">420ms</div>
                    <div class="metric-change">↓ 15ms faster</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Vector Precision</div>
                    <div class="metric-value">94.8%</div>
                    <div class="metric-change" style="color: var(--text-muted);">Top-K Match Rate</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Active AI Models</div>
                    <div class="metric-value">3</div>
                    <div class="metric-change" style="color: var(--text-muted);">Router, Embed, Generate</div>
                </div>
            </div>""",
    "", "", "Query Latency (ms)", "chart-inference"
)

tab_outcome = restructure_tab(
    "tab-outcome",
    "Value Generation Loop",
    """<div class="process-flow" style="flex-shrink: 0;">
                <div class="process-step">
                    <h4>1. Resolution</h4>
                    <p>Agent solves query autonomously</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. Deflection</h4>
                    <p>Time saved logged for SMEs</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. Feedback</h4>
                    <p>User feedback feeds into system</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. ROI Dashboard</h4>
                    <p>Real-time cost savings view</p>
                </div>
            </div>""",
    "<strong>How it works:</strong> The ultimate goal of the AI Hub is driving measurable business outcomes. We actively track when the AI successfully resolves a query (like dataset discovery or troubleshooting) versus when it escalates to an IT ticket. By measuring SME (Subject Matter Expert) deflection rates and turnaround times, we quantify the monetary value and efficiency gains the AI agent brings to the enterprise.",
    "Business Impact",
    """<div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">Automated Res.</div>
                    <div class="metric-value" id="metric-auto-res">12,450</div>
                    <div class="metric-change">↑ 18% vs Last Month</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">SME Hours Saved</div>
                    <div class="metric-value">840 hrs</div>
                    <div class="metric-change" style="color: var(--text-muted);">Estimated this week</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Resolution Time</div>
                    <div class="metric-value">- 45%</div>
                    <div class="metric-change">Reduced turnaround</div>
                </div>
            </div>""",
    "", "", "Automated Resolutions vs Escalations", "chart-outcome"
)

tab_benchmarking = restructure_tab(
    "tab-benchmarking",
    "Evaluation Pipeline",
    """<div class="process-flow" style="flex-shrink: 0;">
                <div class="process-step">
                    <h4>1. Golden Data</h4>
                    <p>Curated Q&A pairs validated</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. Batch Inference</h4>
                    <p>System runs queries overnight</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. LLM-as-a-Judge</h4>
                    <p>Model grades responses</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. CI/CD Gate</h4>
                    <p>Blocks deploy if drop < 90%</p>
                </div>
            </div>""",
    "<strong>How it works:</strong> To ensure trust, the system is continuously evaluated. We maintain a \"Golden Dataset\" of hundreds of complex business questions and their exact correct answers. Every time a change is made to the pipeline or LLM prompt, we run an automated benchmark suite overnight. This calculates precision, recall, and hallucination rates, acting as an automated CI/CD guardrail for AI quality.",
    "Evaluation Metrics",
    """<div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">F1 Score</div>
                    <div class="metric-value" id="metric-f1">0.92</div>
                    <div class="metric-change">↑ Excellent</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">SME Agreement</div>
                    <div class="metric-value">96.5%</div>
                    <div class="metric-change" style="color: var(--text-muted);">Human Verification</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Hallucination</div>
                    <div class="metric-value">0.04%</div>
                    <div class="metric-change">↓ Below 1% threshold</div>
                </div>
            </div>""",
    "", "", "F1 Score Trend", "chart-benchmarking"
)

tab_storage = restructure_tab(
    "tab-storage",
    "Data Topology",
    """<div class="process-flow" style="flex-shrink: 0;">
                <div class="process-step">
                    <h4>1. Object Storage</h4>
                    <p>Raw files in AWS S3 buckets</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. Document DB</h4>
                    <p>Parsed JSON in MongoDB</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. Vector Store</h4>
                    <p>High-dim embeddings in Milvus</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. Graph DB</h4>
                    <p>Relationships in Neo4j</p>
                </div>
            </div>""",
    "<strong>How it works:</strong> The backend is powered by a multi-database architecture optimized for AI. Object storage retains raw files for auditability. Document databases store parsed semi-structured data. For lightning-fast semantic search, we use a scalable Vector Database to query embeddings. Finally, a Graph Database maintains the complex web of relationships for entity traversal and reasoning.",
    "Capacity & Health",
    """<div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">Vector DB Util</div>
                    <div class="metric-value">42%</div>
                    <div class="metric-change" style="color: var(--text-muted);">Scale: Normal</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Graph DB Size</div>
                    <div class="metric-value">18.4 GB</div>
                    <div class="metric-change" style="color: var(--text-muted);">Optimal Cache Hit</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Cold Storage</div>
                    <div class="metric-value">124 TB</div>
                    <div class="metric-change" style="color: var(--text-muted);">Archived Data</div>
                </div>
            </div>""",
    "System Status",
    """<div class="feature-list">
                <div class="feature-item">
                    <span>Milvus Vector Cluster</span>
                    <span class="status-badge">Operational</span>
                </div>
                <div class="feature-item">
                    <span>Neo4j Graph Database</span>
                    <span class="status-badge">Operational</span>
                </div>
                <div class="feature-item">
                    <span>AWS S3 Datalake Storage</span>
                    <span class="status-badge">Operational</span>
                </div>
            </div>""",
    "Database Utilization", "chart-storage"
)

# Replace the entire block of tabs.
pattern = re.compile(r'<div id="tab-info".*?</main>', re.DOTALL)
replacement = f"{tab_info}\n{tab_knowledge}\n{tab_inference}\n{tab_outcome}\n{tab_benchmarking}\n{tab_storage}\n    </main>"
content = re.sub(pattern, replacement, content)

# Update dashboard grid CSS to use smaller minmax so 3 cards can fit easily in the right column
content = content.replace('minmax(130px, 1fr)', 'minmax(120px, 1fr)')

with open('app/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Layout fixed successfully.")
