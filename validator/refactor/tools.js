// Update progress bar
function updateProgressBar(percent, type) {
    const progressBar = document.getElementById('progress-bar' + type);
    const progressText = document.getElementById('progressText' + type);
    progressBar.style.width = percent + '%';
    progressText.textContent = percent + '%';
}

// Show modal dialog
function showModal(title, message) {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modalTitle');
    const modalMessage = document.getElementById('modalMessage');
    modalTitle.textContent = title;
    modalMessage.textContent = message;
    modal.classList.add('active');
}

// Generate UUID
function generateUUID() {
    // Simple UUID generator
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = (Math.random() * 16) | 0,
            v = c === 'x' ? r : (r & 0x3) | 0x8;
        return v.toString(16);
    });
}

// Function to download JSON
function downloadJSON(data, filename) {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", filename);
    document.body.appendChild(downloadAnchor); // required for firefox
    downloadAnchor.click();
    downloadAnchor.remove();
}
