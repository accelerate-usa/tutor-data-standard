// Handle file selection
function handleFileSelect(event, type) {
    const fileInput = event.target;
    const file = fileInput.files[0];
    if (type === 'School') {
        selectedFileSchool = file;
    } else {
        selectedFileProvider = file;
    }
    // Update UI
    const fileUpload = document.getElementById('fileUpload' + type);
    fileUpload.querySelector('p').textContent = 'File selected: ' + file.name;
}

// Handle drag over
function handleDragOver(event, type) {
    event.preventDefault();
    const fileUpload = document.getElementById('fileUpload' + type);
    fileUpload.classList.add('dragover');
}

// Handle drag leave
function handleDragLeave(event, type) {
    event.preventDefault();
    const fileUpload = document.getElementById('fileUpload' + type);
    fileUpload.classList.remove('dragover');
}

// Handle file drop
function handleFileDrop(event, type) {
    event.preventDefault();
    const files = event.dataTransfer.files;
    if (files.length > 0) {
        if (type === 'School') {
            selectedFileSchool = files[0];
            document.getElementById('fileInputSchool').files = files;
        } else {
            selectedFileProvider = files[0];
            document.getElementById('fileInputProvider').files = files;
        }
        // Update UI
        const fileUpload = document.getElementById('fileUpload' + type);
        fileUpload.querySelector('p').textContent = 'File selected: ' + files[0].name;
        fileUpload.classList.remove('dragover');
    }
}

function processCSV(data, type) {
    // Split the data into rows, filter out empty lines
    const rows = data.split('\n')
        .map(row => row.trim())
        .filter(row => row !== '')
        .map(row => row.split(',').map(cell => cell.trim()));
    const headers = rows[0];
    validateData(rows, headers, type);
}

function processXLSX(data, type) {
    const workbook = XLSX.read(data, { type: 'array' });
    const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
    let rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
    // Filter out empty rows
    rows = rows.filter(row => row.some(cell => cell !== null && cell !== undefined && cell.toString().trim() !== ''))
        .map(row => row.map(cell => (typeof cell === 'string') ? cell.trim() : cell));
    const headers = rows[0];
    validateData(rows, headers, type);
}

function processJSON(data, type) {
    const jsonData = JSON.parse(data);
    if (jsonData.length === 0) {
        showModal('Empty File', 'The JSON file appears to be empty.');
        return;
    }
    const headers = Object.keys(jsonData[0]);
    const rows = [headers].concat(jsonData.map(obj => headers.map(header => obj[header])));
    validateData(rows, headers, type);
}
