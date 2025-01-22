function validateProviderData(rows) {
    const resultDiv = document.getElementById('outputProvider');
    let errors = [];

    if (rows.length <= 1) {
        resultDiv.innerHTML = '<p class="error">The file appears to be empty or only contains headers.</p>';
        return;
    }

    // Expected headers for provider data
    const expectedHeaders = ["student_id", "session_topic", "session_date", "session_duration", "tutor_id"];

    // Normalize headers from the file
    const headers = rows[0].map(header => header.trim());
    const headerSet = new Set(headers);

    // Check for missing headers
    const missingHeaders = expectedHeaders.filter(h => !headerSet.has(h));
    if (missingHeaders.length > 0) {
        resultDiv.innerHTML = `<h2 class="error">Invalid Headers</h2><p>The following headers are missing or misspelled:</p><ul>` + missingHeaders.map(h => `<li>${h}</li>`).join('') + `</ul>`;
        return;
    }

    // Validate each row
    rows.slice(1).forEach((row, index) => {
        // Skip empty rows
        if (row.every(cell => cell === '' || cell === null || cell === undefined)) {
            return;
        }

        const rowData = {};
        headers.forEach((header, idx) => {
            rowData[header] = row[idx];
        });

        // Validation rules for provider data

        // student_id should be a string of digits
        if (!/^\d+$/.test(rowData["student_id"])) {
            errors.push(`Row ${index + 2}: Invalid student_id "${rowData["student_id"]}"`);
        }

        // session_topic should be 'math' or 'ela'
        if (!["math", "ela"].includes(rowData["session_topic"].toLowerCase())) {
            errors.push(`Row ${index + 2}: Invalid session_topic "${rowData["session_topic"]}"`);
        }

        // session_date should be in YYYY-MM-DD format
        if (!/^\d{4}-\d{2}-\d{2}$/.test(rowData["session_date"])) {
            errors.push(`Row ${index + 2}: Invalid session_date "${rowData["session_date"]}"`);
        } else {
            const dateParts = rowData["session_date"].split('-');
            const year = parseInt(dateParts[0], 10);
            const month = parseInt(dateParts[1], 10);
            const day = parseInt(dateParts[2], 10);
            const date = new Date(year, month - 1, day);
            if (date.getFullYear() !== year || date.getMonth() + 1 !== month || date.getDate() !== day) {
                errors.push(`Row ${index + 2}: Invalid session_date "${rowData["session_date"]}"`);
            }
        }

        // session_duration should be a positive number (minutes)
        const duration = parseFloat(rowData["session_duration"]);
        if (isNaN(duration) || duration <= 0) {
            errors.push(`Row ${index + 2}: Invalid session_duration "${rowData["session_duration"]}"`);
        }

        // tutor_id should be a non-empty string
        if (typeof rowData["tutor_id"] !== 'string' || rowData["tutor_id"].trim() === '') {
            errors.push(`Row ${index + 2}: Invalid tutor_id "${rowData["tutor_id"]}"`);
        }
    });

    if (errors.length > 0) {
        resultDiv.innerHTML = '<h2 class="error">Errors Found:</h2><ul>' + errors.map(error => `<li>${error}</li>`).join('') + '</ul>';
    } else {
        resultDiv.innerHTML = `<h2 class="success"><i class="fas fa-check-circle"></i> Congratulations! Your data are valid.</h2>`;
        generateSummary(rows, headers, 'provider');
    }
}
