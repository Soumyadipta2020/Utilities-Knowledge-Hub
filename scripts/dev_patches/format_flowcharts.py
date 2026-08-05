import re

with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(
    r'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; gap: 4px;">\s*<h4 style="margin: 0; line-height: 1\.2;">(.*?)</h4>\s*<span style="font-size: 9px; font-weight: bold; color: #22c55e; background: rgba\(34, 197, 94, 0\.15\); padding: 2px 4px; border-radius: 4px; white-space: nowrap;">(.*?)</span>\s*</div>'
)

replacement = r'''<h4 style="margin: 0; line-height: 1.2; color: var(--accent-orange); font-size: 12px; margin-bottom: 6px;">\1</h4>
                    <div style="margin-bottom: 6px;"><span style="font-size: 9.5px; font-weight: bold; color: #22c55e; background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3); padding: 2px 6px; border-radius: 4px; white-space: nowrap; display: inline-block;">\2</span></div>'''

new_content = re.sub(pattern, replacement, content)

with open('app/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Flowcharts formatted successfully.")
