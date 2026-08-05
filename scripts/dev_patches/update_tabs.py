import re
import os

filepath = 'app/templates/index.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add CSS before </style>
css_addition = """
        .process-flow {
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 28px 0;
            overflow-x: auto;
            padding-bottom: 8px;
        }
        .process-step {
            background: rgba(30, 30, 30, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 14px;
            min-width: 160px;
            text-align: center;
            flex-shrink: 0;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
        .process-step h4 {
            font-size: 13px;
            color: var(--accent-orange);
            margin-bottom: 6px;
        }
        .process-step p {
            font-size: 11px;
            color: var(--text-muted);
            line-height: 1.4;
        }
        .process-arrow {
            color: rgba(255, 255, 255, 0.2);
            font-size: 16px;
            flex-shrink: 0;
        }
        .tab-section-title {
            font-size: 15px;
            color: #fff;
            margin-top: 32px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 8px;
            margin-bottom: 16px;
        }
        .explanation-text {
            font-size: 13px;
            color: var(--text-muted);
            line-height: 1.6;
            margin-bottom: 16px;
        }
"""
content = content.replace("    </style>", css_addition + "    </style>")

# 2. Replace tab-info
tab_info_new = """<div id="tab-info" class="tab-content" style="padding: 24px 32px; overflow-y: auto;">
            <h3 style="font-family: 'Outfit', sans-serif; font-size: 22px; color: #fff;">Information Harnessing</h3>
            <p style="color: var(--text-muted); font-size: 13px; margin-top: 8px;">Ingestion, parsing, and structured translation of multi-modal enterprise data sources.</p>
            
            <h4 class="tab-section-title">Architecture Pipeline</h4>
            <div class="process-flow">
                <div class="process-step">
                    <h4>1. Data Connectors</h4>
                    <p>APIs pull from SAP, Snowflake & SharePoint</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. Multi-modal Parser</h4>
                    <p>Extracts text, tables, and images from raw docs</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. Cleaning Engine</h4>
                    <p>Deduplication and canonicalization of records</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. Staging Lake</h4>
                    <p>Clean data lands in AWS S3 for embedding</p>
                </div>
            </div>

            <div class="explanation-text">
                <strong>How it works:</strong> The Information Harnessing layer is the foundation of the intelligence hub. We use highly concurrent webhooks and API connectors to synchronize data from our enterprise systems in real-time. Unstructured documents like PDFs and manuals are passed through a vision-language model to accurately parse tables and diagrams before text is extracted.
            </div>

            <h4 class="tab-section-title">Live Telemetry</h4>
            <div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">Total Documents Ingested</div>
                    <div class="metric-value" id="metric-docs">1.4M</div>
                    <div class="metric-change">↑ 12% this week</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Daily Processing Volume</div>
                    <div class="metric-value">4.2 TB</div>
                    <div class="metric-change" style="color: var(--text-muted);">Stable</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Active Data Connectors</div>
                    <div class="metric-value">24</div>
                    <div class="metric-change">↑ 2 new added</div>
                </div>
            </div>

            <h4 class="tab-section-title">Source Lineage Status</h4>
            <div class="feature-list">
                <div class="feature-item">
                    <span>🗄️ SharePoint Manuals & Tech Docs</span>
                    <span class="status-badge">Synced Live</span>
                </div>
                <div class="feature-item">
                    <span>❄️ Snowflake Telemetry Data</span>
                    <span class="status-badge">Synced Live</span>
                </div>
                <div class="feature-item">
                    <span>🔧 SAP Equipment Registry</span>
                    <span id="sap-sync-status" class="status-badge" style="background: rgba(250, 204, 21, 0.15); color: #facc15;">Syncing (92%)</span>
                </div>
            </div>
        </div>"""

content = re.sub(r'<div id="tab-info".*?(?=<div id="tab-knowledge")', tab_info_new + '\n\n        ', content, flags=re.DOTALL)

