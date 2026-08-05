import re
import sys

# Define the metrics for each tab
tab_metrics = {
    'tab-info': ['24 Sources', '1.4M Docs', '4.2 TB', '100% Synced'],
    'tab-knowledge': ['5.6M Chunks', '845k Entities', '3.2M Edges', '98.4% Conf'],
    'tab-inference': ['99% Acc', '94.8% Prec', '120ms', '420ms'],
    'tab-outcome': ['12.4k Res', '840 Hrs', '4.8/5 Rating', '$1.2M ROI'],
    'tab-benchmarking': ['5k Pairs', 'Overnight', '96.5% Agr', '0.04% Hall'],
    'tab-storage': ['124 TB', '18.4 GB', '42% Util', '3.2M Edges']
}

try:
    with open('app/templates/index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Function to replace process-steps in a specific tab
    def process_tab(tab_id, metrics):
        global content
        # Find the block for the tab
        tab_start = content.find(f'<div id="{tab_id}"')
        if tab_start == -1:
            print(f"Tab {tab_id} not found!")
            return
            
        # Find the end of the tab (rough estimation by looking for the next tab or </main>)
        next_tab_start = content.find('<div id="tab-', tab_start + 10)
        if next_tab_start == -1:
            next_tab_start = content.find('</main>', tab_start)
            
        tab_content = content[tab_start:next_tab_start]
        
        step_pattern = re.compile(r'<div class="process-step">\s*<h4>(.*?)</h4>\s*<p>(.*?)</p>\s*</div>')
        
        step_idx = 0
        def step_replacer(match):
            nonlocal step_idx
            if step_idx < len(metrics):
                metric = metrics[step_idx]
                step_idx += 1
                return f"""<div class="process-step">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; gap: 4px;">
                        <h4 style="margin: 0; line-height: 1.2;">{match.group(1)}</h4>
                        <span style="font-size: 9px; font-weight: bold; color: #22c55e; background: rgba(34, 197, 94, 0.15); padding: 2px 4px; border-radius: 4px; white-space: nowrap;">{metric}</span>
                    </div>
                    <p style="margin: 0;">{match.group(2)}</p>
                </div>"""
            else:
                return match.group(0)
                
        new_tab_content = re.sub(step_pattern, step_replacer, tab_content)
        
        # Update main content
        content = content[:tab_start] + new_tab_content + content[next_tab_start:]

    for tab_id, metrics in tab_metrics.items():
        process_tab(tab_id, metrics)

    with open('app/templates/index.html', 'w', encoding='utf-8') as f:
        f.write(content)

    print("Step metrics added successfully.")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
