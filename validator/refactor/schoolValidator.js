function validateSchoolData(rows) {
    const resultDiv = document.getElementById('outputSchool');
    let errors = [];

    if (rows.length <= 1) {
        resultDiv.innerHTML = '<p class="error">The file appears to be empty or only contains headers.</p>';
        return;
    }

    // Expected headers for school data
    const expectedHeaders = [
        "student_id",
        "district_id",
        "district_name",
        "school_id",
        "school_name",
        "current_grade_level",
        "gender",
        "ethnicity",
        "ell",
        "iep",
        "gifted_flag",
        "homeless_flag",
        "ela_state_score_two_years_ago",
        "ela_state_score_one_year_ago",
        "ela_state_score_current_year",
        "math_state_score_two_years_ago",
        "math_state_score_one_year_ago",
        "math_state_score_current_year",
        "performance_level_prior_year",
        "performance_level_current_year",
        "disability",
        "economic disadvantage"
    ];

    // Normalize headers from the file
    const headers = rows[0].map(header => header.trim());
    const headerSet = new Set(headers);

    // Check for missing headers
    const missingHeaders = expectedHeaders.filter(h => !headerSet.has(h));
    if (missingHeaders.length > 0) {
        resultDiv.innerHTML = `<h2 class="error">Invalid Headers</h2><p>The following headers are missing or misspelled:</p><ul>` + missingHeaders.map(h => `<li>${h}</li>`).join('') + `</ul>`;
        return;
    }

    // Initialize sets to collect unique values
    let uniqueEthnicities = new Set();
    let uniquePerformanceLevelsPrior = new Set();
    let uniquePerformanceLevelsCurrent = new Set();

    // Validation functions for each field
    const fieldValidations = {
        "student_id": function(value) {
            // Should be a string of digits, length 10
            if (!/^\d{10}$/.test(value)) {
                return 'Invalid student_id "' + value + '" (should be a 10-digit number)';
            }
            return null; // No error
        },
        "district_id": function(value) {
            // Should be a string of digits, length 7
            if (!/^\d{7}$/.test(value)) {
                return 'Invalid district_id "' + value + '" (should be a 7-digit number)';
            }
            return null;
        },
        "district_name": function(value) {
            // Any string
            return null;
        },
        "school_id": function(value) {
            // Should be a string of digits, length 6
            if (!/^\d{6}$/.test(value)) {
                return 'Invalid school_id "' + value + '" (should be a 6-digit number)';
            }
            return null;
        },
        "school_name": function(value) {
            // Any string
            return null;
        },
        "current_grade_level": function(value) {
            // Integer between 0 and 12 inclusive
            const intValue = parseInt(value, 10);
            if (isNaN(intValue) || intValue < 0 || intValue > 12) {
                return 'Invalid current_grade_level "' + value + '" (should be integer between 0 and 12)';
            }
            return null;
        },
        "gender": function(value) {
            // Should be 'Male' or 'Female'
            if (!['Male', 'Female'].includes(value)) {
                return 'Invalid gender "' + value + '" (should be "Male" or "Female")';
            }
            return null;
        },
        "ethnicity": function(value) {
            // Any string
            uniqueEthnicities.add(value);
            return null;
        },
        "ell": function(value) {
            // Boolean: 'TRUE' or 'FALSE'
            if (!['TRUE', 'FALSE'].includes(value)) {
                return 'Invalid ell "' + value + '" (should be "TRUE" or "FALSE")';
            }
            return null;
        },
        "iep": function(value) {
            // Boolean: 'TRUE' or 'FALSE'
            if (!['TRUE', 'FALSE'].includes(value)) {
                return 'Invalid iep "' + value + '" (should be "TRUE" or "FALSE")';
            }
            return null;
        },
        "gifted_flag": function(value) {
            if (!['TRUE', 'FALSE'].includes(value)) {
                return 'Invalid gifted_flag "' + value + '" (should be "TRUE" or "FALSE")';
            }
            return null;
        },
        "homeless_flag": function(value) {
            if (!['TRUE', 'FALSE'].includes(value)) {
                return 'Invalid homeless_flag "' + value + '" (should be "TRUE" or "FALSE")';
            }
            return null;
        },
        "ela_state_score_two_years_ago": function(value) {
            // Integer between 650 and 800
            const intValue = parseInt(value, 10);
            if (isNaN(intValue) || intValue < 650 || intValue > 800) {
                return 'Invalid ela_state_score_two_years_ago "' + value + '" (should be integer between 650 and 800)';
            }
            return null;
        },
        "ela_state_score_one_year_ago": function(value) {
            // Same as above
            const intValue = parseInt(value, 10);
            if (isNaN(intValue) || intValue < 650 || intValue > 800) {
                return 'Invalid ela_state_score_one_year_ago "' + value + '" (should be integer between 650 and 800)';
            }
            return null;
        },
        "ela_state_score_current_year": function(value) {
            // Same as above
            const intValue = parseInt(value, 10);
            if (isNaN(intValue) || intValue < 650 || intValue > 800) {
                return 'Invalid ela_state_score_current_year "' + value + '" (should be integer between 650 and 800)';
            }
            return null;
        },
        "math_state_score_two_years_ago": function(value) {
            // Integer between 650 and 800
            const intValue = parseInt(value, 10);
            if (isNaN(intValue) || intValue < 650 || intValue > 800) {
                return 'Invalid math_state_score_two_years_ago "' + value + '" (should be integer between 650 and 800)';
            }
            return null;
        },
        "math_state_score_one_year_ago": function(value) {
            // Integer between 650 and 800
            const intValue = parseInt(value, 10);
            if (isNaN(intValue) || intValue < 650 || intValue > 800) {
                return 'Invalid math_state_score_one_year_ago "' + value + '" (should be integer between 650 and 800)';
            }
            return null;
        },
        "math_state_score_current_year": function(value) {
            // Integer between 650 and 800
            const intValue = parseInt(value, 10);
            if (isNaN(intValue) || intValue < 650 || intValue > 800) {
                return 'Invalid math_state_score_current_year "' + value + '" (should be integer between 650 and 800)';
            }
            return null;
        },
        "performance_level_prior_year": function(value) {
            // Collect unique performance levels
            uniquePerformanceLevelsPrior.add(value);
            return null;
        },
        "performance_level_current_year": function(value) {
            uniquePerformanceLevelsCurrent.add(value);
            return null;
        },
        "disability": function(value) {
            // Boolean: 'TRUE' or 'FALSE'
            if (!['TRUE', 'FALSE'].includes(value)) {
                return 'Invalid disability "' + value + '" (should be "TRUE" or "FALSE")';
            }
            return null;
        },
        "economic disadvantage": function(value) {
            // Boolean: 'TRUE' or 'FALSE'
            if (!['TRUE', 'FALSE'].includes(value)) {
                return 'Invalid economic disadvantage "' + value + '" (should be "TRUE" or "FALSE")';
            }
            return null;
        },
    };

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

        // For each field, apply the validation function
        expectedHeaders.forEach(field => {
            const value = rowData[field];
            const validationFn = fieldValidations[field];
            if (validationFn) {
                const error = validationFn(value);
                if (error) {
                    errors.push(`Row ${index + 2}: ${error}`);
                }
            }
        });
    });

    // After processing all rows, check unique values
    if (uniqueEthnicities.size > 10) {
        errors.push(`The 'ethnicity' column has more than 10 unique values (${uniqueEthnicities.size})`);
    }
    if (uniquePerformanceLevelsPrior.size > 6) {
        errors.push(`The 'performance_level_prior_year' column has more than 6 unique values (${uniquePerformanceLevelsPrior.size})`);
    }
    if (uniquePerformanceLevelsCurrent.size > 6) {
        errors.push(`The 'performance_level_current_year' column has more than 6 unique values (${uniquePerformanceLevelsCurrent.size})`);
    }

    if (errors.length > 0) {
        resultDiv.innerHTML = '<h2 class="error">Errors Found:</h2><ul>' + errors.map(error => `<li>${error}</li>`).join('') + '</ul>';
    } else {
        resultDiv.innerHTML = `
            <h2 class="success">
                <i class="fas fa-check-circle"></i> Congratulations! Your data are valid.
            </h2>
            <div class="note">
                If you'd like to join the list of agencies dedicated to data quality, please upload the output below to this website: 
                <a href="https://accelerate.us/placeholder" target="_blank">https://accelerate.us/placeholder</a>. 
                Rename the file to your agency name. Feel free to redact any information you don't want to share.
            </div>`;
        // If needed, call a function to handle valid data
        generateSummary(rows, headers, 'school');
    }
    
}