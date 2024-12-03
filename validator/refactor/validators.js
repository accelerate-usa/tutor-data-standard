// Validate file
function validateFile(type) {
    const selectedFile = type === 'school' ? selectedFileSchool : selectedFileProvider;

    const resultDiv = document.getElementById('output' + (type === 'school' ? 'School' : 'Provider'));
    resultDiv.innerHTML = ''; // Clear previous output

    // Clear previous summary
    const summaryDiv = document.getElementById('summary' + (type === 'school' ? 'School' : 'Provider'));
    summaryDiv.innerHTML = '';

    if (!selectedFile) {
        showModal('No File Selected', 'Please select a file to validate.');
        return;
    }

    const fileType = selectedFile.name.split('.').pop().toLowerCase();

    const reader = new FileReader();
    reader.onprogress = function(e) {
        if (e.lengthComputable) {
            const percentLoaded = Math.round((e.loaded / e.total) * 100);
            updateProgressBar(percentLoaded, type === 'school' ? 'School' : 'Provider');
        }
    };
    reader.onload = function(e) {
        const data = e.target.result;
        if (fileType === 'csv') {
            processCSV(data, type);
        } else if (fileType === 'xlsx') {
            processXLSX(data, type);
        } else if (fileType === 'json') {
            processJSON(data, type);
        } else {
            showModal('Unsupported File Type', 'Please upload a CSV, XLSX, or JSON file.');
        }
    };
    reader.onloadend = function() {
        updateProgressBar(100, type === 'school' ? 'School' : 'Provider');
    };

    if (fileType === "xlsx") {
        reader.readAsArrayBuffer(selectedFile);
    } else {
        reader.readAsText(selectedFile);
    }
}

// Function to delegate validation based on type
function validateData(rows, headers, type) {
    if (type === 'school') {
        validateSchoolData(rows, headers);
    } else if (type === 'provider') {
        validateProviderData(rows, headers);
    }
}
