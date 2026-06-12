document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('generate-form');
    const ddlInput = document.getElementById('ddl-input');
    const rowsInput = document.getElementById('rows-input');
    const generateBtn = document.getElementById('generate-btn');
    const btnText = document.querySelector('.btn-text');
    const spinner = document.querySelector('.spinner');
    const errorMsg = document.getElementById('error-message');
    
    const tokenCounterElement = document.getElementById('token-counter');
    const tabsContainer = document.getElementById('tabs');
    const resultsContent = document.getElementById('results-content');
    const tokenCountValue = document.getElementById('token-count-value');

    let currentData = null;
    let globalTokenCount = 0;
    // Clear any old saved tokens from localStorage just in case
    localStorage.removeItem('tokenCount');
    if (tokenCountValue) {
        tokenCountValue.textContent = globalTokenCount;
    }
    if (tokenCounterElement) {
        if (globalTokenCount === 0) {
            tokenCounterElement.classList.add('hidden');
        } else {
            tokenCounterElement.classList.remove('hidden');
        }
    }



    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const ddl = ddlInput.value.trim();
        const rows = parseInt(rowsInput.value);

        if (!ddl) return;

        // UI Loading state
        generateBtn.disabled = true;
        btnText.classList.add('hidden');
        spinner.classList.remove('hidden');
        errorMsg.classList.add('hidden');
        // We do not hide the persistent token counter during loading
        resultsContent.innerHTML = '<div class="empty-state"><p>Generating data (calling LLM)...</p></div>';

        try {
            const isLocalOrDifferentPort = window.location.protocol === 'file:' || window.location.port !== '8000';
            const baseUrl = isLocalOrDifferentPort ? 'http://localhost:8000' : '';
            const response = await fetch(`${baseUrl}/api/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ddl, rows })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'An error occurred during generation.');
            }

            currentData = data;
            
            // Accumulate tokens
            if (data.tokens_used) {
                globalTokenCount += data.tokens_used;
                if (tokenCountValue) tokenCountValue.textContent = globalTokenCount;
                if (globalTokenCount > 0 && tokenCounterElement) {
                    tokenCounterElement.classList.remove('hidden');
                }
            }
            renderTabs();
            if (tabsContainer.firstChild) {
                tabsContainer.firstChild.click(); // Default to first table
            }

        } catch (error) {
            errorMsg.textContent = error.message;
            errorMsg.classList.remove('hidden');
            resultsContent.innerHTML = '<div class="empty-state"><p>Error generating data.</p></div>';
        } finally {
            generateBtn.disabled = false;
            btnText.classList.remove('hidden');
            spinner.classList.add('hidden');
        }
    });

    function renderTabs() {
        tabsContainer.innerHTML = '';

        // Table tabs first
        currentData.tables.forEach((table, index) => {
            const tab = document.createElement('button');
            tab.className = 'tab';
            tab.textContent = table.name;
            tab.onclick = () => {
                setActiveTab(tab);
                renderTableViewer(index);
            };
            tabsContainer.appendChild(tab);
        });

        // Seed All tab last
        const seedTab = document.createElement('button');
        seedTab.className = 'tab';
        seedTab.textContent = 'seed_all.sql';
        seedTab.onclick = () => {
            setActiveTab(seedTab);
            renderSeedAll();
        };
        tabsContainer.appendChild(seedTab);
    }

    function setActiveTab(selectedTab) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        selectedTab.classList.add('active');
    }

    function renderSeedAll() {
        resultsContent.innerHTML = `<div class="code-viewer">${escapeHtml(currentData.seed_all)}</div>`;
    }

    function renderTableViewer(tableIndex) {
        const table = currentData.tables[tableIndex];

        resultsContent.innerHTML = `
            <div style="height: 100%; display: flex; flex-direction: column;">
                <div class="format-tabs" style="display: flex; justify-content: space-between; align-items: center; padding-right: 1rem;">
                    <div style="display: flex;">
                        <div class="format-tab active" id="view-table">Table Data</div>
                        <div class="format-tab" id="view-sql">SQL Insert</div>
                        <div class="format-tab" id="view-csv">CSV Data</div>
                    </div>
                    <button id="download-csv-btn" style="height: 32px; padding: 0 1rem; font-size: 0.85rem; background: var(--accent-red); color: white; box-shadow: 2px 2px 0px 0px #111111; transition: none;">Download CSV</button>
                </div>
                <div class="code-viewer" id="code-content" style="padding: 0;"></div>
            </div>
        `;

        function buildTableHtml(dataRows) {
            if (!dataRows || dataRows.length === 0) return '<div class="empty-state">No data</div>';
            const headers = Object.keys(dataRows[0]);
            let html = '<div class="data-table-container"><table class="data-table"><thead><tr>';
            headers.forEach(h => html += `<th>${escapeHtml(h)}</th>`);
            html += '</tr></thead><tbody>';
            dataRows.forEach(row => {
                html += '<tr>';
                headers.forEach(h => html += `<td>${escapeHtml(String(row[h] !== null ? row[h] : ''))}</td>`);
                html += '</tr>';
            });
            html += '</tbody></table></div>';
            return html;
        }

        const codeContent = document.getElementById('code-content');

        document.getElementById('download-csv-btn').onclick = () => {
            const blob = new Blob([table.csv], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${table.name}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        };

        document.getElementById('view-table').onclick = (e) => {
            document.querySelectorAll('.format-tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            codeContent.style.padding = '0';
            codeContent.innerHTML = buildTableHtml(table.data);
        };

        document.getElementById('view-sql').onclick = (e) => {
            document.querySelectorAll('.format-tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            codeContent.style.padding = '1.5rem';
            codeContent.innerHTML = escapeHtml(table.sql);
        };

        document.getElementById('view-csv').onclick = (e) => {
            document.querySelectorAll('.format-tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            codeContent.style.padding = '1.5rem';
            codeContent.innerHTML = escapeHtml(table.csv);
        };

        // Default
        document.getElementById('view-table').click();
    }

    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});