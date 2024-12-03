// Function to generate output JSON data
function generateOutput(rows, headers, type) {
    // Exclude header row from data rows
    const dataRows = rows.slice(1);
    const totalRows = dataRows.length;

    // Initialize column completion stats
    let columnCompletion = {};

    headers.forEach((header, index) => {
        let nonEmptyCount = 0;

        dataRows.forEach(row => {
            const cell = row[index];
            if (cell !== null && cell !== undefined && cell.toString().trim() !== '') {
                nonEmptyCount++;
            }
        });

        const percentComplete = ((nonEmptyCount / totalRows) * 100).toFixed(2);
        columnCompletion[header] = {
            "non_empty_cells": nonEmptyCount,
            "percent_complete": percentComplete + '%'
        };
    });

    // Create output JSON
    const outputData = {
        "total_rows": totalRows,
        "column_completion": columnCompletion
    };

    // Convert to JSON string
    const jsonString = JSON.stringify(outputData, null, 2);

    // Display the JSON in the output div and provide copy/download buttons
    const resultDiv = document.getElementById('output' + (type === 'school' ? 'School' : 'Provider'));
    resultDiv.innerHTML += `
        <h3>Data Summary:</h3>
        <pre id="jsonOutput">${jsonString}</pre>
        <button onclick="copyJSON('${type}')">Copy JSON</button>
        <button onclick="downloadJSON('${type}')">Download JSON</button>
    `;
}

// Function to copy JSON to clipboard
function copyJSON(type) {
    const jsonOutput = document.querySelector('#output' + (type === 'school' ? 'School' : 'Provider') + ' #jsonOutput');
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(jsonOutput);
    selection.removeAllRanges();
    selection.addRange(range);
    try {
        document.execCommand('copy');
        alert('JSON copied to clipboard');
    } catch (err) {
        alert('Failed to copy JSON');
    }
    selection.removeAllRanges();
}

// Function to download JSON as a file
function downloadJSON(type) {
    const jsonOutput = document.querySelector('#output' + (type === 'school' ? 'School' : 'Provider') + ' #jsonOutput').textContent;
    const blob = new Blob([jsonOutput], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = type + '_data_summary.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
