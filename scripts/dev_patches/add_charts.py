import re

with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add Chart.js CDN before the other scripts
if 'chart.js' not in content:
    content = content.replace(
        '<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>',
        '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>'
    )

# Insert Canvas into each tab
tabs = ['info', 'knowledge', 'inference', 'outcome', 'benchmarking', 'storage']
titles = {
    'info': 'Ingestion Volume (Last 7 Days)',
    'knowledge': 'Graph Entities Growth',
    'inference': 'Query Latency (ms)',
    'outcome': 'Automated Resolutions vs Escalations',
    'benchmarking': 'F1 Score Trend',
    'storage': 'Database Utilization'
}

for tab in tabs:
    # Look for the end of the tab div. We can find it by finding the next <div id="tab- or </main>
    # It's safer to use regex to inject right before the end of the tab's specific block.
    # Since we know the exact structure, we can just find the closing </div> of each tab.
    # Actually, we can just replace the specific headers from the bottom, or just append to the content of the tab.
    # We'll use a regex that captures the tab content up to the next tab or </main>
    
    chart_html = f"""
            <div style="margin-top: 12px; height: 180px; width: 100%; padding: 12px; background: rgba(20, 20, 20, 0.8); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px;">
                <h4 style="font-size: 11px; color: #fff; text-transform: uppercase; margin-bottom: 8px; margin-top: 0;">{titles[tab]}</h4>
                <div style="position: relative; height: 140px; width: 100%;">
                    <canvas id="chart-{tab}"></canvas>
                </div>
            </div>
    """
    
    # We will insert chart_html right before the end of the tab's div.
    # To do this safely, we match the feature-list or dashboard-grid at the end of the tab.
    if tab == 'info':
        content = content.replace('<span id="sap-sync-status" class="status-badge" style="background: rgba(250, 204, 21, 0.15); color: #facc15;">Syncing (92%)</span>\n                </div>\n            </div>',
                                  '<span id="sap-sync-status" class="status-badge" style="background: rgba(250, 204, 21, 0.15); color: #facc15;">Syncing (92%)</span>\n                </div>\n            </div>' + chart_html)
    elif tab == 'knowledge':
        content = content.replace('<div class="metric-change">↑ 0.2% improvement</div>\n                </div>\n            </div>',
                                  '<div class="metric-change">↑ 0.2% improvement</div>\n                </div>\n            </div>' + chart_html)
    elif tab == 'inference':
        content = content.replace('<div class="metric-change" style="color: var(--text-muted);">Router, Embed, Generate</div>\n                </div>\n            </div>',
                                  '<div class="metric-change" style="color: var(--text-muted);">Router, Embed, Generate</div>\n                </div>\n            </div>' + chart_html)
    elif tab == 'outcome':
        content = content.replace('<div class="metric-change">Reduced turnaround</div>\n                </div>\n            </div>',
                                  '<div class="metric-change">Reduced turnaround</div>\n                </div>\n            </div>' + chart_html)
    elif tab == 'benchmarking':
        content = content.replace('<div class="metric-change">↓ Below 1% threshold</div>\n                </div>\n            </div>',
                                  '<div class="metric-change">↓ Below 1% threshold</div>\n                </div>\n            </div>' + chart_html)
    elif tab == 'storage':
        content = content.replace('<span class="status-badge">Operational</span>\n                </div>\n            </div>',
                                  '<span class="status-badge">Operational</span>\n                </div>\n            </div>' + chart_html)