# 3. Replace tab-knowledge
tab_knowledge_new = """<div id="tab-knowledge" class="tab-content" style="padding: 24px 32px; overflow-y: auto;">
            <h3 style="font-family: 'Outfit', sans-serif; font-size: 22px; color: #fff;">Knowledge Harnessing</h3>
            <p style="color: var(--text-muted); font-size: 13px; margin-top: 8px;">Entity extraction, relationship mapping, and enterprise ontology building.</p>

            <h4 class="tab-section-title">Semantic Workflow</h4>
            <div class="process-flow">
                <div class="process-step">
                    <h4>1. Chunking</h4>
                    <p>Documents split into semantic context windows</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. Entity Extraction</h4>
                    <p>NLP models identify assets, people, and metrics</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. Relationship Mapping</h4>
                    <p>Linking entities (e.g. "Boiler" -> "Maintained By" -> "John")</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. Knowledge Graph</h4>
                    <p>Nodes & edges injected into Neo4j graph database</p>
                </div>
            </div>

            <div class="explanation-text">
                <strong>How it works:</strong> Once data is ingested, it must be structured so the AI can "understand" business context. We use specialized NLP pipelines to perform Named Entity Recognition (NER) to pull out critical business terms. These terms are mapped against our custom enterprise ontology, creating a massive, interconnected Knowledge Graph that links unstructured text directly to structured SQL tables and SME ownership.
            </div>

            <h4 class="tab-section-title">Graph Metrics</h4>
            <div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">Knowledge Graph Nodes</div>
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
            </div>
        </div>"""

content = re.sub(r'<div id="tab-knowledge".*?(?=<div id="tab-inference")', tab_knowledge_new + '\n\n        ', content, flags=re.DOTALL)

# 4. Replace tab-inference
tab_inference_new = """<div id="tab-inference" class="tab-content" style="padding: 24px 32px; overflow-y: auto;">
            <h3 style="font-family: 'Outfit', sans-serif; font-size: 22px; color: #fff;">Inference Harnessing</h3>
            <p style="color: var(--text-muted); font-size: 13px; margin-top: 8px;">LLM Reasoning, vector search, and agentic multi-step task execution.</p>

            <h4 class="tab-section-title">Query Execution Engine</h4>
            <div class="process-flow">
                <div class="process-step">
                    <h4>1. Intent Router</h4>
                    <p>Classifies query as Search, Task, or SQL Request</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. GraphRAG Retrieval</h4>
                    <p>Hybrid search across Vector DB and Knowledge Graph</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. Prompt Assembly</h4>
                    <p>Injects retrieved context & guardrails into prompt</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. LLM Generation</h4>
                    <p>Foundational model streams final grounded response</p>
                </div>
            </div>

            <div class="explanation-text">
                <strong>How it works:</strong> The Inference layer powers the chatbot. When a user asks a question, an intent router determines what tools the AI agent needs. We utilize Graph-based Retrieval-Augmented Generation (GraphRAG) to pull highly relevant contextual snippets. This ensures the Large Language Model generates answers that are strictly grounded in our enterprise data, minimizing hallucination and ensuring compliance.
            </div>

            <h4 class="tab-section-title">Model Performance</h4>
            <div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">Avg Query Latency</div>
                    <div class="metric-value">420ms</div>
                    <div class="metric-change">↓ 15ms faster</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Vector Search Precision</div>
                    <div class="metric-value">94.8%</div>
                    <div class="metric-change" style="color: var(--text-muted);">Top-K Match Rate</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Active AI Models</div>
                    <div class="metric-value">3</div>
                    <div class="metric-change" style="color: var(--text-muted);">Router, Embed, Generate</div>
                </div>
            </div>
        </div>"""

content = re.sub(r'<div id="tab-inference".*?(?=<div id="tab-outcome")', tab_inference_new + '\n\n        ', content, flags=re.DOTALL)

# 5. Replace tab-outcome
tab_outcome_new = """<div id="tab-outcome" class="tab-content" style="padding: 24px 32px; overflow-y: auto;">
            <h3 style="font-family: 'Outfit', sans-serif; font-size: 22px; color: #fff;">Outcome Harnessing</h3>
            <p style="color: var(--text-muted); font-size: 13px; margin-top: 8px;">Business value metrics, ROI tracking, and resolution impact.</p>

            <h4 class="tab-section-title">Value Generation Loop</h4>
            <div class="process-flow">
                <div class="process-step">
                    <h4>1. Automated Resolution</h4>
                    <p>Agent solves user query without human escalation</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. SME Deflection</h4>
                    <p>Time saved logged for Subject Matter Experts</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. Feedback Tracking</h4>
                    <p>User thumbs up/down feeds back into system</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. ROI Dashboard</h4>
                    <p>Business leaders view cost savings in real-time</p>
                </div>
            </div>

            <div class="explanation-text">
                <strong>How it works:</strong> The ultimate goal of the AI Hub is driving measurable business outcomes. We actively track when the AI successfully resolves a query (like dataset discovery or troubleshooting) versus when it escalates to an IT ticket. By measuring SME (Subject Matter Expert) deflection rates and turnaround times, we quantify the monetary value and efficiency gains the AI agent brings to the enterprise.
            </div>

            <h4 class="tab-section-title">Business Impact</h4>
            <div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">Automated Resolutions</div>
                    <div class="metric-value" id="metric-auto-res">12,450</div>
                    <div class="metric-change">↑ 18% vs Last Month</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">SME Hours Saved</div>
                    <div class="metric-value">840 hrs</div>
                    <div class="metric-change" style="color: var(--text-muted);">Estimated this week</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Time to Resolution</div>
                    <div class="metric-value">- 45%</div>
                    <div class="metric-change">Reduced turnaround</div>
                </div>
            </div>
        </div>"""

