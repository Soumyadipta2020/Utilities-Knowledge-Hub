import re

with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to match the h3 and p tags at the top of each tab
pattern = re.compile(
    r'[ \t]*<h3 style="font-family: \'Outfit\', sans-serif; font-size: 18px; color: #fff; margin: 0; flex-shrink: 0;">.*?</h3>\s*<p style="color: var\(--text-muted\); font-size: 11\.5px; margin-top: 4px; margin-bottom: 12px; flex-shrink: 0;">.*?</p>\s*',
    re.DOTALL
)

# Remove the matched headers
new_content = re.sub(pattern, '', content)

with open('app/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Headers removed successfully.")
