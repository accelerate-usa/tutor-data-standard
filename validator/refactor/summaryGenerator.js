function generateSummary(rows, headers, type) {
    const summaryDiv = document.getElementById('summary' + (type === 'school' ? 'School' : 'Provider'));
    const uuid = generateUUID();
    const numRows = rows.length - 1;

    // Calculate percentage of non-missing values per column
    const columnStats = {};
    headers.forEach((header, colIndex) => {
        let nonMissingCount = 0;
        for (let i = 1; i < rows.length; i++) {
            const cell = rows[i][colIndex];
            if (cell !== null && cell !== undefined && cell.toString().trim() !== '') {
                nonMissingCount++;
            }
        }
        const percentNonMissing = ((nonMissingCount / numRows) * 100).toFixed(2);
        columnStats[header] = percentNonMissing + '%';
    });

    // Create summary object
    const summary = {
        uuid: uuid,
        numberOfRows: numRows,
        percentNonMissingPerColumn: columnStats
    };

    if (type === 'school') {
        // Calculate district_id counts
        const districtCounts = {};
        const districtIdIndex = headers.indexOf('district_id');
        if (districtIdIndex !== -1) {
            for (let i = 1; i < rows.length; i++) {
                const districtId = rows[i][districtIdIndex];
                if (districtId !== null && districtId !== undefined && districtId.toString().trim() !== '') {
                    districtCounts[districtId] = (districtCounts[districtId] || 0) + 1;
                }
            }
            summary.districtCounts = districtCounts;
        }
    }

    // Display summary in the UI
    summaryDiv.innerHTML = `
        <h2>Data Summary</h2>
        <pre>${JSON.stringify(summary, null, 2)}</pre>
        <button class="download-button" onclick='downloadJSON(${JSON.stringify(summary)}, "data_summary_${type}.json")'>Download Summary</button>
    `;
}