content = re.sub(r'<div id="tab-outcome".*?(?=<div id="tab-benchmarking")', tab_outcome_new + '\n\n        ', content, flags=re.DOTALL)

# 6. Replace tab-benchmarking
tab_benchmarking_new = """<div id="tab-benchmarking" class="tab-content" style="padding: 24px 32px; overflow-y: auto;">
            <h3 style="font-family: 'Outfit', sans-serif; font-size: 22px; color: #fff;">Benchmarking</h3>
            <p style="color: var(--text-muted); font-size: 13px; margin-top: 8px;">Continuous evaluation of response accuracy against ground truth datasets.</p>

            <h4 class="tab-section-title">Evaluation Pipeline</h4>
            <div class="process-flow">
                <div class="process-step">
                    <h4>1. Golden Dataset</h4>
                    <p>Curated Q&A pairs validated by human experts</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. Batch Inference</h4>
                    <p>System automatically runs queries overnight</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. LLM-as-a-Judge</h4>
                    <p>Stronger model grades responses for accuracy</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. CI/CD Gate</h4>
                    <p>Blocks deployment if precision drops below 90%</p>
                </div>
            </div>

            <div class="explanation-text">
                <strong>How it works:</strong> To ensure trust, the system is continuously evaluated. We maintain a "Golden Dataset" of hundreds of complex business questions and their exact correct answers. Every time a change is made to the pipeline or LLM prompt, we run an automated benchmark suite overnight. This calculates precision, recall, and hallucination rates, acting as an automated CI/CD guardrail for AI quality.
            </div>

            <h4 class="tab-section-title">Evaluation Metrics</h4>
            <div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">F1 Score</div>
                    <div class="metric-value" id="metric-f1">0.92</div>
                    <div class="metric-change">↑ Excellent</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Human-in-the-loop Agreement</div>
                    <div class="metric-value">96.5%</div>
                    <div class="metric-change" style="color: var(--text-muted);">SME Verification</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Hallucination Rate</div>
                    <div class="metric-value">0.04%</div>
                    <div class="metric-change">↓ Below 1% threshold</div>
                </div>
            </div>
        </div>"""

content = re.sub(r'<div id="tab-benchmarking".*?(?=<div id="tab-storage")', tab_benchmarking_new + '\n\n        ', content, flags=re.DOTALL)

# 7. Replace tab-storage
tab_storage_new = """<div id="tab-storage" class="tab-content" style="padding: 24px 32px; overflow-y: auto;">
            <h3 style="font-family: 'Outfit', sans-serif; font-size: 22px; color: #fff;">Storage</h3>
            <p style="color: var(--text-muted); font-size: 13px; margin-top: 8px;">Infrastructure health, database utilization, and vector cluster status.</p>

            <h4 class="tab-section-title">Data Topology</h4>
            <div class="process-flow">
                <div class="process-step">
                    <h4>1. Object Storage</h4>
                    <p>Raw files stored in AWS S3 buckets</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>2. Document DB</h4>
                    <p>Parsed JSON stored in MongoDB</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>3. Vector Store</h4>
                    <p>High-dim embeddings in Milvus cluster</p>
                </div>
                <div class="process-arrow">➔</div>
                <div class="process-step">
                    <h4>4. Graph DB</h4>
                    <p>Relationships stored in Neo4j instances</p>
                </div>
            </div>

            <div class="explanation-text">
                <strong>How it works:</strong> The backend is powered by a multi-database architecture optimized for AI. Object storage retains raw files for auditability. Document databases store parsed semi-structured data. For lightning-fast semantic search, we use a scalable Vector Database to query embeddings. Finally, a Graph Database maintains the complex web of relationships for entity traversal and reasoning.
            </div>

            <h4 class="tab-section-title">Capacity & Health</h4>
            <div class="dashboard-grid">
                <div class="metric-card">
                    <div class="metric-title">Vector DB Utilization</div>
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
            </div>
            
            <h4 class="tab-section-title">System Status</h4>
            <div class="feature-list">
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
            </div>
        </div>"""

content = re.sub(r'<div id="tab-storage".*?</main>', tab_storage_new + '\n    </main>', content, flags=re.DOTALL)


with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updates completed successfully")
