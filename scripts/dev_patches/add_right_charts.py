import re

with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

charts_info = {
    'tab-info': ('chart-info-2', 'Data Sources Breakdown'),
    'tab-knowledge': ('chart-knowledge-2', 'Entity Types Distribution'),
    'tab-inference': ('chart-inference-2', 'Model Requests (Last 6h)'),
    'tab-outcome': ('chart-outcome-2', 'Estimated Cost Savings ($)'),
    'tab-benchmarking': ('chart-benchmarking-2', 'Category Accuracy'),
    'tab-storage': ('chart-storage-2', 'Weekly Data Growth (TB)')
}

# 1. Add chart HTML to the right column of each tab
for tab_id, (chart_id, chart_title) in charts_info.items():
    # Find the end of the right column for this tab.
    # The right column ends right before the closing </div> of the .tab-content (which is before the next <div id="tab-... or </main>)
    # But wait, there are two closing </div>s at the end of the tab (one for the flex row wrapper, one for tab-content).
    # It's easier to just match the end of the right column. In our previous script, the right column was:
    # <!-- Right Column -->
    # <div style="flex: 1; ...">
    # ...
    # </div>
    # </div>
    # </div>
    
    chart_html = f"""
                    <div style="flex: 1; display: flex; flex-direction: column; background: rgba(20, 20, 20, 0.8); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 12px; min-height: 0; margin-top: 12px;">
                        <h4 style="font-size: 11px; color: #fff; text-transform: uppercase; margin-bottom: 8px; margin-top: 0; flex-shrink: 0;">{chart_title}</h4>
                        <div style="position: relative; flex: 1; width: 100%; min-height: 0;">
                            <canvas id="{chart_id}"></canvas>
                        </div>
                    </div>"""
    
    # We will inject chart_html right before the closing </div> of the right column.
    # Let's find the specific block for the tab.
    tab_pattern = re.compile(rf'(<div id="{tab_id}".*?<!-- Right Column -->.*?)(</div>\s*</div>\s*</div>)', re.DOTALL)
    
    # Wait, the Right column has feature_section at the bottom, which ends with a </div>. Then the right column ends with </div>, then the flex container ends with </div>, then the tab ends with </div>.
    # Let's just find the last </div> before the end of the flex container.
    # A safer approach: insert right before `\s*</div>\s*</div>\s*</div>\s*(?:<div id="tab-|</main>)`
    
    def replacer(match):
        return match.group(1) + chart_html + "\n                " + match.group(2)
        
    content = re.sub(tab_pattern, replacer, content)

# 2. Add the JS initialization for the new charts
new_charts_js = """
        // Info Tab Chart 2 (Doughnut)
        if(document.getElementById('chart-info-2')) {
            window.dashboardCharts['info-2'] = new Chart(document.getElementById('chart-info-2'), {
                type: 'doughnut',
                data: {
                    labels: ['SharePoint', 'Snowflake', 'SAP', 'Other'],
                    datasets: [{
                        data: [45, 25, 20, 10],
                        backgroundColor: [primaryBg, secondaryBg, 'rgba(59, 130, 246, 0.2)', 'rgba(168, 85, 247, 0.2)'],
                        borderColor: [primaryColor, secondaryColor, '#3b82f6', '#a855f7'],
                        borderWidth: 1
                    }]
                },
                options: { ...chartOptions, plugins: { legend: { display: true, position: 'right', labels: {color: '#a1a1aa', boxWidth: 10, font: {size: 10}} } }, scales: {x: {display: false}, y: {display: false}} }
            });
        }

        // Knowledge Tab Chart 2 (Pie)
        if(document.getElementById('chart-knowledge-2')) {
            window.dashboardCharts['knowledge-2'] = new Chart(document.getElementById('chart-knowledge-2'), {
                type: 'pie',
                data: {
                    labels: ['People', 'Assets', 'Locations', 'Metrics'],
                    datasets: [{
                        data: [30, 40, 15, 15],
                        backgroundColor: [primaryBg, secondaryBg, 'rgba(59, 130, 246, 0.2)', 'rgba(239, 68, 68, 0.2)'],
                        borderColor: [primaryColor, secondaryColor, '#3b82f6', 'rgba(239, 68, 68, 1)'],
                        borderWidth: 1
                    }]
                },
                options: { ...chartOptions, plugins: { legend: { display: true, position: 'right', labels: {color: '#a1a1aa', boxWidth: 10, font: {size: 10}} } }, scales: {x: {display: false}, y: {display: false}} }
            });
        }

        // Inference Tab Chart 2 (Bar)
        if(document.getElementById('chart-inference-2')) {
            window.dashboardCharts['inference-2'] = new Chart(document.getElementById('chart-inference-2'), {
                type: 'bar',
                data: {
                    labels: ['Search', 'Summarize', 'Extract', 'SQL Gen'],
                    datasets: [{
                        label: 'Requests',
                        data: [420, 310, 250, 180],
                        backgroundColor: secondaryBg,
                        borderColor: secondaryColor,
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: chartOptions
            });
        }

        // Outcome Tab Chart 2 (Line)
        if(document.getElementById('chart-outcome-2')) {
            window.dashboardCharts['outcome-2'] = new Chart(document.getElementById('chart-outcome-2'), {
                type: 'line',
                data: {
                    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
                    datasets: [{
                        label: 'Savings ($)',
                        data: [12000, 15000, 22000, 28000, 35000],
                        borderColor: '#22c55e',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: chartOptions
            });
        }

        // Benchmarking Tab Chart 2 (Radar or Bar - using Bar for simplicity)
        if(document.getElementById('chart-benchmarking-2')) {
            window.dashboardCharts['benchmarking-2'] = new Chart(document.getElementById('chart-benchmarking-2'), {
                type: 'bar',
                data: {
                    labels: ['Finance', 'HR', 'Engineering', 'Legal'],
                    datasets: [{
                        label: 'Accuracy %',
                        data: [94, 98, 91, 96],
                        backgroundColor: 'rgba(168, 85, 247, 0.2)',
                        borderColor: '#a855f7',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: { ...chartOptions, indexAxis: 'y' }
            });
        }

        // Storage Tab Chart 2 (Line)
        if(document.getElementById('chart-storage-2')) {
            window.dashboardCharts['storage-2'] = new Chart(document.getElementById('chart-storage-2'), {
                type: 'line',
                data: {
                    labels: ['W1', 'W2', 'W3', 'W4'],
                    datasets: [{
                        label: 'Growth (TB)',
                        data: [2.1, 2.4, 2.9, 3.5],
                        borderColor: primaryColor,
                        backgroundColor: primaryBg,
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: chartOptions
            });
        }
"""

# Insert new_charts_js before the end of initCharts function
# We can find `    // Call initCharts on window load` and insert right before it.
content = content.replace("    // Call initCharts on window load", new_charts_js + "\n    // Call initCharts on window load")

with open('app/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Right column charts added successfully.")
