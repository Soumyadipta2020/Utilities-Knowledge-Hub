import re

with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_fetch_logic = """    function fetchDatasets() {
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
    }"""

new_fetch_logic = """    function fetchDatasets() {
        fetch('/api/datasets')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const datasets = data.datasets;
                    // Add fallbacks just in case
                    if(!datasets || datasets.length === 0) {
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
    }"""

if old_fetch_logic in content:
    content = content.replace(old_fetch_logic, new_fetch_logic)
    with open('app/templates/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully replaced fetchDatasets in index.html")
else:
    print("Could not find the exact old fetchDatasets block in index.html")
