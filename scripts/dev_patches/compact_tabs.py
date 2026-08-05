import re

with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update CSS
css_replacements = {
    r'\.process-flow \{[^}]+\}': """.process-flow {
            display: flex;
            align-items: stretch;
            gap: 10px;
            margin: 10px 0;
        }""",
    r'\.process-step \{[^}]+\}': """.process-step {
            background: rgba(30, 30, 30, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            padding: 10px;
            flex: 1;
            text-align: center;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            justify-content: center;
        }""",
    r'\.process-step h4 \{[^}]+\}': """.process-step h4 {
            font-size: 12px;
            color: var(--accent-orange);
            margin-bottom: 4px;
        }""",
    r'\.process-step p \{[^}]+\}': """.process-step p {
            font-size: 10.5px;
            color: var(--text-muted);
            line-height: 1.3;
        }""",
    r'\.process-arrow \{[^}]+\}': """.process-arrow {
            color: rgba(255, 255, 255, 0.2);
            font-size: 14px;
            display: flex;
            align-items: center;
        }""",
    r'\.tab-section-title \{[^}]+\}': """.tab-section-title {
            font-size: 12px;
            color: #fff;
            margin-top: 14px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 4px;
            margin-bottom: 8px;
        }""",
    r'\.explanation-text \{[^}]+\}': """.explanation-text {
            font-size: 11.5px;
            color: var(--text-muted);
            line-height: 1.4;
            margin-bottom: 8px;
        }""",
    r'\.dashboard-grid \{[^}]+\}': """.dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
        }""",
    r'\.metric-card \{[^}]+\}': """.metric-card {
            background: rgba(20, 20, 20, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            transition: transform 0.2s;
        }""",
    r'\.metric-title \{[^}]+\}': """.metric-title {
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }""",
    r'\.metric-value \{[^}]+\}': """.metric-value {
            font-size: 22px;
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            color: #fff;
        }""",
    r'\.feature-list \{[^}]+\}': """.feature-list {
            margin-top: 8px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }""",
    r'\.feature-item \{[^}]+\}': """.feature-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 12px;
            background: rgba(10, 10, 10, 0.6);
            border-radius: 6px;
            border: 1px solid rgba(255,255,255,0.05);
            font-size: 11.5px;
        }"""
}

for pattern, replacement in css_replacements.items():
    content = re.sub(pattern, replacement, content)

# 2. Update inline styles in HTML for compactness
content = content.replace('padding: 24px 32px;', 'padding: 12px 24px;')
content = content.replace('font-size: 22px;', 'font-size: 18px; margin: 0;')
content = content.replace('font-size: 13px; margin-top: 8px;', 'font-size: 12px; margin-top: 4px; margin-bottom: 8px;')

with open('app/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Compacting updates completed successfully")
