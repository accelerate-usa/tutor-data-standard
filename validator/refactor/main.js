// Variables to store selected files
let selectedFileSchool = null;
let selectedFileProvider = null;

// Function to switch tabs
function showTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(function(content) {
        content.classList.remove('active');
    });
    // Remove active class from all tabs
    document.querySelectorAll('.tab').forEach(function(tab) {
        tab.classList.remove('active');
    });
    // Show the selected tab content
    document.getElementById(tabName).classList.add('active');
    // Add active class to the selected tab
    event.target.classList.add('active');
}

// Close modal dialog
function closeModal() {
    const modal = document.getElementById('modal');
    modal.classList.remove('active');
}