# Add the Chart JS rendering logic at the end of the file, before </body>
chart_js_code = """
<script>
    window.dashboardCharts = {};
    
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: { color: 'rgba(255,255,255,0.05)' },
                ticks: { color: '#a1a1aa', font: { size: 10 } }
            },
            x: {
                grid: { display: false },
                ticks: { color: '#a1a1aa', font: { size: 10 } }
            }
        }
    };

    function initCharts() {
        const primaryColor = 'rgba(249, 115, 22, 1)';
        const primaryBg = 'rgba(249, 115, 22, 0.2)';
        const secondaryColor = 'rgba(34, 197, 94, 1)';
        const secondaryBg = 'rgba(34, 197, 94, 0.2)';

        // Info Tab Chart (Bar)
        if(document.getElementById('chart-info')) {
            window.dashboardCharts['info'] = new Chart(document.getElementById('chart-info'), {
                type: 'bar',
                data: {
                    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                    datasets: [{
                        label: 'Docs Ingested',
                        data: [12000, 19000, 15000, 22000, 18000, 9000, 11000],
                        backgroundColor: primaryBg,
                        borderColor: primaryColor,
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: chartOptions
            });
        }

        // Knowledge Tab Chart (Line)
        if(document.getElementById('chart-knowledge')) {
            window.dashboardCharts['knowledge'] = new Chart(document.getElementById('chart-knowledge'), {
                type: 'line',
                data: {
                    labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
                    datasets: [
                        { label: 'Nodes', data: [500000, 620000, 750000, 845000], borderColor: primaryColor, backgroundColor: primaryBg, fill: true, tension: 0.4 },
                        { label: 'Edges', data: [1200000, 1800000, 2500000, 3200000], borderColor: secondaryColor, backgroundColor: secondaryBg, fill: true, tension: 0.4 }
                    ]
                },
                options: chartOptions
            });
        }

        // Inference Tab Chart (Line)
        if(document.getElementById('chart-inference')) {
            window.dashboardCharts['inference'] = new Chart(document.getElementById('chart-inference'), {
                type: 'line',
                data: {
                    labels: ['10:00', '11:00', '12:00', '13:00', '14:00', '15:00'],
                    datasets: [{
                        label: 'Latency (ms)',
                        data: [450, 480, 420, 410, 460, 420],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.2)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: chartOptions
            });
        }

        // Outcome Tab Chart (Stacked Bar)
        if(document.getElementById('chart-outcome')) {
            window.dashboardCharts['outcome'] = new Chart(document.getElementById('chart-outcome'), {
                type: 'bar',
                data: {
                    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
                    datasets: [
                        { label: 'Automated', data: [8000, 9500, 10200, 11500, 12450], backgroundColor: secondaryBg, borderColor: secondaryColor, borderWidth: 1 },
                        { label: 'Escalated', data: [2000, 1800, 1500, 1200, 900], backgroundColor: 'rgba(239, 68, 68, 0.2)', borderColor: 'rgba(239, 68, 68, 1)', borderWidth: 1 }
                    ]
                },
                options: {
                    ...chartOptions,
                    scales: {
                        x: { stacked: true, grid: { display: false }, ticks: { color: '#a1a1aa', font: { size: 10 } } },
                        y: { stacked: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#a1a1aa', font: { size: 10 } } }
                    }
                }
            });
        }

        // Benchmarking Tab Chart (Line)
        if(document.getElementById('chart-benchmarking')) {
            window.dashboardCharts['benchmarking'] = new Chart(document.getElementById('chart-benchmarking'), {
                type: 'line',
                data: {
                    labels: ['v1.0', 'v1.1', 'v1.2', 'v2.0', 'v2.1'],
                    datasets: [{
                        label: 'F1 Score',
                        data: [0.85, 0.87, 0.89, 0.91, 0.92],
                        borderColor: primaryColor,
                        backgroundColor: primaryBg,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: chartOptions
            });
        }

        // Storage Tab Chart (Doughnut/Bar)
        if(document.getElementById('chart-storage')) {
            window.dashboardCharts['storage'] = new Chart(document.getElementById('chart-storage'), {
                type: 'bar',
                data: {
                    labels: ['Vector DB', 'Graph DB', 'Cold Storage'],
                    datasets: [{
                        label: 'Capacity Used (%)',
                        data: [42, 65, 28],
                        backgroundColor: [primaryBg, secondaryBg, 'rgba(59, 130, 246, 0.2)'],
                        borderColor: [primaryColor, secondaryColor, '#3b82f6'],
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    ...chartOptions,
                    indexAxis: 'y'
                }
            });
        }
    }

    // Call initCharts on window load
    window.addEventListener('load', initCharts);

    // Patch switchMainTab to resize charts when they become visible
    const originalSwitch = window.switchMainTab;
    if (typeof originalSwitch !== 'undefined') {
        window.switchMainTab = function(el, tabId) {
            originalSwitch(el, tabId);
            // Trigger chart resize after a tiny delay to let CSS apply display:flex
            setTimeout(() => {
                Object.values(window.dashboardCharts).forEach(chart => {
                    chart.resize();
                });
            }, 10);
        };
    }
</script>
</body>"""

content = content.replace('</body>', chart_js_code)

# We need to make sure switchMainTab is actually patchable (it needs to be accessible globally)
# In the original HTML, switchMainTab is just defined in a script tag as `function switchMainTab(el, tabId)`.
# So patching window.switchMainTab works perfectly.

with open('app/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Charts successfully added")
